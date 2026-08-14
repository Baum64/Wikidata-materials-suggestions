"""
Benchmark: Wie gut sind metallische Werkstoffe in Wikidata belegt?
==================================================================

Zaehlt fuer jede Property aus nomadwiki.cli.PROPERTY_MAP, wie viele Items
unterhalb von "Metallischer Werkstoff" (Q1924900) diese Aussage tatsaechlich
tragen. Damit wird sichtbar, wo sich Vorschlaege aus NOMAD ueberhaupt lohnen.

PROPERTY_MAP und NOMAD_FIELD_MAP werden importiert, nicht kopiert - die
Auswertung bleibt so automatisch synchron zum Generator.

Grundgesamtheit
---------------
Konkrete Werkstoffe sind in Wikidata ueberwiegend als UNTERKLASSEN modelliert
(Stahl ist eine Unterklasse von metallischem Werkstoff, keine Instanz).
Ausgewertet wird deshalb die Vereinigung aus
  - Instanzen:     ?i wdt:P31/wdt:P279* wd:Q1924900
  - Unterklassen:  ?i wdt:P279*         wd:Q1924900
Beide Teilmengen werden zusaetzlich einzeln ausgewiesen.

Aufruf
------
  python -m benchmark.benchmark
  python -m benchmark.benchmark --root Q11426 --csv abdeckung.csv
"""

import argparse
import csv
import os
import sys
import time
from typing import Optional

import requests

# Repo-Wurzel in den Pfad, damit "import nomadwiki" auch bei direktem
# Aufruf (python benchmark/benchmark.py) funktioniert.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nomadwiki.cli import NOMAD_FIELD_MAP, PROPERTY_MAP  # noqa: E402

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "MaterialsWikidataSuggestBot/0.1 (mailto:DEINE-ADRESSE@example.org)"
HEADERS = {"User-Agent": USER_AGENT}

DEFAULT_ROOT = "Q1924900"  # Metallischer Werkstoff

# Instanzen ODER Unterklassen - siehe Modul-Docstring.
POPULATION_PATTERN = (
    "{{ ?i wdt:P31/wdt:P279* wd:{root} }} UNION {{ ?i wdt:P279* wd:{root} }}"
)


def sparql(query: str, attempts: int = 5) -> list:
    """SPARQL-GET mit Backoff. Der Query-Service antwortet unter Last
    sporadisch mit 429/502; ohne Retry reisst das die Auswertung ab.
    """
    delay = 3.0
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=90,
            )
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            print(f"  {type(exc).__name__} - Versuch {attempt}/{attempts}", file=sys.stderr)
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp.json()["results"]["bindings"]
            if attempt == attempts:
                resp.raise_for_status()
            print(
                f"  HTTP {resp.status_code} - Versuch {attempt}/{attempts}, "
                f"warte {delay:.0f}s",
                file=sys.stderr,
            )
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("SPARQL-Endpunkt nicht erreichbar")


def count_population(root: str) -> dict:
    """Groesse der Grundgesamtheit, aufgeschluesselt nach Modellierung."""
    counts = {}
    for key, pattern in {
        "instanzen": "?i wdt:P31/wdt:P279* wd:%s" % root,
        "unterklassen": "?i wdt:P279* wd:%s" % root,
        "gesamt": POPULATION_PATTERN.format(root=root),
    }.items():
        rows = sparql(f"SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE {{ {pattern} }}")
        counts[key] = int(rows[0]["n"]["value"])
    return counts


def count_filled(root: str, pids: list) -> dict:
    """{pid: Anzahl Items der Grundgesamtheit mit dieser Aussage}.

    Properties ohne einen einzigen Treffer tauchen im GROUP BY nicht auf und
    werden deshalb explizit auf 0 vorbelegt.
    """
    values = " ".join(f"wdt:{pid}" for pid in pids)
    rows = sparql(
        f"""SELECT ?p (COUNT(DISTINCT ?i) AS ?n) WHERE {{
  {POPULATION_PATTERN.format(root=root)}
  VALUES ?p {{ {values} }}
  ?i ?p ?v .
}} GROUP BY ?p"""
    )
    filled = {pid: 0 for pid in pids}
    for row in rows:
        filled[row["p"]["value"].rsplit("/", 1)[-1]] = int(row["n"]["value"])
    return filled


