"""Pruef-Dokument im QuickStatements-Format (V1, "|" als Trenner) und Pruefung.

Das Dokument (proposals/pmdmap/quickstatements_<datum>.txt) ist Pruefung und
Batch zugleich:
  - Zeilen ohne "#" am Anfang sind AKTIV,
  - "#<QS-Zeile>" ist ein auskommentierter Vorschlag - "#" loeschen aktiviert ihn,
  - "##..." ist Erlaeuterung.

Nach der Durchsicht wird die GANZE Datei in QuickStatements eingefuegt; die
#-Zeilen verwirft QuickStatements dabei (Erfahrung des Nutzers - die
Hilfeseite dokumentiert Kommentarzeilen nicht). Deshalb darf das Dokument
nichts Aktives enthalten, das nicht ausgefuehrt werden soll.

"export" ist die optionale Pruefung davor (Format, IRIs, P4390, halbe
Umstellungen, Doppelte) und schreibt auf Wunsch reine Teil-Dateien zu 50
Zeilen.

Aktiv vorbelegt ist nur, was sicher ist: neue P1709/P1628-Abbildung, bei der
Regel und Einschaetzung uebereinstimmen und kein Grenzfall vorliegt. Alles,
was eine bestehende Aussage loescht, bleibt auskommentiert.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .assessment import (
    BEHALTEN, ENTFERNEN, NEU_P1628, NEU_P1709, NEU_P2888, OFFEN, P4390_ERGAENZEN, UMSTELLEN,
    VERWERFEN, Assessment,
)
from .config import Config
from .iri import IriScheme
from .ontology import Ontology

BLOCK = 50
LEGACY_SUFFIXES = (".qs",)            # fruehere Dateiendung (bis 19.11.2026)


def doc_name(date: str) -> str:
    """Name des Pruef-Dokuments; ".txt" genuegt fuer QuickStatements."""
    return f"quickstatements_{date}.txt"
# Eine QS-Zeile im V1-Format, wie pmdmap sie schreibt: [-]Subjekt|Property|"Wert"[|Paare...]
QS_LINE = re.compile(r'^(-)?([QP]\d+)\|(P\d+)\|"([^"|]+)"((?:\|[PS]\d+\|[^|]+)*)$')


# --- Zeilen bauen --------------------------------------------------------------
def qs_date(iso_date: str) -> str:
    """'2026-11-19' -> '+2026-11-19T00:00:00Z/11' (Tagesgenauigkeit)."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso_date):
        raise ValueError(f"Datum {iso_date!r} nicht im Format JJJJ-MM-TT")
    return f"+{iso_date}T00:00:00Z/11"


def qs_add(subject: str, prop: str, iri: str, source_qid: str, retrieved: str, p4390: str = "") -> str:
    parts = [subject, prop, f'"{iri}"']
    if p4390:
        parts += ["P4390", p4390]
    parts += ["S248", source_qid, "S813", qs_date(retrieved)]
    return "|".join(parts)


def qs_remove(subject: str, prop: str, iri: str) -> str:
    return f'-{subject}|{prop}|"{iri}"'


def line_key(qs: str) -> str:
    """Schluessel fuer das Wiedererkennen beim Neuerzeugen: ohne Quellen
    (S813 aendert sich mit jedem Abruf)."""
    return qs.split("|S248|", 1)[0]


@dataclass
class ParsedLine:
    no: int
    active: bool
    text: str              # QS-Zeile ohne fuehrendes "#"
    remove: bool
    subject: str
    prop: str
    value: str
    pairs: list[tuple[str, str]]

    @property
    def qualifiers(self) -> dict[str, str]:
        return {k: v for k, v in self.pairs if k.startswith("P")}

    @property
    def sources(self) -> dict[str, str]:
        return {k: v for k, v in self.pairs if k.startswith("S")}


