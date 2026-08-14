"""
Benchmark: Wie gut sind metallische Werkstoffe in Wikidata belegt?
==================================================================

Zaehlt fuer jede Property, wie viele Items unterhalb von "Metallischer
Werkstoff" (Q1924900) diese Aussage tatsaechlich tragen. Damit wird sichtbar,
wo sich Vorschlaege aus NOMAD ueberhaupt lohnen.

Woher kommt die Property-Liste?
-------------------------------
Aus [[Wikidata:WikiProject Materials/Properties]], den Abschnitten
Physics, Mechanical, Thermal, Chemical und "Electric and Magnetic".
Die Seite listet ihre Properties als {{List of properties with sources/Row
|id=NNNN}}; genau diese ids werden ausgelesen (Platzhalter "id=new" aus der
Vorlagendoku werden verworfen, Unterabschnitte gehoeren zum Elternabschnitt).

Die Liste wird live geholt und als Momentaufnahme in properties_snapshot.json
abgelegt - damit bleibt ein Lauf reproduzierbar und --offline moeglich.

Zusaetzlich wird markiert, welche Properties nomadwiki ueberhaupt bedienen
kann: PROPERTY_MAP und NOMAD_FIELD_MAP werden importiert, nicht kopiert.

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
  python -m benchmark.benchmark --offline          # ohne Wiki-Abruf
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from typing import Optional

import requests

# Repo-Wurzel in den Pfad, damit "import nomadwiki" auch bei direktem
# Aufruf (python benchmark/benchmark.py) funktioniert.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nomadwiki.cli import NOMAD_FIELD_MAP, PROPERTY_MAP  # noqa: E402

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "MaterialsWikidataSuggestBot/0.1 (mailto:DEINE-ADRESSE@example.org)"
HEADERS = {"User-Agent": USER_AGENT}

DEFAULT_ROOT = "Q1924900"  # Metallischer Werkstoff
PROJECT_PAGE = "Wikidata:WikiProject Materials/Properties"
DEFAULT_SECTIONS = ["Physics", "Mechanical", "Thermal", "Chemical",
                    "Electric and Magnetic"]
SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "properties_snapshot.json")

# Instanzen ODER Unterklassen - siehe Modul-Docstring.
POPULATION_PATTERN = (
    "{{ ?i wdt:P31/wdt:P279* wd:{root} }} UNION {{ ?i wdt:P279* wd:{root} }}"
)

HEADING_RE = re.compile(r"^(={2,})\s*(.+?)\s*\1\s*$", re.M)
ROW_ID_RE = re.compile(r"/Row\|id=(\d+)")  # nur echte Zahlen, "new" faellt raus


# ---------------------------------------------------------------------------
# HTTP mit Backoff
# ---------------------------------------------------------------------------

def _get(url: str, params: dict, attempts: int = 5, timeout: int = 120):
    """GET mit Backoff bei 429/5xx. Der Query-Service antwortet unter Last
    sporadisch mit 429/502; ohne Retry reisst das die Auswertung ab.
    """
    delay = 3.0
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            print(f"  {type(exc).__name__} - Versuch {attempt}/{attempts}",
                  file=sys.stderr)
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp
            if attempt == attempts:
                resp.raise_for_status()
            print(f"  HTTP {resp.status_code} - Versuch {attempt}/{attempts}, "
                  f"warte {delay:.0f}s", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"nicht erreichbar: {url}")


def sparql(query: str) -> list:
    return _get(WIKIDATA_SPARQL, {"query": query, "format": "json"}).json()[
        "results"]["bindings"]


# ---------------------------------------------------------------------------
# Property-Liste aus dem WikiProject
# ---------------------------------------------------------------------------

def parse_sections(wikitext: str, wanted: list) -> dict:
    """{Abschnitt: [PID, ...]} aus dem Wikitext der Projektseite.

    Ein Abschnitt reicht bis zur naechsten Ueberschrift GLEICHER oder
    hoeherer Ebene, damit Unterabschnitte (z. B. "Multidirectional mechanical
    properties" unter Mechanical) mit ausgewertet werden.
    """
    heads = [(m.start(), len(m.group(1)), m.group(2))
             for m in HEADING_RE.finditer(wikitext)]
    out = {}
    for i, (pos, lvl, name) in enumerate(heads):
        if name not in wanted:
            continue
        end = len(wikitext)
        for pos2, lvl2, _ in heads[i + 1:]:
            if lvl2 <= lvl:
                end = pos2
                break
        seen = []
        for num in ROW_ID_RE.findall(wikitext[pos:end]):
            pid = f"P{num}"
            if pid not in seen:
                seen.append(pid)
        out[name] = seen
    return out


def fetch_project_properties(sections: list, offline: bool = False) -> dict:
    """Property-Liste holen; bei --offline oder Netzfehler aus dem Snapshot."""
    if not offline:
        try:
            data = _get(WIKIDATA_API, {
                "action": "parse", "page": PROJECT_PAGE,
                "prop": "wikitext", "format": "json", "formatversion": "2",
            }, timeout=60).json()
            if "error" in data:
                raise RuntimeError(data["error"].get("info", "Parse-Fehler"))
            parsed = parse_sections(data["parse"]["wikitext"], sections)
            fehlend = [s for s in sections if not parsed.get(s)]
            if fehlend:
                print(f"  Warnung: Abschnitt(e) ohne Properties: {fehlend}",
                      file=sys.stderr)
            with open(SNAPSHOT, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=1, ensure_ascii=False)
            return parsed
        except Exception as exc:  # Netz weg / Seite umbenannt -> Snapshot
            print(f"  Abruf fehlgeschlagen ({exc}); nutze Snapshot.",
                  file=sys.stderr)
    if not os.path.exists(SNAPSHOT):
        raise SystemExit(
            f"Kein Snapshot unter {SNAPSHOT} - einmal online laufen lassen.")
    with open(SNAPSHOT, encoding="utf-8") as f:
        return json.load(f)


def fetch_property_meta(pids: list) -> dict:
    """{pid: {'label': ..., 'datatype': ...}} - wbgetentities nimmt max. 50."""
    meta = {}
    for i in range(0, len(pids), 50):
        batch = pids[i:i + 50]
        data = _get(WIKIDATA_API, {
            "action": "wbgetentities", "ids": "|".join(batch),
            "props": "labels|datatype", "languages": "de|en",
            "format": "json", "formatversion": "2",
        }, timeout=60).json()
        for pid, ent in data.get("entities", {}).items():
            labels = ent.get("labels", {})
            meta[pid] = {
                "label": (labels.get("de") or labels.get("en")
                          or {"value": pid})["value"],
                "datatype": ent.get("datatype", "?"),
            }
    return meta


# ---------------------------------------------------------------------------
# Zaehlung
# ---------------------------------------------------------------------------

def count_population(root: str) -> dict:
    counts = {}
    for key, pattern in {
        "instanzen": f"?i wdt:P31/wdt:P279* wd:{root}",
        "unterklassen": f"?i wdt:P279* wd:{root}",
        "gesamt": POPULATION_PATTERN.format(root=root),
    }.items():
        rows = sparql(f"SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE {{ {pattern} }}")
        counts[key] = int(rows[0]["n"]["value"])
    return counts


def count_filled(root: str, pids: list, chunk: int = 60) -> dict:
    """{pid: Anzahl Items der Grundgesamtheit mit dieser Aussage}.

    Properties ohne Treffer fehlen im GROUP BY und werden auf 0 vorbelegt.
    In Bloecken abgefragt, damit die Query bei langen Listen nicht ins
    Timeout des Query-Service laeuft.
    """
    filled = {pid: 0 for pid in pids}
    for i in range(0, len(pids), chunk):
        values = " ".join(f"wdt:{p}" for p in pids[i:i + chunk])
        rows = sparql(f"""SELECT ?p (COUNT(DISTINCT ?i) AS ?n) WHERE {{
  {POPULATION_PATTERN.format(root=root)}
  VALUES ?p {{ {values} }}
  ?i ?p ?v .
}} GROUP BY ?p""")
        for row in rows:
            filled[row["p"]["value"].rsplit("/", 1)[-1]] = int(row["n"]["value"])
    return filled


def best_covered(root: str, pids: list, limit: int = 10) -> list:
    values = " ".join(f"wdt:{p}" for p in pids)
    return sparql(f"""SELECT ?i ?iLabel (COUNT(DISTINCT ?p) AS ?n) WHERE {{
  {POPULATION_PATTERN.format(root=root)}
  VALUES ?p {{ {values} }}
  ?i ?p ?v .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}} GROUP BY ?i ?iLabel ORDER BY DESC(?n) LIMIT {limit}""")


# ---------------------------------------------------------------------------
# Bericht
# ---------------------------------------------------------------------------

def build_rows(sections: dict, meta: dict, filled: dict, total: int) -> list:
    # Welche Properties kann nomadwiki bedienen?
    pid_to_key = {info["pid"]: key for key, info in PROPERTY_MAP.items()}
    mit_nomad_pfad = set(NOMAD_FIELD_MAP.values())

    rows = []
    for section, pids in sections.items():
        for pid in pids:
            key = pid_to_key.get(pid)
            n = filled.get(pid, 0)
            rows.append({
                "abschnitt": section,
                "pid": pid,
                "label": meta.get(pid, {}).get("label", pid),
                "datatype": meta.get(pid, {}).get("datatype", "?"),
                "gefuellt": n,
                "luecke": total - n,
                "anteil_prozent": round(100.0 * n / total, 2) if total else 0.0,
                "in_property_map": key or "",
                "nomad_quelle": "ja" if key in mit_nomad_pfad else "nein",
            })
    return rows


def print_report(root: str, population: dict, rows: list) -> None:
    total = population["gesamt"]
    print()
    print(f"Grundgesamtheit unterhalb von {root}")
    print(f"  Instanzen (P31/P279*)          {population['instanzen']:>7}")
    print(f"  Unterklassen (P279*)           {population['unterklassen']:>7}")
    print(f"  ausgewertet (Vereinigung)      {total:>7}")

    for section in dict.fromkeys(r["abschnitt"] for r in rows):
        teil = sorted((r for r in rows if r["abschnitt"] == section),
                      key=lambda r: -r["gefuellt"])
        belegt = sum(1 for r in teil if r["gefuellt"])
        print()
        print(f"== {section}  ({len(teil)} Properties, {belegt} davon belegt)")
        kopf = (f"  {'PID':<8}{'Label':<34}{'Typ':<12}"
                f"{'gefuellt':>9}{'Anteil':>9}  nomadwiki")
        print(kopf)
        print("  " + "-" * (len(kopf) - 2))
        for r in teil:
            marker = "<- " + r["in_property_map"] if r["in_property_map"] else ""
            if r["nomad_quelle"] == "ja":
                marker += " [NOMAD]"
            print(f"  {r['pid']:<8}{r['label'][:33]:<34}{r['datatype'][:11]:<12}"
                  f"{r['gefuellt']:>9}{r['anteil_prozent']:>8.2f}%  {marker}")

    print()
    leer = [r for r in rows if not r["gefuellt"]]
    print(f"Zusammenfassung: {len(rows)} Properties, "
          f"{len(rows) - len(leer)} mindestens einmal belegt, "
          f"{len(leer)} komplett leer.")
    belegbar = [r for r in rows if r["nomad_quelle"] == "ja"]
    if belegbar:
        print("Aus NOMAD tatsaechlich belegbar:")
        for r in belegbar:
            print(f"  {r['pid']} {r['label']:<28} {r['gefuellt']:>6} von "
                  f"{total} gefuellt  ->  {r['luecke']} offen")
    print()


def write_csv(rows: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV geschrieben nach: {path}", file=sys.stderr)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Zaehlt, wie oft die Properties aus dem WikiProject "
                    "Materials unterhalb eines Wikidata-Items belegt sind.")
    parser.add_argument("--root", default=DEFAULT_ROOT,
                        help=f"Wurzel-Item (Default: {DEFAULT_ROOT}, "
                             "Metallischer Werkstoff)")
    parser.add_argument("--sections", nargs="+", default=DEFAULT_SECTIONS,
                        help="Abschnitte der Projektseite "
                             f"(Default: {' '.join(DEFAULT_SECTIONS)})")
    parser.add_argument("--offline", action="store_true",
                        help="Property-Liste aus properties_snapshot.json")
    parser.add_argument("--csv", default=None, help="Ergebnis zusaetzlich als CSV")
    parser.add_argument("--top", type=int, default=10,
                        help="Anzahl der am besten belegten Items (0 = aus)")
    args = parser.parse_args(argv)

    sections = fetch_project_properties(args.sections, args.offline)
    pids = list(dict.fromkeys(p for v in sections.values() for p in v))
    print(f"{len(pids)} Properties aus {len(sections)} Abschnitten von "
          f"[[{PROJECT_PAGE}]]", file=sys.stderr)

    meta = fetch_property_meta(pids)
    population = count_population(args.root)
    filled = count_filled(args.root, pids)
    rows = build_rows(sections, meta, filled, population["gesamt"])
    print_report(args.root, population, rows)

    if args.top:
        print(f"Am besten belegte Items (max. {len(pids)} Aussagen):")
        for b in best_covered(args.root, pids, args.top):
            qid = b["i"]["value"].rsplit("/", 1)[-1]
            print(f"  {b['n']['value']:>3}/{len(pids)}  {qid:<12} "
                  f"{b['iLabel']['value']}")
        print()

    if args.csv:
        write_csv(rows, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
