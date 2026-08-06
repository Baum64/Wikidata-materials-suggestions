"""Command-line interface.

Example:
    python -m wikikg.cli --title Holz --lang de
    python -m wikikg.cli --title Holz --lang de --format json --output holz.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import List

from .compare import LinkComparison, compare_links, missing_only, summarize
from .wikidata_client import WikidataClient
from .wikipedia_client import WikipediaClient


def run(title: str, lang: str = "de") -> List[LinkComparison]:
    wp = WikipediaClient(lang=lang)
    wd = WikidataClient(lang=lang)

    source_qid = wp.resolve_qid(title)
    if source_qid is None:
        raise SystemExit(
            f"Für den Artikel '{title}' wurde kein Wikidata-Item gefunden."
        )

    print(f"Quellartikel: {title}  ->  Wikidata {source_qid}", file=sys.stderr)

    print("Lade ausgehende Wikipedia-Links ...", file=sys.stderr)
    wp_links = list(wp.get_outgoing_links(title))
    print(f"  {len(wp_links)} Links gefunden.", file=sys.stderr)

    print("Lade ausgehende Wikidata-Statements ...", file=sys.stderr)
    wd_claims = wd.get_outgoing_item_claims(source_qid)
    print(f"  {len(wd_claims)} verknüpfte Items in Wikidata gefunden.", file=sys.stderr)

    results = compare_links(wp_links, wd_claims)

    # enrich matched results with human-readable property labels
    all_prop_ids = sorted({p for r in results for p in r.via_properties})
    if all_prop_ids:
        labels = wd.get_property_labels(all_prop_ids)
        for r in results:
            r.via_properties = [labels.get(p, p) for p in r.via_properties]

    return results


def write_output(results: List[LinkComparison], fmt: str, output: str | None) -> None:
    if fmt == "json":
        payload = [r.__dict__ for r in results]
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        _write(text, output)
    elif fmt == "csv":
        lines = ["title,qid,status,via_properties"]
        for r in results:
            via = "|".join(r.via_properties)
            lines.append(f'"{r.title}","{r.qid or ""}","{r.status}","{via}"')
        _write("\n".join(lines), output)
    else:  # table (default, human-readable)
        summary = summarize(results)
        lines = [
            f"Gesamt: {summary['total']}  |  "
            f"in Wikidata vorhanden: {summary['matched']}  |  "
            f"fehlend: {summary['missing']}  |  "
            f"ohne Wikidata-Item: {summary['no_wikidata_item']}",
            "",
            "Fehlende Verbindungen (in Wikipedia verlinkt, in Wikidata nicht als Statement vorhanden):",
        ]
        for r in missing_only(results):
            lines.append(f"  - {r.title}  ({r.qid})")
        _write("\n".join(lines), output)


def _write(text: str, output: str | None) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Ergebnis geschrieben nach {output}", file=sys.stderr)
    else:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vergleicht ausgehende Wikipedia-Links eines Artikels mit den "
        "ausgehenden Beziehungen des entsprechenden Wikidata-Items und zeigt, "
        "welche Verbindungen in Wikidata fehlen."
    )
    parser.add_argument("--title", required=True, help="Wikipedia-Artikeltitel, z.B. Holz")
    parser.add_argument("--lang", default="de", help="Wikipedia-/Wikidata-Sprachcode (default: de)")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table")
    parser.add_argument("--output", help="Datei zum Schreiben statt stdout")
    args = parser.parse_args()

    results = run(args.title, args.lang)
    write_output(results, args.format, args.output)


if __name__ == "__main__":
    main()