def parse_line(raw: str, no: int = 0) -> ParsedLine | None:
    """None fuer Erlaeuterungen ("##"), Leerzeilen und alles, was keine QS-Zeile ist."""
    s = raw.rstrip("\n").rstrip()
    if not s or s.startswith("##"):
        return None
    active = not s.startswith("#")
    body = s.lstrip("#").strip()
    m = QS_LINE.match(body)
    if not m:
        return None
    rest = m.group(5)
    tokens = rest.split("|")[1:] if rest else []
    pairs = list(zip(tokens[0::2], tokens[1::2]))
    return ParsedLine(no, active, body, bool(m.group(1)), m.group(2), m.group(3), m.group(4), pairs)


def parse_document(text: str) -> tuple[list[ParsedLine], list[str]]:
    """Alle Vorschlagszeilen; dazu aktive Zeilen, die keine gueltige QS-Zeile sind."""
    lines, junk = [], []
    for no, raw in enumerate(text.splitlines(), 1):
        p = parse_line(raw, no)
        if p:
            lines.append(p)
            continue
        s = raw.strip()
        if s and not s.startswith("#"):
            junk.append(f"Zeile {no}: aktiv, aber keine gültige QS-Zeile: {s[:80]}")
    return lines, junk


# --- Dokument erzeugen -----------------------------------------------------------
@dataclass
class DocWriter:
    cfg: Config
    retrieved: str
    previous: dict[str, tuple[bool, str]] = field(default_factory=dict)   # line_key -> (aktiv, Zeile)
    lines: list[str] = field(default_factory=list)
    used_keys: set[str] = field(default_factory=set)
    n_active: int = 0
    n_commented: int = 0

    def note(self, text: str = "") -> None:
        for part in str(text).splitlines() or [""]:
            self.lines.append(f"## {part}".rstrip())

    def qs(self, qs: str, active: bool) -> None:
        key = line_key(qs)
        if key in self.previous:          # Stand aus der vorigen Fassung gewinnt
            active = self.previous[key][0]
        self.used_keys.add(key)
        self.lines.append(qs if active else f"#{qs}")
        if active:
            self.n_active += 1
        else:
            self.n_commented += 1

    def add(self, subject: str, prop: str, iri: str, active: bool, p4390: str = "") -> None:
        self.qs(qs_add(subject, prop, iri, self.cfg.profile.source_qid, self.retrieved, p4390), active)

    def remove(self, subject: str, prop: str, iri: str) -> None:
        self.qs(qs_remove(subject, prop, iri), False)     # Loeschen nie vorbelegt

    def section(self, title: str) -> None:
        self.lines += ["", "## " + "=" * 74, f"## {title}", "## " + "=" * 74]


