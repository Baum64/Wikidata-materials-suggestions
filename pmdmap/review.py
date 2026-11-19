"""Pruef-Tabelle: schreiben (aus dem Bestand) und zuruecklesen (fuer den Export).

Format: CSV, UTF-8 (mit BOM, damit Excel Umlaute richtig zeigt), Semikolon.
Eine Zeile pro Abbildung. Die Spalten entscheidung / entscheidung_p4390 /
bemerkung fuellt der Mensch; alles andere ist Belegmaterial.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .assessment import (
    Assessor, assess_candidate, assess_property, load_candidate_assessments,
)
from .iri import IriScheme
from .ontology import Ontology

COLUMNS = [
    "paket", "kandidat_rang", "qid", "wd_typ", "wd_label_de", "wd_label_en", "wd_beschreibung",
    "wd_p31", "wd_p279", "wd_sitelinks",
    "pmd_iri", "pmd_label", "pmd_definition", "pmd_kategorie",
    "aktuell", "aktuell_p4390", "aktuell_referenzen", "statement_id",
    "vorschlag", "vorschlag_p4390", "befunde", "begruendung",
    "entscheidung", "entscheidung_p4390", "bemerkung",
    "abgerufen", "ontologie_version",
]
HUMAN_COLUMNS = ("entscheidung", "entscheidung_p4390", "bemerkung")
REQUIRED_ON_READ = ("paket", "qid", "pmd_iri", "aktuell", "aktuell_p4390",
                    "aktuell_referenzen", "entscheidung", "entscheidung_p4390", "abgerufen")

# zulaessige Entscheidungen (Schreibweise beim Einlesen tolerant)
DECISIONS = {
    "p1709": "P1709",
    "p2888": "P2888",
    "p1628": "P1628",
    "entfernen": "entfernen",
    "überspringen": "überspringen",
    "ueberspringen": "überspringen",
}
SEP = " | "
_QID = re.compile(r"\b(Q\d+)\b")
_ENTITY = re.compile(r"^[QP]\d+$")

_CATEGORY_ORDER = {"werkstoff": 0, "eigenschaft": 1}


# --- Schreiben --------------------------------------------------------------
def _with_labels(ids: list[str], labels: dict) -> str:
    out = []
    for q in ids:
        lab = labels.get(q, {})
        name = lab.get("de") or lab.get("en")
        out.append(f"{name} ({q})" if name else q)
    return SEP.join(out)


def format_p4390(qid: str, labels: dict) -> str:
    if not qid:
        return ""
    name = labels.get(qid, {}).get("en")
    return f"{name} ({qid})" if name else qid


def build_paket0_rows(snap: dict, onto: Ontology, assessor: Assessor) -> tuple[list[dict], list]:
    """Zeilen fuer Paket 0 und die Bewertungen (fuer Bericht/review-needed)."""
    labels = snap["labels"]
    rows, assessed = [], []
    for m in snap["mappings"]:
        ent = snap["entities"].get(m["entity"], {})
        cls = onto.get(m["value"])
        a = assessor.assess(m)
        assessed.append((m, a))
        desc = SEP.join(x for x in (
            f"de: {ent['desc_de']}" if ent.get("desc_de") else "",
            f"en: {ent['desc_en']}" if ent.get("desc_en") else "",
        ) if x)
        pmd_label = ""
        if cls:
            pmd_label = cls.labels.get("en", "")
            if cls.labels.get("de"):
                pmd_label += f" / {cls.labels['de']}"
        rows.append({
            "paket": "0",
            "kandidat_rang": "",
            "qid": m["entity"],
            "wd_typ": "Eigenschaft" if m["entity"].startswith("P") else "Eintrag",
            "wd_label_de": ent.get("label_de", ""),
            "wd_label_en": ent.get("label_en", ""),
            "wd_beschreibung": desc,
            "wd_p31": _with_labels(ent.get("p31", []), labels),
            "wd_p279": _with_labels(ent.get("p279", []), labels),
            "wd_sitelinks": str(ent.get("sitelinks", "")),
            "pmd_iri": m["value"],
            "pmd_label": pmd_label,
            "pmd_definition": cls.definition("en") if cls else "",
            "pmd_kategorie": m.get("category", ""),
            "aktuell": m["prop"],
            "aktuell_p4390": SEP.join(format_p4390(q, labels) for q in m["p4390"]),
            "aktuell_referenzen": str(m["references"]),
            "statement_id": m["statement_id"],
            "vorschlag": a.vorschlag,
            "vorschlag_p4390": format_p4390(a.vorschlag_p4390, labels),
            "befunde": ", ".join(a.codes),
            "begruendung": a.begruendung,
            "entscheidung": "",
            "entscheidung_p4390": "",
            "bemerkung": "",
            "abgerufen": snap["retrieved"],
            "ontologie_version": snap["ontology"]["version"],
        })
    order = sorted(
        range(len(rows)),
        key=lambda i: (
            _CATEGORY_ORDER.get(rows[i]["pmd_kategorie"], 2), rows[i]["pmd_kategorie"],
            (rows[i]["wd_label_de"] or rows[i]["wd_label_en"]).lower(),
        ),
    )
    return [rows[i] for i in order], [assessed[i] for i in order]


def row_key(row: dict) -> tuple[str, str, str]:
    """Eine Abbildung = Paket + Wikidata-ID + Ontologie-IRI."""
    return (str(row.get("paket", "")), str(row.get("qid", "")), str(row.get("pmd_iri", "")))


def merge_rows(existing: list[dict], new: list[dict], pakete: set[str]) -> tuple[list[dict], list[str]]:
    """Neue Zeilen der Pakete `pakete` einsetzen, alles andere behalten.

    - Zeilen anderer Pakete bleiben unveraendert stehen.
    - Handspalten (entscheidung, entscheidung_p4390, bemerkung) werden per
      row_key in die neuen Zeilen uebernommen.
    - Eine Zeile mit ausgefuellter Entscheidung, die im neuen Lauf fehlt,
      wird NICHT verworfen, sondern behalten und gemeldet.
    """
    hand = {row_key(r): {c: r.get(c, "") for c in HUMAN_COLUMNS} for r in existing}
    new_keys = {row_key(r) for r in new}
    notes: list[str] = []
    merged_new = []
    for r in new:
        r = dict(r)
        for c, v in hand.get(row_key(r), {}).items():
            if v:
                r[c] = v
        merged_new.append(r)
    kept = []
    for r in existing:
        if str(r.get("paket", "")) not in pakete:
            kept.append(r)
        elif row_key(r) not in new_keys and any(r.get(c) for c in HUMAN_COLUMNS):
            kept.append(r)
            notes.append(f"Zeile {r.get('qid')} ↔ {r.get('pmd_iri')} (Paket {r.get('paket')}) fehlt im neuen Lauf, "
                         "hat aber eine Entscheidung - behalten")
    order = {"0": 0, "1": 1, "2": 2}
    out = sorted(kept + merged_new, key=lambda r: order.get(str(r.get("paket", "")), 9))
    # stabile Reihenfolge innerhalb der Pakete: neue Zeilen in Erzeugungsreihenfolge
    return out, notes


def write_review(rows: list[dict], path: Path, pakete: set[str] | None = None) -> tuple[Path, list[str]]:
    """Schreiben; existiert die Datei, wird zusammengefuehrt (merge_rows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    if path.exists():
        old = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
        pakete = pakete if pakete is not None else {str(r.get("paket", "")) for r in rows}
        rows, notes = merge_rows(old.to_dict(orient="records"), rows, pakete)
    df = pd.DataFrame(rows, columns=COLUMNS).fillna("")
    df.to_csv(path, sep=";", index=False, encoding="utf-8-sig")
    return path, notes


# --- Zuruecklesen -----------------------------------------------------------
@dataclass
class Decision:
    line: int                 # Zeilennummer in der Datei (Kopfzeile = 1)
    row: dict
    decision: str             # "" = noch offen
    p4390: str = ""           # QID


@dataclass
class ReviewFile:
    decisions: list[Decision] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def open(self) -> list[Decision]:
        return [d for d in self.decisions if not d.decision]


def _resolve_p4390(value: str, allowed: dict[str, str] | None) -> tuple[str, str | None]:
    """'close match', 'Q39893184' oder 'close match (Q39893184)' -> QID."""
    value = value.strip()
    if not value:
        return "", None
    m = _QID.search(value)
    if m:
        qid = m.group(1)
        if allowed is not None and qid not in allowed.values():
            return qid, f"P4390-Wert {qid} ist laut Constraint nicht erlaubt"
        return qid, None
    if allowed is not None:
        qid = allowed.get(value.lower())
        if qid:
            return qid, None
        return "", f"P4390-Wert „{value}“ unbekannt (erlaubt: {', '.join(sorted(allowed))})"
    return "", f"P4390-Wert „{value}“ ohne QID und ohne Liste erlaubter Werte nicht auflösbar"


def read_review(path: Path, scheme: IriScheme | None = None,
                allowed_p4390: dict[str, str] | None = None) -> ReviewFile:
    """Pruef-Tabelle einlesen und pruefen.

    allowed_p4390: {englisches Label (klein): QID} aus dem Constraint;
    None = nicht gegen den Constraint pruefen.
    """
    out = ReviewFile()
    df = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in REQUIRED_ON_READ if c not in df.columns]
    if missing:
        out.errors.append(f"Spalten fehlen: {', '.join(missing)}")
        return out
    for i, row in enumerate(df.to_dict(orient="records")):
        line = i + 2
        where = f"Zeile {line} ({row.get('qid', '?')})"
        raw = row["entscheidung"].strip()
        decision = DECISIONS.get(raw.lower(), None) if raw else ""
        if decision is None:
            out.errors.append(f"{where}: Entscheidung „{raw}“ unbekannt (erlaubt: P1709, P2888, P1628, entfernen, überspringen)")
            continue
        if not decision:                         # noch offen - nichts zu pruefen
            out.decisions.append(Decision(line, row, ""))
            continue
        qid = row["qid"].strip()
        if not _ENTITY.match(qid):
            out.errors.append(f"{where}: qid „{row['qid']}“ ist keine Wikidata-ID")
            continue
        if decision == "P1628" and not qid.startswith("P"):
            out.errors.append(f"{where}: P1628 gehört an eine Wikidata-Eigenschaft (P…), nicht an {qid} (E7)")
            continue
        if decision == "P1709" and qid.startswith("P"):
            out.errors.append(f"{where}: P1709 gehört an einen Eintrag (Q…); für Eigenschaften P1628 (E7)")
            continue
        if scheme is not None and decision in ("P1709", "P2888") and not scheme.is_class_iri(row["pmd_iri"]):
            out.errors.append(f"{where}: pmd_iri „{row['pmd_iri']}“ ist keine Klassen-IRI ({scheme.problem(row['pmd_iri'])})")
            continue
        p4390, problem = _resolve_p4390(row["entscheidung_p4390"], allowed_p4390)
        if problem:
            out.errors.append(f"{where}: {problem}")
            continue
        if decision == "P2888" and not p4390:
            out.errors.append(f"{where}: P2888 braucht entscheidung_p4390 (E3)")
            continue
        if decision in ("P1709", "P1628") and p4390:
            out.errors.append(f"{where}: {decision} ohne P4390 (Präzisierung E3/E4) - entscheidung_p4390 leeren oder P2888 wählen")
            continue
        if decision in ("entfernen", "überspringen") and p4390:
            out.warnings.append(f"{where}: entscheidung_p4390 wird bei „{decision}“ ignoriert")
            p4390 = ""
        out.decisions.append(Decision(line, row, decision, p4390))
    return out