def best_covered(root: str, pids: list, limit: int = 10) -> list:
    """Items der Grundgesamtheit mit den meisten der betrachteten Aussagen."""
    values = " ".join(f"wdt:{pid}" for pid in pids)
    return sparql(
        f"""SELECT ?i ?iLabel (COUNT(DISTINCT ?p) AS ?n) WHERE {{
  {POPULATION_PATTERN.format(root=root)}
  VALUES ?p {{ {values} }}
  ?i ?p ?v .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}} GROUP BY ?i ?iLabel ORDER BY DESC(?n) LIMIT {limit}"""
    )


def build_rows(root: str) -> tuple:
    """Sammelt alle Kennzahlen. Gibt (population, rows) zurueck."""
    pids = [p["pid"] for p in PROPERTY_MAP.values()]
    population = count_population(root)
    filled = count_filled(root, pids)
    total = population["gesamt"]

    # Welche Schluessel kann nomadwiki ueberhaupt befuellen?
    mit_nomad_pfad = set(NOMAD_FIELD_MAP.values())

    rows = []
    for key, info in PROPERTY_MAP.items():
        n = filled[info["pid"]]
        rows.append(
            {
                "schluessel": key,
                "pid": info["pid"],
                "label": info["label"],
                "datatype": info.get("datatype", "quantity"),
                "gefuellt": n,
                "luecke": total - n,
                "anteil_prozent": round(100.0 * n / total, 2) if total else 0.0,
                "nomad_quelle": "ja" if key in mit_nomad_pfad else "nein",
            }
        )
    rows.sort(key=lambda r: r["gefuellt"], reverse=True)
    return population, rows


def print_report(root: str, population: dict, rows: list) -> None:
    total = population["gesamt"]
    print()
    print(f"Grundgesamtheit unterhalb von {root}")
    print(f"  Instanzen (P31/P279*)          {population['instanzen']:>7}")
    print(f"  Unterklassen (P279*)           {population['unterklassen']:>7}")
    print(f"  ausgewertet (Vereinigung)      {total:>7}")
    print()
    kopf = (
        f"{'Schluessel':<24}{'PID':<8}{'Typ':<10}"
        f"{'gefuellt':>9}{'Anteil':>9}{'Luecke':>9}  NOMAD-Quelle"
    )
    print(kopf)
    print("-" * len(kopf))
    for r in rows:
        print(
            f"{r['schluessel']:<24}{r['pid']:<8}{r['datatype']:<10}"
            f"{r['gefuellt']:>9}{r['anteil_prozent']:>8.2f}%{r['luecke']:>9}"
            f"  {r['nomad_quelle']}"
        )
    print()

    belegbar = [r for r in rows if r["nomad_quelle"] == "ja"]
    if belegbar:
        print("Aus NOMAD tatsaechlich belegbar (Rest wartet auf Quelle/Property):")
        for r in belegbar:
            print(
                f"  {r['label']:<28} {r['gefuellt']:>6} von {total} gefuellt"
                f"  ->  {r['luecke']} offen"
            )
    print()


def write_csv(rows: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV geschrieben nach: {path}", file=sys.stderr)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zaehlt, wie oft die PROPERTY_MAP-Properties unterhalb "
        "eines Wikidata-Items belegt sind."
    )
    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help=f"Wurzel-Item der Grundgesamtheit (Default: {DEFAULT_ROOT}, "
        "Metallischer Werkstoff)",
    )
    parser.add_argument("--csv", default=None, help="Ergebnis zusaetzlich als CSV")
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Anzahl der am besten belegten Items in der Ausgabe (0 = aus)",
    )
    args = parser.parse_args(argv)

    population, rows = build_rows(args.root)
    print_report(args.root, population, rows)

    if args.top:
        pids = [p["pid"] for p in PROPERTY_MAP.values()]
        print(f"Am besten belegte Items (max. {len(pids)} Aussagen):")
        for b in best_covered(args.root, pids, args.top):
            qid = b["i"]["value"].rsplit("/", 1)[-1]
            print(f"  {b['n']['value']:>2}/{len(pids)}  {qid:<12} {b['iLabel']['value']}")
        print()

    if args.csv:
        write_csv(rows, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