def _short(text: str, n: int = 240) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _local(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def previous_state(path: Path) -> dict[str, tuple[bool, str]]:
    """line_key -> (aktiv, ganze Zeile) aus einer vorhandenen Fassung."""
    if not path.exists():
        return {}
    lines, _ = parse_document(path.read_text(encoding="utf-8"))
    return {line_key(p.text): (p.active, p.text) for p in lines}


def build_document(cfg: Config, onto: Ontology, snap: dict, assessed0: list, cands: dict | None,
                   assessed12: list, previous: dict[str, tuple[bool, str]]) -> tuple[str, dict]:
    short = cfg.profile.short_name
    version = snap["ontology"]["version"]
    retrieved = snap["ontology"]["retrieved"]
    labels = {**snap["labels"], **((cands or {}).get("labels", {}))}
    lab = lambda q: labels.get(q, {}).get("en", q)              # noqa: E731
    p4 = lambda q: f"{lab(q)} ({q})" if q else ""               # noqa: E731
    w = DocWriter(cfg, retrieved, previous)

    # --- Kopf -----------------------------------------------------------------
    w.note(f"pmdmap – Prüfung und QuickStatements · {short} {version} · Wikidata {snap['retrieved']}")
    w.note()
    w.note("SO GEHT'S")
    w.note("  - Zeilen OHNE \"#\" am Anfang sind aktiv, alle #-Zeilen verwirft QuickStatements.")
    w.note("  - Vorschlag annehmen: das \"#\" am Zeilenanfang löschen. Ablehnen: \"#\" davorsetzen.")
    w.note("  - Umstellen = Löschzeile (-Q…) + neue Zeile: immer BEIDE aktivieren.")
    w.note("  - P4390-Wert in einer Zeile ändern: die QID nach \"P4390|\" ersetzen.")
    w.note("  - Danach die GANZE Datei in QuickStatements einfügen (V1-Format).")
    doc_rel = cfg.output_dir / doc_name(snap["retrieved"])
    doc_rel = doc_rel.relative_to(cfg.root) if doc_rel.is_relative_to(cfg.root) else doc_rel
    w.note(f"  - Optional vorher prüfen:  python -m pmdmap export --review {doc_rel} --nur-pruefen")
    w.note("    (Format, IRIs, P4390, halbe Umstellungen, doppelte Zeilen; ohne --nur-pruefen")
    w.note("    zusätzlich Teil-Dateien qs_*_partNN.txt à 50 Zeilen)")
    w.note("  - Ein neues \"pmdmap review\" behält, was hier aktiviert oder auskommentiert wurde.")
    w.note()
    w.note("AKTIV VORBELEGT ist nur Sicheres: neue P1709/P1628, bei der Regel und Einschätzung")
    w.note("übereinstimmen, ohne Grenzfall. Alles andere – und jede Löschung – ist auskommentiert.")
    w.note()
    w.note("P4390-Werte laut Constraint: " + ", ".join(f"{lab(q)} = {q}" for q in snap["mapping_relation_allowed"][:5]))
    w.note(f"  (\"narrow match\": {short}-Klasse ENGER als der Eintrag, \"broad match\": WEITER)")
    w.note(f"Quelle jeder neuen Aussage: S248 = {cfg.profile.source_qid} ({cfg.profile.name}), S813 = {retrieved}")
    w.note("Hinweis Help:QuickStatements: \"_\" in Zeichenketten kann das Werkzeug verwirren – die PMD-IRIs")
    w.note("enthalten \"_\". Vor dem Ausführen die Vorschau in QuickStatements prüfen.")

    stats: dict = {"blocks": Counter()}

    # --- Pakete 1/2 -------------------------------------------------------------
    by_class: dict[str, list] = defaultdict(list)
    for pilot, eid, a in assessed12:
        by_class[pilot["iri"]].append((pilot, eid, a))
    if cands:
        for paket, title in (("1", "PAKET 1 – Pilot-Werkstoffe: neue Abbildungen"),
                             ("2", "PAKET 2 – Pilot-Eigenschaften (E7): Begriffs-Eintrag + Wikidata-Eigenschaft")):
            entries = [e for e in cands["classes"].values() if e["pilot"]["paket"] == paket]
            if not entries:
                continue
            w.section(title)
            for e in entries:
                pilot = e["pilot"]
                iri = pilot["iri"]
                cls = onto.get(iri)
                w.lines.append("")
                w.note(f"[P{paket}] {pilot['label']} ({_local(iri)}) – {pilot['reason']}")
                w.note(f"  {short}: {_short(cls.definition('en'))}")
                if pilot.get("hint"):
                    w.note(f"  Hinweis: {pilot['hint']}")
                if pilot["linked"]:
                    w.note("  bereits abgebildet (Paket 0): " + ", ".join(pilot["linked"]))
                rows = by_class.get(iri, [])
                if not rows and not pilot["linked"]:
                    w.note("  keine Kandidaten gefunden")
                for _, eid, a in rows:
                    _candidate_block(w, cands, iri, eid, a, p4)
                    stats["blocks"][a.vorschlag] += 1
        missing = [m for ms in cands.get("missing", {}).values() for m in ms]
        if missing:
            w.lines.append("")
            w.note(f"Nicht in {short} {version} (keine Abbildung möglich): " + ", ".join(missing))

    # --- Paket 0 ------------------------------------------------------------------
    changes = [(m, a) for m, a in assessed0 if a.vorschlag != BEHALTEN]
    keep = [(m, a) for m, a in assessed0 if a.vorschlag == BEHALTEN]
    w.section(f"PAKET 0 – Bestand ändern ({len(changes)}) – alles auskommentiert")
    for m, a in changes:
        _paket0_block(w, snap, onto, m, a, p4, cfg)
        stats["blocks"][a.vorschlag] += 1
    w.section(f"PAKET 0 – Bestand behalten ({len(keep)}) – keine Änderung; Alternative auskommentiert")
    w.note("Wer eine dieser Abbildungen doch umstellen will: beide Zeilen aktivieren und P4390 prüfen")
    w.note("(vorbelegt ist close match als Platzhalter).")
    for m, a in keep:
        _paket0_block(w, snap, onto, m, a, p4, cfg)
        stats["blocks"][a.vorschlag] += 1

    # --- nur Info ---------------------------------------------------------------
    conflicts = snap["e1"]["conflicts"]
    if conflicts:
        w.section("NUR INFO – E1: Fremdontologie-Konstrukt als Oberklasse eines Werkstoffs (kein Entwurf)")
        for c in conflicts:
            w.note(f"{c['child_label']} ({c['child']}) → P279 → {c.get('parent_label') or c['parent']} "
                   f"({c['parent']}; {c['why_candidate']}) – siehe review-needed.md")

    # Aktive Zeilen der vorigen Fassung, die nicht mehr vorgeschlagen werden
    orphans = [text for k, (active, text) in previous.items() if active and k not in w.used_keys]
    if orphans:
        # auskommentiert: die Datei wird als Ganzes eingefuegt - nichts soll
        # unbemerkt mitlaufen, was der Lauf nicht mehr vorschlaegt
        w.section("AUS DER VORIGEN FASSUNG – war aktiv, wird nicht mehr vorgeschlagen (auskommentiert)")
        w.note("Diese Zeilen waren aktiv; der neue Lauf schlägt sie nicht mehr vor. Wieder aktivieren nur nach Prüfung.")
        for text in orphans:
            w.lines.append(f"#{text}")
            w.n_commented += 1
    stats.update(active=w.n_active, commented=w.n_commented, orphans=len(orphans))
    return "\n".join(w.lines) + "\n", stats


def _candidate_block(w: DocWriter, cands: dict, iri: str, eid: str, a: Assessment, p4) -> None:
    s = cands["entities"].get(eid, {})
    name = f"{s.get('label_de') or '–'} / {s.get('label_en') or '–'}"
    desc = s.get("desc_de") or s.get("desc_en") or ""
    kind = "Eigenschaft" if eid.startswith("P") else "Eintrag"
    if a.vorschlag == VERWERFEN:            # eine Zeile genuegt
        why = a.begruendung.split(" | Einschätzung: ", 1)
        why = why[1] if len(why) > 1 else why[0].removeprefix("Regel: ")
        w.note(f"  verworfen: {kind} {eid} {name} – {_short(why, 160)}")
        return
    w.lines.append("")
    w.note(f"  {kind} {eid}: {name} – {_short(desc, 140)}")
    w.note(f"  Vorschlag: {a.vorschlag}{(' · ' + p4(a.vorschlag_p4390)) if a.vorschlag_p4390 else ''}"
           f"{' · GRENZFALL' if a.grenzfall else ''}")
    w.note(f"  {_short(a.begruendung, 600)}")
    safe = a.vorschlag in (NEU_P1709, NEU_P1628) and a.vorschlag == a.rule_vorschlag and not a.grenzfall
    natural = "P1628" if eid.startswith("P") else "P1709"
    if a.vorschlag in (NEU_P1709, NEU_P1628):
        w.add(eid, natural, iri, safe)
    elif a.vorschlag == NEU_P2888:
        w.add(eid, "P2888", iri, False, a.vorschlag_p4390)
    elif a.vorschlag == OFFEN:
        w.note("  offen – Alternativen:")
        w.add(eid, natural, iri, False)
        if a.vorschlag_p4390:
            w.add(eid, "P2888", iri, False, a.vorschlag_p4390)
    elif a.vorschlag == BEHALTEN:
        w.note("  schon vorhanden – keine Zeile")


def _paket0_block(w: DocWriter, snap: dict, onto: Ontology, m: dict, a: Assessment, p4, cfg: Config) -> None:
    ent = snap["entities"].get(m["entity"], {})
    qid, prop, iri = m["entity"], m["prop"], m["value"]
    cls = onto.get(iri)
    w.lines.append("")
    w.note(f"[P0] {ent.get('label_de') or '–'} / {ent.get('label_en') or '–'} ({qid}) ↔ "
           f"{cls.label() if cls else '?'} ({_local(iri)}) · aktuell {prop}"
           f"{(' + ' + ', '.join(p4(q) for q in m['p4390'])) if m['p4390'] else ''}"
           f" · {m['references']} Quelle(n)")
    if ent.get("desc_de") or ent.get("desc_en"):
        w.note(f"  WD: {_short(ent.get('desc_de') or ent.get('desc_en'), 160)}")
    if cls:
        w.note(f"  {cfg.profile.short_name}: {_short(cls.definition('en'), 200)}")
    w.note(f"  Vorschlag: {a.vorschlag}{(' · ' + p4(a.vorschlag_p4390)) if a.vorschlag_p4390 else ''}"
           f"{' · GRENZFALL' if a.grenzfall else ''}")
    w.note(f"  {_short(a.begruendung, 600)}")
    warn_refs = (lambda: w.note(f"  Achtung: die bestehende Aussage hat {m['references']} Quelle(n) – "
                                "sie gehen mit dem Löschen verloren.")) if m["references"] else (lambda: None)
    close = next((q for q in snap["mapping_relation_allowed"]
                  if snap["labels"].get(q, {}).get("en") == "close match"), "")
    if a.vorschlag in (UMSTELLEN, OFFEN) and (a.vorschlag_p4390 or a.vorschlag == UMSTELLEN):
        if not a.vorschlag_p4390:
            w.note("  P4390 noch offen – Platzhalter close match, vor dem Aktivieren prüfen")
        warn_refs()
        w.remove(qid, prop, iri)
        w.add(qid, "P2888", iri, False, a.vorschlag_p4390 or close)
    elif a.vorschlag == OFFEN and not (cls and not cls.deprecated):
        warn_refs()
        w.note("  IRI unbekannt/veraltet – Löschen als Option:")
        w.remove(qid, prop, iri)
    elif a.vorschlag == OFFEN:
        w.note("  offen – nichts tun heißt: bleibt wie es ist. Alternative (P4390 Platzhalter close match):")
        warn_refs()
        w.remove(qid, prop, iri)
        w.add(qid, "P2888", iri, False, close)
    elif a.vorschlag == P4390_ERGAENZEN:
        w.note("  P4390 an der bestehenden Aussage ergänzen (Platzhalter close match):")
        w.add(qid, "P2888", iri, False, a.vorschlag_p4390 or close)
    elif a.vorschlag == ENTFERNEN:
        warn_refs()
        w.remove(qid, prop, iri)
    elif a.vorschlag == BEHALTEN and prop == "P1709":
        w.remove(qid, prop, iri)
        w.add(qid, "P2888", iri, False, close)


# --- Export ---------------------------------------------------------------------
@dataclass
class ExportResult:
    files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)