# --- Pakete 1/2 ---------------------------------------------------------------
def p4390_lookup(snap: dict):
    """Label (en, klein) -> QID der laut Constraint erlaubten P4390-Werte."""
    table = {snap["labels"].get(q, {}).get("en", "").lower(): q for q in snap["mapping_relation_allowed"]}
    return lambda name: table.get(str(name).lower(), "")


def build_candidate_rows(cfg, onto: Ontology, snap: dict, cands: dict) -> tuple[list[dict], list]:
    """Zeilen fuer Pakete 1/2 aus dem Kandidaten-Ergebnis (candidates.collect)."""
    manual_all = load_candidate_assessments(cfg.profile.candidate_assessments_file)
    lookup = p4390_lookup(snap)
    labels = {**snap["labels"], **cands["labels"]}
    rows, assessed = [], []

    def base(pilot: dict, eid: str, s: dict, typ: str, rank: int) -> dict:
        cls = onto.get(pilot["iri"])
        pmd_label = cls.labels.get("en", "") + (f" / {cls.labels['de']}" if cls.labels.get("de") else "")
        desc = SEP.join(x for x in (
            f"de: {s['desc_de']}" if s.get("desc_de") else "",
            f"en: {s['desc_en']}" if s.get("desc_en") else "",
        ) if x)
        return {
            "paket": pilot["paket"], "kandidat_rang": str(rank), "qid": eid, "wd_typ": typ,
            "wd_label_de": s.get("label_de", ""), "wd_label_en": s.get("label_en", ""), "wd_beschreibung": desc,
            "wd_p31": _with_labels(s.get("p31", []), labels), "wd_p279": _with_labels(s.get("p279", []), labels),
            "wd_sitelinks": str(s.get("sitelinks", "")),
            "pmd_iri": pilot["iri"], "pmd_label": pmd_label, "pmd_definition": cls.definition("en"),
            "pmd_kategorie": onto.category(pilot["iri"]),
            "aktuell": "", "aktuell_p4390": "", "aktuell_referenzen": "", "statement_id": "",
            "entscheidung": "", "entscheidung_p4390": "", "bemerkung": "",
            "abgerufen": snap["ontology"]["retrieved"], "ontologie_version": snap["ontology"]["version"],
        }

    for iri, entry in cands["classes"].items():
        pilot = entry["pilot"]
        manual = manual_all.get(iri.rsplit("/", 1)[-1], {})
        for rank, c in enumerate(entry["candidates"], 1):
            a = assess_candidate(cfg, onto, pilot, c, rank, lookup, manual.get(c["qid"]))
            r = base(pilot, c["qid"], cands["entities"][c["qid"]], "Eintrag", rank)
            r.update({"vorschlag": a.vorschlag, "vorschlag_p4390": format_p4390(a.vorschlag_p4390, labels),
                      "befunde": ", ".join(a.codes), "begruendung": a.begruendung})
            rows.append(r)
            assessed.append((pilot, c["qid"], a))
        for rank, p in enumerate(entry["properties"], 1):
            a = assess_property(cfg, pilot, p, rank, lookup, manual.get(p["pid"]))
            r = base(pilot, p["pid"], p["summary"], f"Eigenschaft ({p['datatype']})", rank)
            r.update({"aktuell": "P1628" if pilot["iri"] in p["p1628"] else "",
                      "vorschlag": a.vorschlag, "vorschlag_p4390": format_p4390(a.vorschlag_p4390, labels),
                      "befunde": ", ".join(a.codes), "begruendung": a.begruendung})
            rows.append(r)
            assessed.append((pilot, p["pid"], a))
    return rows, assessed
