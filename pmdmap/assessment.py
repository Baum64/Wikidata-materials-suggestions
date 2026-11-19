"""Paket 0: Vorschlag je bestehendem Ontologie-Link.

Zwei getrennte Quellen, im Begruendungstext gekennzeichnet:
  "Regel:"        mechanische Pruefungen (IRI, Property, Qualifier, Labels,
                  Element-Erkennung, Begriffsart, Mehrfachbelegung)
  "Einschätzung:" fachliche Einschaetzung nach Lesen der Definitionen,
                  gepflegt in pmdmap/einschaetzungen/<profil>.yaml

Die Entscheidung trifft immer der Mensch (Spalten entscheidung*).
Grenzfaelle (Vorschlag "offen" oder als grenzfall markiert) gehen
zusaetzlich nach proposals/review-needed.md (CLAUDE.md, Arbeitsweise 3).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import Config
from .ontology import Ontology

BEHALTEN = "behalten"
P4390_ERGAENZEN = "P4390 ergänzen"
UMSTELLEN = "umstellen auf P2888+P4390"
ENTFERNEN = "entfernen"
OFFEN = "offen"
VORSCHLAEGE = (BEHALTEN, P4390_ERGAENZEN, UMSTELLEN, ENTFERNEN, OFFEN)
# Pakete 1/2: neue Aussagen
NEU_P1709 = "neu: P1709"
NEU_P2888 = "neu: P2888+P4390"
NEU_P1628 = "neu: P1628"
VERWERFEN = "verwerfen"
VORSCHLAEGE_NEU = (NEU_P1709, NEU_P2888, NEU_P1628, VERWERFEN, OFFEN, BEHALTEN)
# hoehere Zahl gewinnt, wenn mehrere Regeln greifen
_RANK = {BEHALTEN: 0, P4390_ERGAENZEN: 1, UMSTELLEN: 2, ENTFERNEN: 3, OFFEN: 4}


@dataclass
class Finding:
    code: str
    text: str
    vorschlag: str | None = None   # None = nur Hinweis
    grenzfall: bool = False


@dataclass
class Assessment:
    vorschlag: str
    vorschlag_p4390: str              # QID oder ""
    findings: list[Finding] = field(default_factory=list)
    begruendung: str = ""
    grenzfall: bool = False
    rule_vorschlag: str = ""          # Vorschlag der Regeln, vor einer Einschaetzung

    @property
    def codes(self) -> list[str]:
        return [f.code for f in self.findings]


def normalize(label: str) -> str:
    """Fuer den Label-Vergleich: klein, ohne Klammerzusatz, ohne Leerraum
    und Bindestriche ("vacancy (crystal)" == "vacancy",
    "auto-ignition" == "autoignition", "cross-linking" == "crosslinking")."""
    s = re.sub(r"\([^)]*\)", " ", label.lower())
    return re.sub(r"[\s\-_]+", "", s)


def _label_sets(entity: dict, cls) -> tuple[dict[str, set], dict[str, set]]:
    wd = {
        lang: {normalize(x) for x in [entity.get(f"label_{lang}", ""), *entity.get(f"aliases_{lang}", [])] if x}
        for lang in ("en", "de")
    }
    pmd = {
        lang: {normalize(x) for x in [cls.labels.get(lang, ""), *cls.synonyms.get(lang, [])] if x}
        for lang in ("en", "de")
    }
    return wd, pmd


def load_assessments(path: Path | None) -> dict[str, dict]:
    if not path or not Path(path).exists():
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {str(k): v for k, v in data.items()}


class Assessor:
    def __init__(self, cfg: Config, onto: Ontology, snap: dict, manual: dict[str, dict] | None = None):
        self.cfg = cfg
        self.onto = onto
        self.snap = snap
        self.manual = manual or {}
        self.allowed = set(snap["mapping_relation_allowed"])
        self.labels = snap["labels"]
        # Mehrfachbelegung: gleiche Ontologieklasse an mehreren Eintraegen
        self.iri_count = Counter(
            m["value"] for m in snap["mappings"] if m["prop"] in ("P1709", "P2888", "P3950")
        )
        self.entity_count = Counter(m["entity"] for m in snap["mappings"])
        self.p4390_by_label = {
            self.labels.get(q, {}).get("en", "").lower(): q for q in snap["mapping_relation_allowed"]
        }

    def label(self, qid: str) -> str:
        lab = self.labels.get(qid, {})
        return lab.get("de") or lab.get("en") or qid

    def p4390_qid(self, name: str) -> str:
        """'narrow match' -> QID laut Constraint; leer, wenn nicht erlaubt."""
        return self.p4390_by_label.get(name.lower(), "")

    # --- Regeln -----------------------------------------------------------
    def assess(self, m: dict) -> Assessment:
        cfg, onto = self.cfg, self.onto
        short, version = cfg.profile.short_name, self.onto.meta.version
        qid, prop, iri = m["entity"], m["prop"], m["value"]
        ent = self.snap["entities"].get(qid, {})
        cls = onto.get(iri)
        f: list[Finding] = []
        p4390 = ""

        # IRI selbst
        if not m["iri_ok"]:
            f.append(Finding("iri-ungueltig", f"IRI ungültig ({m['iri_problem']})", OFFEN, True))
        elif cls is None:
            f.append(Finding("iri-unbekannt", f"IRI fehlt in {short} {version} (Tippfehler oder entfernte Klasse?)", OFFEN, True))
        elif cls.deprecated:
            rep = f"; Ersatz laut {short}: {cls.replaced_by} ({onto.label_of(cls.replaced_by)})" if cls.replaced_by else ""
            f.append(Finding("iri-veraltet", f"Klasse in {short} {version} als veraltet markiert{rep}", OFFEN, True))

        # Property und Qualifier (E3/E4 + Praezisierung)
        if prop == "P3950":
            p4390 = self.p4390_qid("narrow match")
            f.append(Finding(
                "property-p3950",
                "P3950 (narrower external class) ist im Konzept nicht vorgesehen; inhaltlich entspricht "
                "das P2888 + P4390 = narrow match (Ontologieklasse enger als der Eintrag). "
                "Konventionsfrage: P3950 behalten oder vereinheitlichen",
                UMSTELLEN, True,
            ))
        elif prop == "P2888":
            if not m["p4390"]:
                f.append(Finding("p4390-fehlt", "P2888 ohne P4390 - nach E3 ist die Abbildungsart Pflicht", P4390_ERGAENZEN))
            for q in m["p4390"]:
                if q not in self.allowed:
                    f.append(Finding("p4390-unzulaessig", f"P4390-Wert {q} nicht im one-of-Constraint", OFFEN, True))
        elif prop == "P1709" and m["p4390"]:
            f.append(Finding("p4390-bei-p1709", "P4390 an P1709 ist überflüssig (Präzisierung E3/E4)"))
        elif prop == "P1628" and qid.startswith("Q"):
            f.append(Finding("p1628-an-item", "P1628 gehört an eine Wikidata-Eigenschaft, nicht an einen Eintrag", OFFEN, True))

        # Mehrfachbelegung: zwei Eintraege "aequivalent" zu einer Klasse
        if self.iri_count[iri] > 1:
            others = sorted({x["entity"] for x in self.snap["mappings"] if x["value"] == iri and x["entity"] != qid})
            f.append(Finding(
                "iri-mehrfach",
                f"dieselbe {short}-Klasse hängt auch an {', '.join(others)} - höchstens einer kann P1709 tragen",
                OFFEN, True,
            ))
        if self.entity_count[qid] > 1:
            f.append(Finding("eintrag-mehrfach", f"{qid} trägt {self.entity_count[qid]} {short}-Abbildungen"))

        # Element vs. Werkstoff (Periodensystem-Regel: Abbildung, kein Fall 1-4)
        category = m.get("category", "")
        if cfg.wikidata.element_class in ent.get("p31", []):
            text = (
                f"Eintrag ist P31 → chemisches Element ({cfg.wikidata.element_class}); "
                f"periodic-table-conventions: kein Fall 1–4 betroffen, P31 → {cfg.wikidata.element_class} bleibt"
            )
            if category == "werkstoff":
                f.append(Finding(
                    "element-statt-werkstoff",
                    text + f"; {short}-Klasse ist ein Werkstoff → keine volle Deckung (E4)",
                    UMSTELLEN, True,
                ))
            else:
                f.append(Finding("element", text))

        # Verdachtsfall laut Konzept
        if qid in cfg.suspects:
            f.append(Finding("verdachtsfall", f"Verdachtsfall laut Konzept: {cfg.suspects[qid]}", None, True))

        # Labels
        label_match = False
        if cls is not None:
            wd_l, pmd_l = _label_sets(ent, cls)
            hits = [lang for lang in ("en", "de") if wd_l[lang] & pmd_l[lang]]
            label_match = bool(hits)
            if not hits:
                f.append(Finding(
                    "label-abweichung",
                    f"Labels weichen ab: WD „{ent.get('label_de') or '–'}“/„{ent.get('label_en') or '–'}“ "
                    f"vs. {short} „{cls.labels.get('de', '–')}“/„{cls.labels.get('en', '–')}“",
                ))

        # Begriffsart (E2 / E7)
        if category and category not in ("werkstoff", "eigenschaft"):
            f.append(Finding("kein-werkstoff", f"Begriffsart {category}: E2 betrifft neue Abbildungen; hier nur P1709/P2888-Prüfung"))
        if category == "eigenschaft":
            for pid in ent.get("p1687", []):
                vals = self.snap["property_p1628"].get(pid, [])
                if iri in vals:
                    f.append(Finding("e7-p1628-vorhanden", f"E7: P1628 an {pid} ({self.label(pid)}) vorhanden"))
                else:
                    f.append(Finding("e7-p1628-fehlt", f"E7: zugehörige Eigenschaft {pid} ({self.label(pid)}) ohne P1628 auf diese Klasse → Paket 2"))

        # Vorschlag aus den Regeln
        vorschlag = BEHALTEN
        for x in f:
            if x.vorschlag and _RANK[x.vorschlag] > _RANK[vorschlag]:
                vorschlag = x.vorschlag
        if vorschlag == BEHALTEN and not label_match and cls is not None:
            vorschlag = OFFEN
        grenzfall = any(x.grenzfall for x in f)

        rule_texts = [x.text for x in f]
        if vorschlag == BEHALTEN:
            rule_texts.append("Label stimmt überein → behalten, sofern Definition und Umfang sich decken (gegenlesen)")
        elif vorschlag == OFFEN and not grenzfall:
            rule_texts.append("keine Regel entscheidet - Definitionen vergleichen")
        begruendung = "Regel: " + "; ".join(rule_texts)

        rule_vorschlag = vorschlag
        # Einschaetzung (ueberschreibt Vorschlag, nie die Regel-Befunde)
        manual = self.manual.get(qid)
        if manual and (not manual.get("iri") or manual["iri"] == iri):
            if manual.get("vorschlag"):
                if manual["vorschlag"] not in VORSCHLAEGE:
                    raise ValueError(f"Einschätzung {qid}: unbekannter Vorschlag {manual['vorschlag']!r}")
                vorschlag = manual["vorschlag"]
            if manual.get("p4390"):
                p4390 = self.p4390_qid(manual["p4390"]) or manual["p4390"]
            if "grenzfall" in manual:
                grenzfall = bool(manual["grenzfall"])
            if manual.get("begruendung"):
                begruendung += " | Einschätzung: " + " ".join(str(manual["begruendung"]).split())

        if vorschlag == OFFEN:
            grenzfall = True
        if vorschlag in (BEHALTEN, ENTFERNEN) and prop == "P1709":
            p4390 = ""
        return Assessment(vorschlag, p4390, f, begruendung, grenzfall, rule_vorschlag)


# --- Pakete 1/2: Kandidaten fuer neue Abbildungen ---------------------------
def load_candidate_assessments(path: Path | None) -> dict[str, dict[str, dict]]:
    """{PMD-IRI-Endung: {QID/PID: {...}}} aus pmdmap/einschaetzungen/<profil>_kandidaten.yaml."""
    if not path or not Path(path).exists():
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {str(k): {str(q): v for q, v in (vals or {}).items()} for k, vals in data.items()}


def _apply_manual(manual: dict | None, vorschlag: str, p4390: str, begruendung: str,
                  grenzfall: bool, p4390_qid, key: str) -> tuple[str, str, str, bool]:
    if not manual:
        return vorschlag, p4390, begruendung, grenzfall
    if manual.get("vorschlag"):
        if manual["vorschlag"] not in VORSCHLAEGE_NEU:
            raise ValueError(f"Einschätzung {key}: unbekannter Vorschlag {manual['vorschlag']!r}")
        vorschlag = manual["vorschlag"]
    if manual.get("p4390"):
        p4390 = p4390_qid(manual["p4390"]) or manual["p4390"]
    if "grenzfall" in manual:
        grenzfall = bool(manual["grenzfall"])
    if manual.get("begruendung"):
        begruendung += " | Einschätzung: " + " ".join(str(manual["begruendung"]).split())
    return vorschlag, p4390, begruendung, grenzfall


def assess_candidate(cfg: Config, onto: Ontology, pilot: dict, cand: dict, rank: int,
                     p4390_qid, manual: dict | None = None) -> Assessment:
    """Begriffs-Eintrag als Kandidat fuer eine Ontologieklasse (Paket 1/2).

    Regel-Vorschlag "neu: P1709" nur fuer Rang 1 mit exakt gleichem Label
    (oder Alias), der eine Klasse ist, in Paket 1 unter Material haengt und
    noch keine P1709 auf eine andere Klasse der Ontologie traegt. Alles
    andere ist "offen" (Rang 1) bzw. "verwerfen" (schwaechere Kandidaten
    ohne Labeltreffer). Definitionen vergleicht erst die Einschaetzung."""
    short = cfg.profile.short_name
    category = onto.category(pilot["iri"])
    f: list[Finding] = []
    lm = cand["label_match"]
    if lm:
        f.append(Finding("label-gleich", "Label/Alias stimmt überein (" + ", ".join(f"{k}: {v}" for k, v in sorted(lm.items())) + ")"))
    else:
        f.append(Finding("label-abweichung", "kein exakter Label-/Aliastreffer"))
    if not cand["is_class"]:
        # Grenzfall Instanz-vs-Klasse nur beim besten Kandidaten; weiter
        # hinten ist es meist ein Namensvetter (Film, Spiel, Artikel).
        f.append(Finding("keine-klasse", "kein P279 - eher Einzelsorte/Instanz als Klasse (E6, Instanz-vs-Klasse)", None, rank == 1))
    if pilot["paket"] == "1" and not cand["is_material"]:
        f.append(Finding("nicht-unter-material", f"hängt nicht (P279*) unter {cfg.wikidata.material_root} (material)"))
    if cand["is_element"]:
        f.append(Finding("element", f"Eintrag ist P31 → chemisches Element ({cfg.wikidata.element_class})"))
    p1709_elsewhere = [x for x in cand["onto_links"] if x.startswith("P1709:")]
    if cand["onto_links"]:
        f.append(Finding(
            "hat-schon-abbildung",
            f"trägt schon {short}-Abbildung(en): " + ", ".join(x.split(":", 1)[0] + " " + x.rsplit("/", 1)[-1] for x in cand["onto_links"]),
            None, bool(p1709_elsewhere),
        ))
    if pilot["paket"] == "1" and category != "werkstoff":
        f.append(Finding("pmd-kein-werkstoff", f"{short} modelliert „{pilot['label']}“ als {category or '?'}, nicht unter material"))
    if pilot.get("hint"):
        f.append(Finding("hinweis", pilot["hint"]))

    strong = bool(lm) and cand["is_class"] and (pilot["paket"] != "1" or cand["is_material"])
    if rank == 1:
        vorschlag = NEU_P1709 if strong and not p1709_elsewhere and not (pilot["paket"] == "1" and category != "werkstoff") else OFFEN
    else:
        # zweiter starker Treffer (gleiches Label, Klasse, ggf. Werkstoff) ist
        # eine echte Konkurrenz; Namensvettern ohne Klasse/Werkstoff nicht
        vorschlag = OFFEN if strong else VERWERFEN
    grenzfall = any(x.grenzfall for x in f) or (vorschlag == OFFEN and rank == 1)
    texts = [x.text for x in f] + [f"Rang {rank}, Score {cand['score']}"]
    if vorschlag == NEU_P1709:
        texts.append("→ P1709, sofern Definition und Umfang sich decken (gegenlesen)")
    begruendung = "Regel: " + "; ".join(texts)
    rule_vorschlag = vorschlag
    vorschlag, p4390, begruendung, grenzfall = _apply_manual(
        manual, vorschlag, "", begruendung, grenzfall, p4390_qid, cand["qid"])
    if manual and manual.get("vorschlag") and "grenzfall" not in manual:
        # Vorschlag per Einschaetzung geaendert: Grenzfall neu bestimmen
        grenzfall = any(x.grenzfall for x in f) or (vorschlag == OFFEN and rank == 1)
    return Assessment(vorschlag, p4390, f, begruendung, grenzfall, rule_vorschlag)


def assess_property(cfg: Config, pilot: dict, prop: dict, rank: int,
                    p4390_qid, manual: dict | None = None) -> Assessment:
    """Wikidata-Eigenschaft als Kandidat fuer P1628 (E7, Paket 2)."""
    f: list[Finding] = []
    iri = pilot["iri"]
    if iri in prop["p1628"]:
        f.append(Finding("p1628-vorhanden", "P1628 auf diese Klasse ist schon gesetzt"))
    elif prop["p1628"]:
        f.append(Finding("p1628-anderswohin", "P1628 zeigt schon auf: " + ", ".join(v.rsplit("/", 1)[-1] for v in prop["p1628"])))
    if prop["via_p1687"]:
        f.append(Finding("via-p1687", "Begriffs-Eintrag " + ", ".join(prop["via_p1687"]) + " nennt sie per P1687"))
    if prop["p1629_hits"]:
        f.append(Finding("via-p1629", "Eigenschaft nennt per P1629 den Begriffs-Eintrag " + ", ".join(prop["p1629_hits"])))
    if prop["label_match"]:
        f.append(Finding("label-gleich", "Label/Alias stimmt überein"))
    if prop["datatype"] != "quantity":
        f.append(Finding("datentyp", f"Datentyp {prop['datatype'] or '?'} statt quantity"))
    if pilot.get("hint"):
        f.append(Finding("hinweis", pilot["hint"]))

    strong = bool(prop["via_p1687"] or prop["p1629_hits"] or prop["label_match"])
    if iri in prop["p1628"]:
        vorschlag = BEHALTEN
    elif rank == 1 and strong and prop["datatype"] == "quantity":
        vorschlag = NEU_P1628
    elif strong:
        vorschlag = OFFEN
    else:
        vorschlag = VERWERFEN
    grenzfall = vorschlag == OFFEN and rank == 1
    texts = [x.text for x in f] + [f"Rang {rank}, Score {prop['score']}"]
    begruendung = "Regel: " + "; ".join(texts)
    rule_vorschlag = vorschlag
    vorschlag, p4390, begruendung, grenzfall = _apply_manual(
        manual, vorschlag, "", begruendung, grenzfall, p4390_qid, prop["pid"])
    if manual and manual.get("vorschlag") and "grenzfall" not in manual:
        grenzfall = vorschlag == OFFEN and rank == 1
    return Assessment(vorschlag, p4390, f, begruendung, grenzfall, rule_vorschlag)