def existing_statements(snap: dict, cands: dict | None) -> dict[tuple[str, str, str], int]:
    """(Subjekt, Property, Wert) -> Zahl der Referenzen, soweit bekannt."""
    out = {(m["entity"], m["prop"], m["value"]): m["references"] for m in snap["mappings"]}
    for e in (cands or {}).get("classes", {}).values():
        for c in e["candidates"]:
            for link in c.get("onto_links", []):
                pid, value = link.split(":", 1)
                out.setdefault((c["qid"], pid, value), -1)
        for p in e["properties"]:
            for v in p["p1628"]:
                out.setdefault((p["pid"], "P1628", v), -1)
    return out


def validate(lines: list[ParsedLine], cfg: Config, onto: Ontology, snap: dict, cands: dict | None) -> ExportResult:
    r = ExportResult()
    scheme = IriScheme.from_profile(cfg.profile)
    allowed = set(snap["mapping_relation_allowed"])
    existing = existing_statements(snap, cands)
    active = [p for p in lines if p.active]
    removals = {(p.subject, p.prop, p.value) for p in active if p.remove}
    where = lambda p: f"Zeile {p.no} ({p.subject} {p.prop} {_local(p.value)})"  # noqa: E731

    seen = Counter((p.remove, p.subject, p.prop, p.value) for p in active)
    for (rm, s, pr, v), n in seen.items():
        if n > 1:
            r.errors.append(f"{'Löschung' if rm else 'Aussage'} {s} {pr} {_local(v)} ist {n}× aktiv")

    for p in active:
        if p.remove:
            if p.pairs:
                r.errors.append(f"{where(p)}: Löschzeile mit Qualifiern/Quellen – nur -Subjekt|Property|\"Wert\"")
            refs = existing.get((p.subject, p.prop, p.value))
            if refs is None:
                r.warnings.append(f"{where(p)}: zu löschende Aussage ist im Abruf nicht bekannt (schon entfernt?)")
            elif refs > 0:
                r.warnings.append(f"{where(p)}: Löschung entfernt eine Aussage mit {refs} Quelle(n)")
            continue
        if p.prop not in ("P1709", "P2888", "P1628"):
            r.errors.append(f"{where(p)}: Property {p.prop} wird von pmdmap nicht neu gesetzt")
            continue
        if not scheme.is_class_iri(p.value):
            r.errors.append(f"{where(p)}: keine {cfg.profile.short_name}-Klassen-IRI ({scheme.problem(p.value)})")
            continue
        cls = onto.get(p.value)
        if cls is None or cls.deprecated:
            r.errors.append(f"{where(p)}: Klasse {'fehlt in' if cls is None else 'veraltet in'} "
                            f"{cfg.profile.short_name} {onto.meta.version}")
        if p.prop == "P1709" and p.subject.startswith("P"):
            r.errors.append(f"{where(p)}: P1709 gehört an einen Eintrag; für Eigenschaften P1628 (E7)")
        if p.prop == "P1628" and p.subject.startswith("Q"):
            r.errors.append(f"{where(p)}: P1628 gehört an eine Wikidata-Eigenschaft (E7)")
        q = p.qualifiers
        if p.prop == "P2888":
            if "P4390" not in q:
                r.errors.append(f"{where(p)}: P2888 ohne P4390 (E3)")
            elif q["P4390"] not in allowed:
                r.errors.append(f"{where(p)}: P4390 {q['P4390']} laut Constraint nicht erlaubt")
        elif "P4390" in q:
            r.errors.append(f"{where(p)}: {p.prop} ohne P4390 (Präzisierung E3/E4)")
        src = p.sources
        if src.get("S248") != cfg.profile.source_qid or "S813" not in src:
            r.errors.append(f"{where(p)}: Quelle fehlt (S248 {cfg.profile.source_qid} und S813)")
        elif not re.fullmatch(r"\+\d{4}-\d{2}-\d{2}T00:00:00Z/11", src["S813"]):
            r.errors.append(f"{where(p)}: S813 nicht im Format +JJJJ-MM-TTT00:00:00Z/11")
        key = (p.subject, p.prop, p.value)
        if key in existing and key not in removals:
            if p.prop == "P2888" and "P4390" in q:
                r.warnings.append(f"{where(p)}: Aussage existiert – QuickStatements ergänzt P4390 und Quelle an ihr")
            else:
                r.warnings.append(f"{where(p)}: Aussage existiert schon – QuickStatements legt sie nicht doppelt an")

    # P1709 hoechstens einmal je Eintrag und je Klasse (inkl. Bestand, der bleibt)
    p1709 = {(s, v) for (s, pr, v) in existing if pr == "P1709" and (s, pr, v) not in removals}
    p1709 |= {(p.subject, p.value) for p in active if not p.remove and p.prop == "P1709"}
    for s, n in Counter(s for s, _ in p1709).items():
        if n > 1:
            r.warnings.append(f"{s} hätte {n}× P1709 auf {cfg.profile.short_name}-Klassen – höchstens eine kann äquivalent sein")
    for v, n in Counter(v for _, v in p1709).items():
        if n > 1:
            subj = sorted(s for s, vv in p1709 if vv == v)
            r.warnings.append(f"{_local(v)} hätte P1709 an {', '.join(subj)} – zwei Einträge wären damit äquivalent")
    # Umstellen nur vollstaendig
    adds = {(p.subject, p.value) for p in active if not p.remove}
    for s, pr, v in removals:
        if pr in ("P1709", "P3950") and (s, v) not in adds:
            r.warnings.append(f"{s}: Löschung {pr} {_local(v)} ohne neue Zeile – die Abbildung entfällt ganz")
    return r


