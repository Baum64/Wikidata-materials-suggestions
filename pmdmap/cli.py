"""Kommandozeile: python -m pmdmap fetch | review | export.

  fetch    Ontologie laden, Wikidata-Bestand erheben, Schnappschuss in cache/
  review   Pruef-Dokument quickstatements_<datum>.txt (+ Beleg-CSV, Berichte, review-needed.md)
  export   Pruef-Dokument pruefen (--nur-pruefen) bzw. in Teil-Dateien zu 50 Zeilen aufteilen

Schreibt nie in Wikidata.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assessment import Assessor, load_assessments
from .candidates import collect as collect_candidates
from .cache import Cache
from .config import Config, load_config
from .http import HttpClient
from .inventory import collect, latest_snapshot, load_snapshot, save_snapshot
from .ontology import load_ontology
from .report import (
    update_review_needed, update_review_needed_candidates, write_candidate_report,
    write_inventory_report,
)
from .qsdoc import build_document, doc_name, parse_document, previous_state, validate, write_export
from .review import build_candidate_rows, build_paket0_rows, write_review
from .wikidata import WikidataClient


def _clients(cfg: Config, refresh: bool):
    cache = Cache(cfg.cache_dir, cfg.cache_max_age_days, refresh=refresh)
    http = HttpClient(cfg.net)
    return cache, http, WikidataClient(cfg.wikidata, http, cache)


def cmd_fetch(cfg: Config, args) -> int:
    cache, http, wd = _clients(cfg, args.refresh)
    onto = load_ontology(cfg.profile, http, cache)
    print(f"{cfg.profile.short_name} {onto.meta.version}: {len(onto.classes)} Klassen im Index", file=sys.stderr)
    snap = collect(cfg, wd, onto)
    path = save_snapshot(cfg, snap)
    print(f"Schnappschuss: {path}")
    return 0


def cmd_review(cfg: Config, args) -> int:
    pakete = sorted(set(args.paket))
    cache, http, wd = _clients(cfg, args.refresh)
    snap_path = Path(args.bestand) if args.bestand else latest_snapshot(cfg)
    if snap_path is None or args.refresh:
        cmd_fetch(cfg, args)
        snap_path = latest_snapshot(cfg)
    snap = load_snapshot(snap_path)
    onto = load_ontology(cfg.profile, http, cache)
    if onto.meta.version != snap["ontology"]["version"]:
        print(f"Warnung: Schnappschuss mit {snap['ontology']['version']}, Ontologie-Cache {onto.meta.version}", file=sys.stderr)

    # Begriffsart neu aus der aktuellen Konfiguration (Ankerklassen), damit
    # eine geaenderte config.yaml keinen neuen Abruf braucht.
    for m in snap["mappings"]:
        m["category"] = onto.category(m["value"]) if onto.get(m["value"]) else ""

    date = snap["retrieved"]
    review_path = cfg.output_dir / f"review_{date}.csv"
    rows: list[dict] = []
    outputs: list[str] = []

    if "0" in pakete:
        assessor = Assessor(cfg, onto, snap, load_assessments(cfg.profile.assessments_file))
        rows0, assessed0 = build_paket0_rows(snap, onto, assessor)
        rows += rows0
        report = write_inventory_report(cfg, snap, assessed0, review_path, cfg.output_dir / f"bestand_{date}.md")
        n = update_review_needed(cfg, snap, assessed0, review_path)
        outputs += [f"Paket 0:       {len(rows0)} Zeilen, Bericht {report}", f"               review-needed: {n} Fund(e)"]

    cand_pakete = [p for p in pakete if p in ("1", "2")]
    if cand_pakete:
        cands = collect_candidates(cfg, wd, onto, snap, cand_pakete)
        rows12, assessed12 = build_candidate_rows(cfg, onto, snap, cands)
        rows += rows12
        report = write_candidate_report(cfg, snap, cands, assessed12, review_path, cfg.output_dir / f"kandidaten_{date}.md")
        n = update_review_needed_candidates(cfg, snap, cands, assessed12, review_path)
        outputs += [f"Pakete {'+'.join(cand_pakete)}:   {len(rows12)} Zeilen, Bericht {report}",
                    f"               review-needed: {n} Fund(e)"]

    review_path, notes = write_review(rows, review_path, set(pakete))

    # Pruef-Dokument (QuickStatements) - immer ueber alle Pakete: fehlende
    # Teile kommen aus dem Bestand bzw. dem letzten Kandidaten-Abruf.
    if "0" not in pakete:
        assessor = Assessor(cfg, onto, snap, load_assessments(cfg.profile.assessments_file))
        _, assessed0 = build_paket0_rows(snap, onto, assessor)
    # Kandidaten-Schnappschuss paketweise zusammenfuehren (ein Lauf nur fuer
    # Paket 2 soll Paket 1 nicht verlieren) und fuer das Dokument verwenden
    previous_cands = latest_candidates(cfg)
    if cand_pakete:
        cands = merge_candidates(previous_cands, cands, cand_pakete)
        cpath = cfg.cache_dir / cfg.profile.key / f"kandidaten_{date}.json"
        cpath.write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        cands = previous_cands
    assessed12 = build_candidate_rows(cfg, onto, snap, cands)[1] if cands else []
    doc_path = cfg.output_dir / doc_name(date)
    # Stand der vorhandenen Fassung uebernehmen - auch aus der frueheren
    # Endung review_<datum>.qs, falls die neue Datei noch nicht existiert
    legacy = cfg.output_dir / f"review_{date}.qs"
    prev = previous_state(doc_path) if doc_path.exists() else previous_state(legacy)
    text, stats = build_document(cfg, onto, snap, assessed0, cands, assessed12, prev)
    doc_path.write_text(text, encoding="utf-8")
    if legacy.exists() and not doc_path.samefile(legacy):
        print(f"Hinweis: {legacy.name} ist ersetzt durch {doc_path.name} (Stand übernommen) und kann gelöscht werden.",
              file=sys.stderr)

    print(f"Prüf-Dokument: {doc_path} ({stats['active']} aktiv, {stats['commented']} auskommentiert"
          + (f", {stats['orphans']} aus voriger Fassung" if stats["orphans"] else "") + ")")
    print(f"Beleg-Tabelle: {review_path}")
    for line in outputs:
        print(line)
    for note in notes:
        print(f"Hinweis: {note}", file=sys.stderr)
    return 0


def merge_candidates(old: dict | None, new: dict, pakete: list[str]) -> dict:
    """Klassen anderer Pakete aus dem alten Schnappschuss uebernehmen."""
    if not old:
        return new
    merged = dict(new)
    merged["classes"] = {k: v for k, v in old["classes"].items() if v["pilot"]["paket"] not in pakete}
    merged["classes"].update(new["classes"])
    merged["entities"] = {**old.get("entities", {}), **new["entities"]}
    merged["labels"] = {**old.get("labels", {}), **new["labels"]}
    merged["missing"] = {**{k: v for k, v in old.get("missing", {}).items() if k not in pakete}, **new["missing"]}
    merged["pakete"] = sorted(set(old.get("pakete", [])) | set(pakete))
    return merged


def latest_candidates(cfg: Config) -> dict | None:
    files = sorted((cfg.cache_dir / cfg.profile.key).glob("kandidaten_*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def cmd_export(cfg: Config, args) -> int:
    """Aktive Zeilen des Pruef-Dokuments pruefen und als reine QuickStatements schreiben."""
    doc = Path(args.review)
    if not doc.exists():
        print(f"{doc}: Datei nicht gefunden", file=sys.stderr)
        return 2
    cache, http, wd = _clients(cfg, False)
    snap_path = latest_snapshot(cfg)
    if snap_path is None:
        print("Kein Bestand im Cache - zuerst 'pmdmap fetch' und 'pmdmap review'.", file=sys.stderr)
        return 2
    snap = load_snapshot(snap_path)
    onto = load_ontology(cfg.profile, http, cache)
    cands = latest_candidates(cfg)
    lines, junk = parse_document(doc.read_text(encoding="utf-8"))
    result = validate(lines, cfg, onto, snap, cands)
    result.errors = junk + result.errors
    n_active = sum(1 for p in lines if p.active)
    for w in result.warnings:
        print(f"Hinweis: {w}", file=sys.stderr)
    if result.errors:
        for e in result.errors:
            print(f"FEHLER: {e}", file=sys.stderr)
        print(f"{len(result.errors)} Fehler - nichts geschrieben. Im Dokument korrigieren und erneut exportieren.", file=sys.stderr)
        return 1
    if not n_active:
        print("Keine aktive Zeile im Dokument - nichts zu exportieren.", file=sys.stderr)
        return 0
    if args.nur_pruefen:
        print(f"Prüfung ok: {n_active} aktive Zeilen, {len(result.warnings)} Hinweise. "
              f"Die Datei kann so in QuickStatements eingefügt werden.")
        return 0
    files = write_export(lines, cfg.output_dir, snap["ontology"]["retrieved"], cfg.profile.short_name)
    report = cfg.output_dir / f"export_{snap['retrieved']}.md"
    L = [f"# Export aus {doc.name}", "", f"{n_active} aktive Zeilen, {len(result.warnings)} Hinweise.", "",
         "## Dateien", ""] + [f"- `{f.name}`" + (f" ({len(f.read_text(encoding='utf-8').splitlines())} Zeilen)"
                                                  if f.suffix == ".txt" else "") for f in files]
    L += ["", "## Hinweise", ""] + ([f"- {w}" for w in result.warnings] or ["- keine"])
    report.write_text("\n".join(L) + "\n", encoding="utf-8")
    for f in files:
        print(f"geschrieben: {f}")
    print(f"Bericht:     {report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pmdmap", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.yaml", help="Konfigurationsdatei (Standard: config.yaml)")
    ap.add_argument("--ontologie", help="Profil aus config.yaml (Standard: Feld 'ontologie')")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="Ontologie und Wikidata-Bestand laden")
    p.add_argument("--refresh", action="store_true", help="Cache ignorieren und neu laden")

    p = sub.add_parser("review", help="Prüf-Tabelle erzeugen")
    p.add_argument("--paket", nargs="+", default=["0"], choices=["0", "1", "2"],
                   help="ein oder mehrere Pakete, z. B. --paket 1 2 (andere Pakete in der Tabelle bleiben erhalten)")
    p.add_argument("--bestand", help="bestimmter Schnappschuss (Standard: neuester)")
    p.add_argument("--refresh", action="store_true", help="vorher neu abrufen")

    p = sub.add_parser("export", help="QuickStatements aus dem Prüf-Dokument")
    p.add_argument("--review", required=True, help="Prüf-Dokument quickstatements_<datum>.txt (aktive Zeilen = ohne #)")
    p.add_argument("--nur-pruefen", action="store_true",
                   help="nur prüfen, keine Teil-Dateien schreiben (die Datei wird als Ganzes eingefügt)")

    args = ap.parse_args(argv)
    cfg = load_config(args.config, args.ontologie)
    return {"fetch": cmd_fetch, "review": cmd_review, "export": cmd_export}[args.cmd](cfg, args)
