"""Bestandsbericht (Markdown) und Abschnitt fuer proposals/review-needed.md."""
from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from .assessment import OFFEN, Assessment
from .config import Config


def _lab(snap: dict, qid: str) -> str:
    if qid in snap["entities"]:
        e = snap["entities"][qid]
        return e.get("label_de") or e.get("label_en") or qid
    lab = snap["labels"].get(qid, {})
    return lab.get("de") or lab.get("en") or qid


def _local(iri: str) -> str:
    return iri.rstrip("/").rsplit("/", 1)[-1]


def write_inventory_report(cfg: Config, snap: dict, assessed: list[tuple[dict, Assessment]],
                           review_path: Path, path: Path) -> Path:
    o, lu = snap["ontology"], snap["link_usage"]
    short = cfg.profile.short_name
    a2_props = Counter(r["prop"] for r in snap["a2_rows"])
    claim_props = Counter(m["prop"] for m in snap["mappings"])
    with_p4390 = sum(1 for m in snap["mappings"] if m["p4390"])
    vorschlaege = Counter(a.vorschlag for _, a in assessed)
    kategorien = Counter(m.get("category") or "(nicht in Ontologie)" for m, _ in assessed)
    codes = Counter(c for _, a in assessed for c in a.codes)
    gh = o.get("github_latest", "")
    gh_note = ""
    if gh:
        gh_note = " ✓ entspricht" if gh.lstrip("v") == o["version"].lstrip("v") else " ✗ ABWEICHUNG zu"
        gh_note += f" der neuesten GitHub-Release ({gh})"

    L = [
        f"# Bestand {short} ↔ Wikidata – {snap['retrieved']}",
        "",
        f"Pruef-Tabelle: `{review_path.name}` · erzeugt {time.strftime('%Y-%m-%d %H:%M')} mit pmdmap",
        "",
        "## Quellen",
        f"- Ontologie: **{short} {o['version']}** (`{o['version_iri']}`, erstellt {o['created'] or '?'}){gh_note}",
        f"- Geladen von {o['source_url']} am {o['retrieved']}, SHA-256 `{o['sha256'][:16]}…`",
        f"- Wikidata abgerufen {snap['retrieved_at']} (Linksuche, SPARQL A2, wbgetentities)",
        "",
        "## Zählungen",
        f"- Linksuche `{lu['query']}` (https), alle Namensräume: **{lu['total']} Links** – "
        + ", ".join(f"Namensraum {ns}: {n}" for ns, n in sorted(lu["by_namespace"].items(), key=lambda x: int(x[0]))),
        f"  (Projektseiten im Namensraum 4: {', '.join(lu['pages_ns4']) or '–'})",
        f"- Einträge/Eigenschaften mit Link (Namensraum 0/120): **{len(lu['entities'])}**",
        f"- Abfrage A2: **{len(snap['a2_rows'])} Zeilen** – "
        + ", ".join(f"{p}: {n}" for p, n in sorted(a2_props.items())),
        f"- Abbildungen laut Claims (Properties {', '.join(cfg.wikidata.mapping_properties)}): **{len(snap['mappings'])}** – "
        + ", ".join(f"{p}: {n}" for p, n in sorted(claim_props.items())),
        f"- davon mit P4390: **{with_p4390}**",
    ]
    if snap["not_in_a2"]:
        L.append("- In den Claims, aber nicht in A2:")
        L += [f"  - {_lab(snap, e)} ({e}) {p} `{v}`" for e, p, v in snap["not_in_a2"]]
    if snap["not_in_claims"]:
        L.append("- In A2, aber nicht in den Claims (Cache-Versatz?):")
        L += [f"  - {e} {p} `{v}`" for e, p, v in snap["not_in_claims"]]
    if snap["other_links"]:
        L.append("- Weitere Links ohne Abbildungs-Property (nicht in der Tabelle):")
        L += [f"  - {_lab(snap, x['entity'])} ({x['entity']}) {x['prop']} `{x['value']}`" for x in snap["other_links"]]
    L += [
        "",
        f"Erlaubte Werte für {cfg.wikidata.mapping_relation_property} laut one-of-Constraint "
        f"({len(snap['mapping_relation_allowed'])}):",
        "",
    ]
    L += [f"- {snap['labels'].get(q, {}).get('en', q)} ({q})" for q in snap["mapping_relation_allowed"]]
    L += ["", "## Begriffsart der abgebildeten Klassen", "", "| Begriffsart | Anzahl |", "|---|---|"]
    L += [f"| {k} | {n} |" for k, n in kategorien.most_common()]
    L += ["", "## Vorschläge", "", "| Vorschlag | Anzahl |", "|---|---|"]
    L += [f"| {k} | {n} |" for k, n in vorschlaege.most_common()]
    L += ["", "| Befund | Anzahl |", "|---|---|"]
    L += [f"| `{k}` | {n} |" for k, n in codes.most_common()]

    grenz = [(m, a) for m, a in assessed if a.grenzfall]
    L += ["", f"## Grenzfälle ({len(grenz)}) – auch in review-needed.md", ""]
    L += [f"- {_lab(snap, m['entity'])} ({m['entity']}) ↔ `{_local(m['value'])}`: {a.vorschlag} – {', '.join(a.codes)}"
          for m, a in grenz] or ["- keine"]

    e1 = snap["e1"]
    L += ["", "## E1 – Ontologie-Konstrukte als Oberklasse von Werkstoffen", "",
          f"Geprüft: P279-Kette von {e1.get('materials_checked', '?')} Werkstoff-Klassen nach oben "
          f"({e1.get('closure_size', '?')} Klassen in der Hülle). Ausgangspunkt sind die auf {short}-Werkstoffklassen "
          f"abgebildeten Einträge und die {e1.get('children_total', '?')} direkten Unterklassen von "
          f"{len(e1['candidates'])} neu angelegten Einträgen mit {short}- oder BFO-Link. "
          f"Als Konstrukt gilt ein neu angelegter Eintrag (ab Q{cfg.e1_new_from_qid}) mit eigener Abbildung auf eine "
          "Fremdontologie oder mit einer Beschreibung wie „DOLCE class“. "
          + "".join(f"Nicht als Konstrukt gewertet: {n} etablierte Einträge mit Link auf `{s}`. "
                    for s, n in e1.get("established_skipped", {}).items()),
          ""]
    L += [f"- {c['child_label']} ({c['child']}) → P279 → **{c.get('parent_label') or _lab(snap, c['parent'])}** "
          f"({c['parent']}; {c['why_candidate']})" for c in e1["conflicts"]] or ["- keine Konflikte gefunden"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


# --- review-needed.md --------------------------------------------------------
def _markers(cfg: Config, paket: str) -> tuple[str, str]:
    tag = f"pmdmap:{cfg.profile.key}:paket{paket}"
    return f"<!-- {tag}:start -->", f"<!-- {tag}:end -->"


def update_review_needed(cfg: Config, snap: dict, assessed: list[tuple[dict, Assessment]],
                         review_path: Path) -> int:
    """Eigenen Abschnitt in review-needed.md ersetzen (oder anhaengen)."""
    short = cfg.profile.short_name
    grenz = [(m, a) for m, a in assessed if a.grenzfall]
    conflicts = snap["e1"]["conflicts"]
    n = len(grenz) + len(conflicts)
    start, end = _markers(cfg, "0")
    rel = review_path.relative_to(cfg.root) if review_path.is_relative_to(cfg.root) else review_path

    L = [start,
         f"## pmdmap Paket 0 – Lauf {snap['retrieved_at'].replace('T', ' ')} "
         f"({n} Fund(e), {short} {snap['ontology']['version']})",
         "",
         f"Offene Fragen aus der Bestandsprüfung der {short}-Links. Entschieden wird in `{rel}` "
         "(Spalten `entscheidung`, `entscheidung_p4390`); hier steht nichts, das pmdmap selbst entscheidet. "
         "Periodensystem-Regel: Die Abbildungen berühren keinen der Fälle 1–4 (sie ändern keine "
         "P31/P279/P361-Aussage).",
         "",
         f"### Abbildungsart P1709 vs. P2888+P4390 ({len(grenz)})",
         ""]
    for m, a in grenz:
        ent = snap["entities"].get(m["entity"], {})
        frage = "volle Deckung (P1709) oder nur Teil-Deckung (P2888 + welche P4390-Stufe)?"
        if "property-p3950" in a.codes:
            frage = "P3950 behalten oder auf P2888 + P4390 = narrow match vereinheitlichen?"
        elif {"iri-unbekannt", "iri-veraltet", "iri-ungueltig"} & set(a.codes):
            frage = "IRI korrigieren, ersetzen oder Abbildung entfernen?"
        elif "iri-mehrfach" in a.codes:
            frage = "welcher Eintrag ist die exakte Entsprechung, welche sind nur close/broad/narrow match?"
        texts = "; ".join(f.text for f in a.findings if f.grenzfall or f.code == "label-abweichung")
        if " | Einschätzung: " in a.begruendung:
            texts = (texts + " – " if texts else "") + "Einschätzung: " + a.begruendung.split(" | Einschätzung: ", 1)[1]
        L.append(
            f"- [ ] **{ent.get('label_de') or ent.get('label_en') or m['entity']}** "
            f"(https://www.wikidata.org/wiki/{m['entity']}) ↔ `{_local(m['value'])}` "
            f"(aktuell {m['prop']}; Vorschlag: {a.vorschlag}"
            + (f", P4390 {snap['labels'].get(a.vorschlag_p4390, {}).get('en', a.vorschlag_p4390)}" if a.vorschlag_p4390 else "")
            + f"). Frage: {frage} Befund: {texts or a.begruendung}"
        )
    if not grenz:
        L.append("- keine")
    L += ["", f"### E1 – Ontologie-Konstrukt als Oberklasse eines Werkstoffs ({len(conflicts)})", ""]
    for c in conflicts:
        L.append(
            f"- [ ] **{c['child_label']}** (https://www.wikidata.org/wiki/{c['child']}) → P279 → "
            f"{c.get('parent_label') or _lab(snap, c['parent'])} ({c['parent']}; {c['why_candidate']}). "
            "Frage: Widerspricht diese Kante E1 (Konstrukt einer Fremdontologie als Oberklasse eines Werkstoffs), "
            "und soll sie durch eine Abbildungs-Aussage ersetzt werden? Kein Entwurf – Eingriff in die "
            "Wikidata-Taxonomie, mit WikiProject Ontology/Materials abstimmen."
        )
    if not conflicts:
        L.append("- keine Konflikte gefunden")
    L.append(end)
    block = "\n".join(L)

    _replace_block(cfg, start, end, block)
    return n


def _replace_block(cfg: Config, start: str, end: str, block: str) -> None:
    """Eigenen Abschnitt in review-needed.md ersetzen oder anhaengen."""
    path = cfg.review_needed
    old = path.read_text(encoding="utf-8") if path.exists() else "# Offene Fragen ohne verbindliche Konvention\n"
    if start in old and end in old:
        head, rest = old.split(start, 1)
        _, tail = rest.split(end, 1)
        new = head + block + tail
    else:
        new = old.rstrip("\n") + "\n\n" + block + "\n"
    path.write_text(new, encoding="utf-8")


# --- Pakete 1/2 ---------------------------------------------------------------
_PAKET_TITEL = {"1": "Pilot-Werkstoffe", "2": "Pilot-Eigenschaften (E7)"}


def _ename(cands: dict, eid: str) -> str:
    e = cands["entities"].get(eid, {})
    return e.get("label_de") or e.get("label_en") or eid


def write_candidate_report(cfg: Config, snap: dict, cands: dict, assessed: list, review_path: Path, path: Path) -> Path:
    short = cfg.profile.short_name
    by_key = {(p["iri"], eid): a for p, eid, a in assessed}
    L = [f"# Kandidaten {short} → Wikidata – {cands['retrieved']}", "",
         f"Prüf-Tabelle: `{review_path.name}` (Pakete {', '.join(cands['pakete'])}) · {short} {snap['ontology']['version']} · "
         f"Wikidata abgerufen {cands['retrieved_at'].replace('T', ' ')}", "",
         "Nur Vorschläge. „Regel:“ = mechanische Prüfung (Label, Klasse, Werkstoff, vorhandene Links), "
         "„Einschätzung:“ = fachlicher Vergleich der Definitionen. Entschieden wird in der Tabelle.", ""]
    if cands.get("warnings"):
        L += ["**Hinweise zum Lauf:**", ""] + [f"- {w}" for w in cands["warnings"]] + [""]
    for paket in cands["pakete"]:
        L += [f"## Paket {paket} – {_PAKET_TITEL.get(paket, '')}", ""]
        if cands["missing"].get(paket):
            L += [f"**Nicht in {short} {snap['ontology']['version']}:** " + ", ".join(cands["missing"][paket])
                  + " – keine Abbildung möglich (siehe review-needed.md).", ""]
        for iri, entry in cands["classes"].items():
            pilot = entry["pilot"]
            if pilot["paket"] != paket:
                continue
            L += [f"### {pilot['label']} (`{iri.rsplit('/', 1)[-1]}`) – {pilot['reason']}", ""]
            if pilot["linked"]:
                L += [f"Bereits abgebildet (Paket 0): " + ", ".join(f"{_ename(cands, q)} ({q})" for q in pilot["linked"]), ""]
            if entry["candidates"]:
                L += ["| Rang | Eintrag | Beschreibung | Score | Vorschlag |", "|---|---|---|---|---|"]
                for rank, c in enumerate(entry["candidates"], 1):
                    e = cands["entities"][c["qid"]]
                    a = by_key[(iri, c["qid"])]
                    p4 = f" ({snap['labels'].get(a.vorschlag_p4390, {}).get('en', a.vorschlag_p4390)})" if a.vorschlag_p4390 else ""
                    desc = (e.get("desc_de") or e.get("desc_en") or "").replace("|", "/")
                    L.append(f"| {rank} | {_ename(cands, c['qid'])} ({c['qid']}) | {desc} | {c['score']} | {a.vorschlag}{p4} |")
                L.append("")
            elif not pilot["linked"]:
                L += ["Keine Kandidaten gefunden.", ""]
            if entry["properties"]:
                L += ["Wikidata-Eigenschaft (P1628):", "", "| Rang | Eigenschaft | Datentyp | Score | Vorschlag |", "|---|---|---|---|---|"]
                for rank, p in enumerate(entry["properties"], 1):
                    a = by_key[(iri, p["pid"])]
                    L.append(f"| {rank} | {_ename(cands, p['pid'])} ({p['pid']}) | {p['datatype']} | {p['score']} | {a.vorschlag} |")
                L.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def update_review_needed_candidates(cfg: Config, snap: dict, cands: dict, assessed: list, review_path: Path) -> int:
    short = cfg.profile.short_name
    rel = review_path.relative_to(cfg.root) if review_path.is_relative_to(cfg.root) else review_path
    total = 0
    for paket in cands["pakete"]:
        grenz = [(p, eid, a) for p, eid, a in assessed if p["paket"] == paket and a.grenzfall]
        missing = cands["missing"].get(paket, [])
        # keine Kandidaten ODER alle Begriffs-Kandidaten verworfen
        usable = {p["iri"] for p, eid, a in assessed
                  if p["paket"] == paket and eid.startswith("Q") and a.vorschlag != "verwerfen"}
        empty = [e["pilot"] for e in cands["classes"].values()
                 if e["pilot"]["paket"] == paket and not e["pilot"]["linked"] and e["pilot"]["iri"] not in usable]
        n = len(grenz) + len(missing) + len(empty)
        total += n
        start, end = _markers(cfg, paket)
        L = [start,
             f"## pmdmap Paket {paket} – {_PAKET_TITEL.get(paket, '')} – Lauf {cands['retrieved_at'].replace('T', ' ')} "
             f"({n} Fund(e), {short} {snap['ontology']['version']})", "",
             f"Kandidaten für neue Abbildungen; entschieden wird in `{rel}`. Nichts davon wird automatisch übernommen.", ""]
        if missing:
            L += [f"### Klasse fehlt in {short} ({len(missing)})", ""]
            L += [f"- [ ] **{m}**: keine Klasse in {short} {snap['ontology']['version']} (Label/Synonym). "
                  f"Frage: an das {short}-Team melden, oder gehört der Begriff in eine andere Ontologie (MWO)?" for m in missing]
            L.append("")
        if empty:
            L += [f"### Kein passender Wikidata-Eintrag ({len(empty)})", ""]
            L += [f"- [ ] **{p['label']}** (`{p['iri'].rsplit('/', 1)[-1]}`): Suche ohne brauchbaren Treffer. "
                  "Frage: andere Bezeichnung suchen, Eintrag anlegen oder Lücke stehen lassen?" for p in empty]
            L.append("")
        L += [f"### Grenzfälle ({len(grenz)})", ""]
        for p, eid, a in grenz:
            texts = "; ".join(f.text for f in a.findings if f.grenzfall)
            if " | Einschätzung: " in a.begruendung:
                texts = (texts + " – " if texts else "") + "Einschätzung: " + a.begruendung.split(" | Einschätzung: ", 1)[1]
            L.append(f"- [ ] **{p['label']}** (`{p['iri'].rsplit('/', 1)[-1]}`) ↔ {_ename(cands, eid)} "
                     f"(https://www.wikidata.org/wiki/{'Property:' if eid.startswith('P') else ''}{eid}): "
                     f"Vorschlag {a.vorschlag}. {texts or 'Kein eindeutiger Kandidat - Definitionen vergleichen.'}")
        if not grenz:
            L.append("- keine")
        L.append(end)
        _replace_block(cfg, start, end, "\n".join(L))
    return total