def _units(lines: list[ParsedLine]) -> dict[str, list[list[str]]]:
    """Aktive Zeilen in Ausgabe-Einheiten; eine Umstellung (Loeschen + Neu)
    bleibt zusammen und wird nie auf zwei Bloecke verteilt."""
    active = [p for p in lines if p.active]
    adds = {(p.subject, p.value): p for p in active if not p.remove}
    used: set[int] = set()
    out: dict[str, list[list[str]]] = defaultdict(list)
    for p in active:
        if not p.remove:
            continue
        partner = adds.get((p.subject, p.value))
        if partner and p.prop in ("P1709", "P3950", "P2888"):
            target = "eigenschaften" if p.subject.startswith("P") else "umstellen"
            out[target].append([p.text, partner.text])
            used |= {p.no, partner.no}
        else:
            out["entfernen"].append([p.text])
            used.add(p.no)
    for p in active:
        if p.no in used or p.remove:
            continue
        out["eigenschaften" if p.subject.startswith("P") else "neu"].append([p.text])
    return out


def chunk(units: list[list[str]], size: int = BLOCK) -> list[list[str]]:
    parts, cur = [], []
    for u in units:
        if cur and len(cur) + len(u) > size:
            parts.append(cur)
            cur = []
        cur += u
    if cur:
        parts.append(cur)
    return parts


