"""
Benchmark: Wie gut sind metallische Werkstoffe in Wikidata belegt?
==================================================================

Zaehlt fuer jede Property, wie viele Items unterhalb von "Metallischer
Werkstoff" (Q1924900) diese Aussage tatsaechlich tragen. Damit wird sichtbar,
wo sich Vorschlaege aus dem Materials Project ueberhaupt lohnen.

Woher kommt die Property-Liste?
-------------------------------
Aus [[Wikidata:WikiProject Materials/Properties]], den Abschnitten
Physics, Mechanical, Thermal, Chemical und "Electric and Magnetic".
Die Seite listet ihre Properties als {{List of properties with sources/Row
|id=NNNN}}; genau diese ids werden ausgelesen (Platzhalter "id=new" aus der
Vorlagendoku werden verworfen, Unterabschnitte gehoeren zum Elternabschnitt).

Die Liste wird live geholt und als Momentaufnahme in properties_snapshot.json
abgelegt - damit bleibt ein Lauf reproduzierbar und --offline moeglich. Stand
des Snapshots: 2026-08-23 (abends), 65 Eintraege, alle verschieden - der
Doppeleintrag P5672 unter Physics und Thermal ist von der Projektseite
verschwunden. Zuletzt kam P1088 (Mohshaerte) unter "Mechanical" dazu;
materialswiki bedient sie seither aus den Infoboxen. Davor waren es die
thermodynamischen Groessen P3078 (Standardbildungsenthalpie) und P3071
(molare Standardentropie) unter "Chemical".

Die Projektseite listet nur Messgroessen. Die CAS-Nummer (P231) wird deshalb
fest ergaenzt (Abschnitt "Identifikatoren", abschaltbar mit --no-extra) - sie
ist der zentrale externe Schluessel zu Stoffdatenbanken.

Zusaetzlich wird je Property markiert, AUS WELCHER QUELLE materialswiki den
Wert ueberhaupt holen koennte - also welche Stufe des Laufs sie wirklich
abfragt:

  COD     Crystallography Open Database (Struktur)
  MP      Materials Project (DFT-Rechnung)
  NIST    NIST Chemistry WebBook (Thermochemie)
  WP      Wikipedia-Infoboxen (de und en)
  Formel  aus der Summenformel abgeleitet, ohne Abruf nach aussen
  WD      aus dem Wikidata-Item selbst abgeleitet (Punktgruppe aus Raumgruppe)

Die vier Netz-Stufen kommen aus STUFEN_PIDS, die Ableitungen aus
PROPERTY_MAP - alles importiert, nicht kopiert, damit Benchmark und
Vorschlagslauf nicht auseinanderlaufen.

Grundgesamtheit
---------------
Zwei Modi, umschaltbar mit --population:

'subtree' (Default): Konkrete Werkstoffe sind in Wikidata ueberwiegend als
UNTERKLASSEN modelliert (Stahl ist eine Unterklasse von metallischem
Werkstoff, keine Instanz). Ausgewertet wird deshalb die Vereinigung aus
  - Instanzen:     ?i wdt:P31/wdt:P279* wd:Q1924900
  - Unterklassen:  ?i wdt:P279*         wd:Q1924900
Beide Teilmengen werden zusaetzlich einzeln ausgewiesen.

'legierungen': die Legierungen unter Q37756 - aber OHNE den Metalle-Zweig.
Wikidata modelliert Q11426 "Metalle" als Unterklasse von Q37756 "Legierung",
also fachlich verkehrt herum; dadurch haengt jedes Metall samt Isotopen unter
"Legierung" und die naive Abfrage liefert 3718 statt 568 Items (Selen-78,
Rubidium-87, gediegen Kupfer ...). Das Muster wird aus materialswiki
importiert, damit Benchmark und Vorschlagslauf dasselbe meinen.

'metalle': die metallischen und halbmetallischen Elemente - genau die
Auswahl, die materialswiki im Periodensystem-Modus bearbeitet (98 der 118).
Ausgewaehlt wird ueber das Elementsymbol gegen die Nichtmetall-Liste aus
materialswiki, NICHT ueber Wikidatas Metall-Klassen: die finden nur 55 der
rund 90 Metalle und verlieren dabei Cr, Mn, Co, Ni, Re und saemtliche
Lanthanoide und Actinoide.

'periodensystem': alle chemischen Elemente, also Instanzen von Q11344 mit
Ordnungszahl (P1086) bis --max-z. Hier taugt der Subtree-Ansatz NICHT: unter
Q11344 haengen 1706 Items, weil Elementgruppen (Halbmetalle, Uebergangs-
metalle, ...) als Unterklassen modelliert sind. Die Z-Grenze ist noetig, weil
Wikidata auch hypothetische Elemente bis Z=184 fuehrt.

Aufruf
------
  python -m benchmark.benchmark
  python -m benchmark.benchmark --root Q11426 --md abdeckung.md
  python -m benchmark.benchmark --population legierungen
  python -m benchmark.benchmark --population metalle
  python -m benchmark.benchmark --population periodensystem
  python -m benchmark.benchmark --offline          # ohne Wiki-Abruf
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Optional

import requests

# Repo-Wurzel in den Pfad, damit "import materialswiki" auch bei direktem
# Aufruf (python benchmark/benchmark.py) funktioniert.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import konfig  # noqa: E402
from materialswiki.cli import (  # noqa: E402
    CHEMBOX_FIELDS, HALBMETALLE, MP_FIELD_MAP, NICHTMETALLE, PROPERTY_MAP,
    STUFEN_PIDS, WERKSTOFFGRUPPEN, WIKIPEDIA_DE_CHEM_FIELDS,
    WIKIPEDIA_DE_FIELDS, WIKIPEDIA_NUMERIC_FIELDS,
)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
# Kontaktadresse aus der Umgebung (konfig spiegelt .env.api-keys hinein).
USER_AGENT = ("MaterialsWikidataSuggestBot/0.1 "
              f'(mailto:{konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")})')
HEADERS = {"User-Agent": USER_AGENT}

DEFAULT_ROOT = "Q1924900"  # Metallischer Werkstoff
PROJECT_PAGE = "Wikidata:WikiProject Materials/Properties"
DEFAULT_SECTIONS = ["Physics", "Mechanical", "Thermal", "Chemical",
                    "Electric and Magnetic"]
SNAPSHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "properties_snapshot.json")

# Die Projektseite listet nur Messgroessen, keine Identifikatoren. Die
# CAS-Nummer ist fuer Werkstoffe und Elemente aber der zentrale externe
# Schluessel (und die Bruecke zu Stoffdatenbanken), deshalb hier fest ergaenzt.
# Herkunft bleibt getrennt sichtbar: eigener Abschnitt, nicht in "Chemical".
EXTRA_SECTIONS = {"Identifikatoren": ["P231"]}  # P231 = CAS-Nummer

# Instanzen ODER Unterklassen - siehe Modul-Docstring.
POPULATION_PATTERN = (
    "{{ ?i wdt:P31/wdt:P279* wd:{root} }} UNION {{ ?i wdt:P279* wd:{root} }}"
)

# "Elemente des Periodensystems": Instanzen von chemisches Element (Q11344)
# MIT Ordnungszahl. Der Subtree-Ansatz taugt hier nicht - P279* unter Q11344
# zieht 1706 Items (Elementgruppen, Halbmetalle, ...) statt der Elemente.
# Die Z-Grenze ist noetig, weil Wikidata auch hypothetische Elemente bis
# Z=184 fuehrt: ohne Filter 174 Items, mit Z<=118 genau das reale
# Periodensystem.
PERIODENSYSTEM_PATTERN = "?i wdt:P31 wd:Q11344 ; wdt:P1086 ?z . FILTER(?z <= {max_z})"
DEFAULT_MAX_Z = 118

# "metalle": dieselbe Grundgesamtheit, die materialswiki im
# Periodensystem-Modus bearbeitet - Metalle und Halbmetalle, also alle
# Elemente ausser den Nichtmetallen. Sonst misst der Benchmark etwas anderes,
# als das Werkzeug beackert.
#
# Die Auswahl laeuft ueber das Elementsymbol (P246) und die fest gepflegte
# Nichtmetall-Liste aus materialswiki, NICHT ueber Wikidatas Metall-Klassen:
# die finden nur 55 der rund 90 Metalle und verlieren dabei Cr, Mn, Co, Ni,
# Re und saemtliche Lanthanoide und Actinoide (gemessen 2026-08-16).
METALLE_PATTERN = (
    "?i wdt:P31 wd:Q11344 ; wdt:P1086 ?z ; wdt:P246 ?sym . "
    "FILTER(?z <= {max_z}) FILTER(?sym NOT IN ({nichtmetalle}))"
)

# ---------------------------------------------------------------------------
# Welche Quelle liefert welche Property - und in welchem Lauf?
# ---------------------------------------------------------------------------
#
# Die vier Stufen, die wirklich nach aussen gehen, stehen schon in
# STUFEN_PIDS (materialswiki/properties.py) - genau die Menge, mit der der
# Lauf entscheidet, ob er eine Quelle ueberhaupt noch befragen muss. Sie wird
# hier importiert, nicht abgeschrieben.
#
# Die beiden ABLEITUNGEN stehen dort nicht, weil sie nichts abfragen: die
# Formelstufe zerlegt die Summenformel (P2670/P527), die Punktgruppenstufe
# liest die Raumgruppe am Item selbst ab (P589).
#
# Entscheidend ist, dass nicht jeder Lauf jede Stufe fahren kann - sonst
# verspricht der Benchmark Vorschlaege, die nie kommen:
#
#   Gruppenlauf (--group, also lauf.py legierungen|minerale|oxide|carbide)
#       faehrt alle sechs Stufen.
#   Elementlauf (--periodic-table, also lauf.py metalle|periodensystem)
#       faehrt NUR die vier externen Quellen. Punktgruppe und Formel gibt es
#       dort nicht: build_periodic_table_proposals ruft sie nicht auf.
#
# Und die Formelstufe ist ueberdies per Default AUS (--formel, cli.py:
# "P527 und P2670 sollen nicht mehr vorgeschlagen werden"). Sie wird deshalb
# eingeklammert ausgewiesen: "(Formel)" heisst "nur, wenn eingeschaltet".
QUELLEN = {
    "cod":         ("COD",    "Crystallography Open Database"),
    "mp":          ("MP",     "Materials Project (DFT)"),
    "nist":        ("NIST",   "NIST Chemistry WebBook"),
    "punktgruppe": ("WD",     "aus der Raumgruppe am Item abgeleitet"),
    "formel":      ("Formel", "aus der Summenformel abgeleitet"),
    # Die Wikipedia-Stufe zerfaellt in ihre Vorlagen - siehe unten.
    "de-element":    ("WPde-El",   "de {{Infobox Chemisches Element}}"),
    "de-chemikalie": ("WPde-Chem", "de {{Infobox Chemikalie}}"),
    "de-mineral":    ("WPde-Min",  "de {{Infobox Mineral}}"),
    "en-element":    ("WPen-El",   "en Template:Infobox <element>"),
    "en-chembox":    ("WPen-Chem", "en {{Chembox}}"),
}

# Stufen, die nichts abfragen und deshalb nicht in STUFEN_PIDS stehen:
# Stufe -> interne Schluessel aus PROPERTY_MAP.
ABLEITUNGS_SCHLUESSEL = {
    "punktgruppe": ("point_group",),
    "formel": ("has_part_of_class", "has_part"),
}

# Stufe -> Schalter, mit dem sie erst angeht. Alles andere laeuft von selbst.
DEFAULT_AUS = {"formel": "--formel"}

# ---------------------------------------------------------------------------
# Die Wikipedia-Stufe ist keine Quelle, sondern fuenf
# ---------------------------------------------------------------------------
#
# STUFEN_PIDS["wikipedia"] ist die Vereinigung aller vier Feldkarten - richtig
# fuer die Frage "muss die Stufe ueberhaupt laufen?", aber viel zu grosszuegig
# fuer die Frage "was kommt bei DIESER Gruppe an". infobox.py wirft die
# Feldnamen einfach auf den Wikitext; welche greifen, entscheidet die Vorlage
# im Artikel:
#
#   Elemente     tragen {{Infobox Chemisches Element}} - die ergiebigste
#   Verbindungen tragen {{Infobox Chemikalie}} - Dichte, Schmelz-, Siedepunkt,
#                CAS
#   Minerale     tragen {{Infobox Mineral}} - dort greifen nur 'Dichte' und
#                'Mohshaerte', weil diese beiden Felder zufaellig genauso
#                heissen wie in der Elementinfobox. Gemessen am Lauf vom
#                2026-08-28 (650 Minerale): genau P2054 und P1088, sonst
#                nichts.
#
# Die englische Seite haengt dagegen am LAUF, nicht am Artikel:
# wikipedia_fallback_proposals bekommt im Elementlauf en_element (die
# Elementvorlage) und im Gruppenlauf en_title (die {{Chembox}}).
#
# Nur der Laengenausdehnungskoeffizient (P5672) haengt an der englischen
# Elementvorlage - also gibt es ihn ausserhalb des Elementlaufs gar nicht.
WP_SCHLUESSEL = {
    "de-element": ({k for k, _ in WIKIPEDIA_DE_FIELDS.values()}
                   | {"cas_number", "crystal_system", "magnetism"}),
    "de-chemikalie": ({k for k, _ in WIKIPEDIA_DE_CHEM_FIELDS.values()}
                      | {"melting_point", "boiling_point", "cas_number"}),
    "de-mineral": {"density", "mohs_hardness"},
    "en-element": ({k for k, _ in WIKIPEDIA_NUMERIC_FIELDS.values()}
                   | {"density", "electrical_resistivity", "crystal_system",
                      "linear_thermal_expansion"}),
    "en-chembox": ({k for k, _, _ in CHEMBOX_FIELDS.values()}
                   | {"cas_number"}),
}

# Welche Vorlage tragen die Artikel dieser Grundgesamtheit? Die einzige
# Zuordnung hier, die nicht aus dem Code folgt - sie ist an den Laeufen vom
# 2026-08-28 abgelesen (Minerale: nur P2054/P1088; Legierungen: Dichte, CAS,
# Schmelz- und Siedepunkt aus de und en, dazu vereinzelt Mohshaerte).
WP_JE_POPULATION = {
    "minerale": ["de-mineral"],
    "oxide": ["de-chemikalie", "en-chembox"],
    "carbide": ["de-chemikalie", "en-chembox"],
    "polymer": ["de-chemikalie", "en-chembox"],
    "magnetwerkstoffe": ["de-chemikalie", "en-chembox"],
    "keramik": ["de-chemikalie", "en-chembox"],
    "glas": ["de-chemikalie", "en-chembox"],
    "legierungen": ["de-chemikalie", "de-mineral", "en-chembox"],
    "benannte-legierungen": ["de-chemikalie", "de-mineral", "en-chembox"],
    "metalle": ["de-element", "en-element"],
    "periodensystem": ["de-element", "en-element"],
}

# Kennt der Benchmark die Gruppe nicht (--population subtree, --root ...),
# steht die Vorlage nicht fest. Dann werden alle im jeweiligen Lauf
# erreichbaren ausgewiesen - lieber zu viel als eine falsche Einschraenkung.
WP_UNBEKANNT = {
    "gruppe": ["de-element", "de-chemikalie", "de-mineral", "en-chembox"],
    "elemente": ["de-element", "en-element"],
}

# Welcher Lauf faehrt welche Stufen? Reihenfolge wie im Lauf; "WP" wird durch
# die Vorlagen der Grundgesamtheit ersetzt.
LAEUFE = {
    "gruppe": ("Gruppenlauf (--group)",
               ["cod", "mp", "nist", "WP", "punktgruppe", "formel"]),
    "elemente": ("Elementlauf (--periodic-table)",
                 ["cod", "mp", "nist", "WP"]),
}


def lauf_modus(population: str) -> str:
    """Welcher materialswiki-Lauf gehoert zu dieser Grundgesamtheit?

    lauf.py bildet beides aufeinander ab: die Werkstoffgruppen laufen ueber
    --group, 'metalle' und 'periodensystem' ueber --periodic-table. Der
    Default 'subtree' hat keinen eigenen Lauf; er wird wie ein Gruppenlauf
    behandelt, weil ihn dieselben Stufen bedienen wuerden.
    """
    return "elemente" if population in ("metalle", "periodensystem") else "gruppe"


def stufen_des_laufs(population: str) -> list:
    """Die Stufen, die fuer diese Grundgesamtheit wirklich etwas liefern."""
    modus = lauf_modus(population)
    wp = WP_JE_POPULATION.get(population, WP_UNBEKANNT[modus])
    stufen = []
    for stufe in LAEUFE[modus][1]:
        stufen += wp if stufe == "WP" else [stufe]
    return stufen


def stufen_pids(stufe: str) -> frozenset:
    """Die PIDs einer Stufe.

    Die vier Netz-Stufen stehen in STUFEN_PIDS, die Ableitungen und die
    einzelnen Infoboxen werden ueber PROPERTY_MAP aufgeloest.
    """
    if stufe in ABLEITUNGS_SCHLUESSEL:
        schluessel = ABLEITUNGS_SCHLUESSEL[stufe]
    elif stufe in WP_SCHLUESSEL:
        schluessel = WP_SCHLUESSEL[stufe]
    else:
        return STUFEN_PIDS[stufe]
    return frozenset(PROPERTY_MAP[k]["pid"] for k in schluessel)


def quellen_je_property(population: str) -> dict:
    """{PID: [Quellenkuerzel, ...]} fuer die Stufen, die dieser Lauf faehrt.

    Eine Property kann aus mehreren Quellen kommen (das Kristallsystem aus
    COD, MP und den Infoboxen); im Lauf gewinnt die zuerst laufende Stufe,
    hier werden alle ausgewiesen. Eingeklammert steht, was erst ein Schalter
    einschaltet.
    """
    out = {}
    for stufe in stufen_des_laufs(population):
        kuerzel = QUELLEN[stufe][0]
        if stufe in DEFAULT_AUS:
            kuerzel = f"({kuerzel})"
        for pid in stufen_pids(stufe):
            out.setdefault(pid, []).append(kuerzel)
    return out


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

def build_population(args) -> tuple:
    """(Muster der Grundgesamtheit, {Bezeichnung: Teilmuster zum Zaehlen}).

    Zwei Modi: der Subtree unter einer Wurzel (Default) oder das
    Periodensystem. Beim Periodensystem ist die Aufteilung in Instanzen und
    Unterklassen sinnlos - die Elemente sind ausnahmslos Instanzen.
    """
    if args.population in WERKSTOFFGRUPPEN:
        # Muster kommt aus materialswiki, damit Benchmark und Vorschlags-
        # lauf garantiert dieselbe Grundgesamtheit meinen.
        pattern = WERKSTOFFGRUPPEN[args.population]["pattern"]
        return pattern, {"gesamt": pattern}
    if args.population == "metalle":
        nichtmetalle = ", ".join(f'"{s}"' for s in sorted(NICHTMETALLE))
        pattern = METALLE_PATTERN.format(max_z=args.max_z,
                                         nichtmetalle=nichtmetalle)
        return pattern, {"gesamt": pattern}
    if args.population == "periodensystem":
        pattern = PERIODENSYSTEM_PATTERN.format(max_z=args.max_z)
        return pattern, {"gesamt": pattern}
    pattern = POPULATION_PATTERN.format(root=args.root)
    return pattern, {
        "instanzen": f"?i wdt:P31/wdt:P279* wd:{args.root}",
        "unterklassen": f"?i wdt:P279* wd:{args.root}",
        "gesamt": pattern,
    }


def count_population(teilmengen: dict) -> dict:
    counts = {}
    for key, pattern in teilmengen.items():
        rows = sparql(f"SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE {{ {pattern} }}")
        counts[key] = int(rows[0]["n"]["value"])
    return counts


def count_filled(population: str, pids: list, chunk: int = 60) -> dict:
    """{pid: Anzahl Items der Grundgesamtheit mit dieser Aussage}.

    Properties ohne Treffer fehlen im GROUP BY und werden auf 0 vorbelegt.
    In Bloecken abgefragt, damit die Query bei langen Listen nicht ins
    Timeout des Query-Service laeuft.
    """
    filled = {pid: 0 for pid in pids}
    for i in range(0, len(pids), chunk):
        values = " ".join(f"wdt:{p}" for p in pids[i:i + chunk])
        rows = sparql(f"""SELECT ?p (COUNT(DISTINCT ?i) AS ?n) WHERE {{
  {population}
  VALUES ?p {{ {values} }}
  ?i ?p ?v .
}} GROUP BY ?p""")
        for row in rows:
            filled[row["p"]["value"].rsplit("/", 1)[-1]] = int(row["n"]["value"])
    return filled


def best_covered(population: str, pids: list, limit: int = 10) -> list:
    values = " ".join(f"wdt:{p}" for p in pids)
    return sparql(f"""SELECT ?i ?iLabel (COUNT(DISTINCT ?p) AS ?n) WHERE {{
  {population}
  VALUES ?p {{ {values} }}
  ?i ?p ?v .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}} GROUP BY ?i ?iLabel ORDER BY DESC(?n) LIMIT {limit}""")


# ---------------------------------------------------------------------------
# Bericht
# ---------------------------------------------------------------------------

def build_rows(sections: dict, meta: dict, filled: dict, total: int,
               population: str = "subtree") -> list:
    # Welche Properties kann materialswiki bedienen - und woher? Das haengt
    # an der Grundgesamtheit: der Elementlauf kennt die beiden Ableitungen
    # nicht, und welche Wikipedia-Vorlage greift, entscheidet die Gruppe.
    pid_to_key = {info["pid"]: key for key, info in PROPERTY_MAP.items()}
    quellen = quellen_je_property(population)
    # MP_FIELD_MAP bildet Feldpfad -> (Schluessel, Faktor) ab; hier zaehlt
    # nur der Schluessel.
    mit_mp_pfad = {schluessel for schluessel, _ in MP_FIELD_MAP.values()}

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
                # Alle Quellen, die diese Property in DIESEM Lauf liefern
                # koennen - leer, wenn keine Stufe sie abfragt.
                "quellen": ", ".join(quellen.get(pid, [])),
                "mp_quelle": "ja" if key in mit_mp_pfad else "nein",
            })
    return rows


def print_report(titel: str, population: dict, rows: list,
                 gruppe: str = "subtree") -> None:
    total = population["gesamt"]
    modus = lauf_modus(gruppe)
    print()
    print(f"Grundgesamtheit: {titel}")
    print(f"Vorschlagslauf:  {LAEUFE[modus][0]}")
    if "instanzen" in population:
        print(f"  Instanzen (P31/P279*)          {population['instanzen']:>7}")
        print(f"  Unterklassen (P279*)           {population['unterklassen']:>7}")
        print(f"  ausgewertet (Vereinigung)      {total:>7}")
    else:
        print(f"  ausgewertet                    {total:>7}")

    for section in dict.fromkeys(r["abschnitt"] for r in rows):
        teil = sorted((r for r in rows if r["abschnitt"] == section),
                      key=lambda r: -r["gefuellt"])
        belegt = sum(1 for r in teil if r["gefuellt"])
        print()
        print(f"== {section}  ({len(teil)} Properties, {belegt} davon belegt)")
        kopf = (f"  {'PID':<8}{'Label':<34}{'Typ':<12}"
                f"{'gefuellt':>9}{'Anteil':>9}  materialswiki")
        print(kopf)
        print("  " + "-" * (len(kopf) - 2))
        for r in teil:
            marker = "<- " + r["in_property_map"] if r["in_property_map"] else ""
            if r["quellen"]:
                marker += f" [{r['quellen']}]"
            print(f"  {r['pid']:<8}{r['label'][:33]:<34}{r['datatype'][:11]:<12}"
                  f"{r['gefuellt']:>9}{r['anteil_prozent']:>8.2f}%  {marker}")

    print()
    leer = [r for r in rows if not r["gefuellt"]]
    print(f"Zusammenfassung: {len(rows)} Properties, "
          f"{len(rows) - len(leer)} mindestens einmal belegt, "
          f"{len(leer)} komplett leer.")
    belegbar = [r for r in rows if r["quellen"]]
    if belegbar:
        print("Von materialswiki belegbar - und aus welcher Quelle:")
        for r in sorted(belegbar, key=lambda r: r["luecke"], reverse=True):
            print(f"  {r['pid']} {r['label']:<28} {r['gefuellt']:>6} von "
                  f"{total} gefuellt  ->  {r['luecke']} offen"
                  f"   [{r['quellen']}]")
        # Wie viel traegt jede einzelne Stufe bei? Summen sind hier sinnlos
        # (eine Property haengt an mehreren Quellen), gezaehlt wird deshalb
        # je Quelle die Zahl der Properties.
        gefahren = stufen_des_laufs(gruppe)
        print()
        print(f"Quellen, die der {LAEUFE[modus][0]} bei dieser "
              f"Grundgesamtheit abfragt:")
        for stufe in gefahren:
            kuerzel, text = QUELLEN[stufe]
            schalter = DEFAULT_AUS.get(stufe)
            if schalter:
                kuerzel = f"({kuerzel})"
                text += f" - nur mit {schalter}, Default aus"
            n = sum(1 for r in belegbar
                    if kuerzel in r["quellen"].split(", "))
            print(f"  {kuerzel:<11}{text:<50}{n:>3} "
                  f"{'Property' if n == 1 else 'Properties'}")
        nicht_gefahren = [QUELLEN[st][0] for st in QUELLEN
                          if st not in gefahren]
        if nicht_gefahren:
            print(f"  nicht in diesem Lauf: {', '.join(nicht_gefahren)}")
        if gruppe not in WP_JE_POPULATION:
            print("  Wikipedia-Vorlage fuer diese Grundgesamtheit nicht "
                  "hinterlegt - alle erreichbaren ausgewiesen")
    print()


def _md_zelle(wert) -> str:
    return (str(wert if wert is not None else "")
            .replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r\n", " ").replace("\n", "<br>").replace("\r", " "))


def write_markdown(rows: list, path: str) -> None:
    spalten = list(rows[0].keys())
    with open(path, "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(spalten) + " |\n")
        f.write("|" + "|".join(["---"] * len(spalten)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(_md_zelle(row.get(s, "")) for s in spalten)
                    + " |\n")
    print(f"Markdown-Tabelle geschrieben nach: {path}", file=sys.stderr)


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
    parser.add_argument("--md", default=None,
                        help="Ergebnistabelle zusaetzlich als Markdown-Datei")
    parser.add_argument("--top", type=int, default=10,
                        help="Anzahl der am besten belegten Items (0 = aus)")
    parser.add_argument("--population",
                        choices=(["subtree", "metalle", "periodensystem"]
                                 + sorted(WERKSTOFFGRUPPEN)),
                        default="subtree",
                        help="Grundgesamtheit: 'subtree' = Instanzen und "
                             "Unterklassen unter --root (Default), "
                             "'legierungen' = die Legierungen unter Q37756 "
                             "ohne den falsch modellierten Metalle-Zweig, "
                             "'metalle' = die metallischen und halbmetallischen "
                             "Elemente, also genau die Auswahl, die "
                             "materialswiki bearbeitet, "
                             "'periodensystem' = alle chemischen Elemente "
                             "(bei den letzten beiden wird --root nicht "
                             "verwendet)")
    parser.add_argument("--max-z", type=int, default=DEFAULT_MAX_Z,
                        help=f"nur mit --population periodensystem: hoechste "
                             f"Ordnungszahl (Default {DEFAULT_MAX_Z}; darueber "
                             f"fuehrt Wikidata nur hypothetische Elemente)")
    parser.add_argument("--no-extra", action="store_true",
                        help="die fest ergaenzten Properties weglassen "
                             f"({', '.join(p for v in EXTRA_SECTIONS.values() for p in v)})")
    args = parser.parse_args(argv)

    sections = fetch_project_properties(args.sections, args.offline)
    aus_projekt = sum(len(v) for v in sections.values())

    # Nach dem Snapshot-Schreiben ergaenzen, damit der Snapshot die
    # Projektseite unvermischt abbildet - und NUR, was dort noch fehlt.
    # Die Ergaenzung loest sich damit von selbst auf, sobald die Projektseite
    # eine Property uebernimmt: P231 stand am 2026-08-16 noch nicht auf der
    # Seite und steht seit demselben Tag unter "Chemical". Ohne diese Pruefung
    # erschiene sie in zwei Abschnitten und die Zusammenfassung zaehlte 66
    # statt 65 Properties.
    uebernommen = []
    if not args.no_extra:
        schon_da = {p for v in sections.values() for p in v}
        for abschnitt, extra_pids in EXTRA_SECTIONS.items():
            fehlend = [p for p in extra_pids if p not in schon_da]
            uebernommen += [p for p in extra_pids if p in schon_da]
            if fehlend:
                sections[abschnitt] = fehlend

    pids = list(dict.fromkeys(p for v in sections.values() for p in v))
    print(f"{aus_projekt} Properties aus {len(args.sections)} Abschnitten von "
          f"[[{PROJECT_PAGE}]]"
          + (f" + {len(pids) - aus_projekt} fest ergaenzt"
             if len(pids) > aus_projekt else "")
          + (f"; {', '.join(uebernommen)} steht inzwischen selbst auf der "
             f"Projektseite und wird nicht mehr ergaenzt" if uebernommen else ""),
          file=sys.stderr)

    population_pattern, teilmengen = build_population(args)
    titel = {
        **{g: i["beschreibung"] for g, i in WERKSTOFFGRUPPEN.items()},
        "metalle": (f"Metalle und Halbmetalle (Elemente ausser Nichtmetallen, "
                    f"Z <= {args.max_z})"),
        "periodensystem": f"Periodensystem (chemische Elemente, Z <= {args.max_z})",
    }.get(args.population, f"unterhalb von {args.root}")

    meta = fetch_property_meta(pids)
    population = count_population(teilmengen)
    filled = count_filled(population_pattern, pids)
    rows = build_rows(sections, meta, filled, population["gesamt"],
                      args.population)
    print_report(titel, population, rows, args.population)

    if args.top:
        print(f"Am besten belegte Items (max. {len(pids)} Aussagen):")
        for b in best_covered(population_pattern, pids, args.top):
            qid = b["i"]["value"].rsplit("/", 1)[-1]
            print(f"  {b['n']['value']:>3}/{len(pids)}  {qid:<12} "
                  f"{b['iLabel']['value']}")
        print()

    if args.md:
        write_markdown(rows, args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