def write_export(lines: list[ParsedLine], out_dir: Path, retrieved: str, short: str) -> list[Path]:
    """Reine QuickStatements schreiben (keine Kommentar-, keine Leerzeilen)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix in (".txt", *LEGACY_SUFFIXES):        # alte Teile dieses Werkzeugs
        for old in out_dir.glob(f"qs_*_part[0-9][0-9]{suffix}"):
            old.unlink()
    files = []
    units = _units(lines)
    for name in ("neu", "umstellen", "entfernen", "eigenschaften"):
        for i, part in enumerate(chunk(units.get(name, [])), 1):
            p = out_dir / f"qs_{name}_part{i:02d}.txt"
            p.write_text("\n".join(part) + "\n", encoding="utf-8")
            files.append(p)
    # P1628 & Co. an Eigenschaften zusaetzlich als Liste zur Handeingabe
    props = [u for u in units.get("eigenschaften", [])]
    md = out_dir / "manuell_eigenschaften.md"
    L = [f"# Aussagen an Wikidata-Eigenschaften ({short}) – {retrieved}", "",
         "QuickStatements unterstützt Eigenschaften als Subjekt (Help:QuickStatements: "
         "„An entity can be an item, a property, …“); dieselben Zeilen stehen in "
         "`qs_eigenschaften_part*.txt` bzw. im Prüf-Dokument. Diese Liste ist für die Eingabe von Hand.", ""]
    for u in props:
        for t in u:
            p = parse_line(t)
            act = "entfernen" if p.remove else "hinzufügen"
            q = p.qualifiers
            L.append(f"- [ ] https://www.wikidata.org/wiki/Property:{p.subject} – {act} **{p.prop}** = `{p.value}`"
                     + (f", P4390 = {q['P4390']}" if "P4390" in q else "")
                     + (f"; Quelle S248 = {p.sources.get('S248')}, S813 = {p.sources.get('S813')}" if not p.remove else ""))
    if not props:
        L.append("- keine")
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    files.append(md)
    return files
