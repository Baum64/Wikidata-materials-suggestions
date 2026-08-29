"""Gemeinsame Wikidata-Zugriffsschicht der beiden Skripte in diesem Ordner.

visualisierung.py und "Vorschläge generieren.py" fragen beide denselben
Query-Service ab, buendeln ihre VALUES-Bloecke gleich und trugen bis
2026-08-29 jeweils eine eigene Kopie von HTTP-Retry, SPARQL-POST und
QID-Zerlegung. Das steht jetzt hier einmal.

Die HTTP-Schicht kommt aus materialswiki.netz - dem einen Einstiegspunkt des
Repos mit Drosselung JE GEGENSTELLE. So teilen sich alle drei Werkzeuge
dieselbe Ruecksicht gegenueber Wikimedia, und die Tests sperren mit einer
einzigen Attrappe den gesamten Netzzugriff.

Bewusst nur die MECHANIK: Endpunkte, Retry, das Zerlegen einer Bindung, das
Stueckeln langer QID-Listen. Fachliche Konstanten (welche QID "Legierung"
ist, welche Wurzel geprueft wird) bleiben in den Skripten.
"""

import os
import sys

# Repo-Wurzel in den Pfad: materialswiki liegt dort. Gleiches Vorgehen wie in
# den beiden Skripten selbst.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from materialswiki import netz  # noqa: E402
from materialswiki.konfiguration import (  # noqa: E402
    WIKIDATA_API, WIKIDATA_SPARQL,
)

ENWIKI_API = "https://en.wikipedia.org/w/api.php"

# Weiterreichen, damit die Skripte nur dieses Modul importieren muessen.
request_with_retry = netz.request_with_retry


# materialswiki.netz setzt an ALLEN Anfragen "Content-Type: application/json"
# (die MP-API braucht das). Der SPARQL-POST ist aber formcodiert - mit dem
# JSON-Header antwortet der Query-Service 405. Also hier ueberschreiben und
# die sprechende Kennung von netz beibehalten.
_SPARQL_HEADERS = {**netz.HEADERS,
                   "Content-Type": "application/x-www-form-urlencoded"}


def sparql_json(query: str) -> dict:
    """Rohe SPARQL-Antwort per POST - GET reisst bei laengeren VALUES-Bloecken
    die URL. Fuer ASK-Abfragen, die den Schluessel 'boolean' brauchen."""
    resp = request_with_retry("POST", WIKIDATA_SPARQL, headers=_SPARQL_HEADERS,
                              data={"query": query, "format": "json"})
    resp.raise_for_status()
    return resp.json()


def sparql(query: str) -> list:
    """Die Bindungen einer SELECT-Abfrage - der Normalfall."""
    return sparql_json(query).get("results", {}).get("bindings", [])


def ask(query: str) -> bool:
    """Das Ergebnis einer ASK-Abfrage."""
    return sparql_json(query).get("boolean", False)


def qid(binding: dict, feld: str) -> str:
    """Aus einer SPARQL-Bindung die nackte Q-Nummer eines Feldes."""
    return binding[feld]["value"].rsplit("/", 1)[-1]


def api_get(url: str, params: dict, timeout: int = 60) -> dict:
    """GET gegen eine MediaWiki-Action-API, JSON zurueck."""
    resp = request_with_retry("GET", url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def in_bloecken(werte, block: int):
    """`werte` in Listen von hoechstens `block` Elementen - fuer VALUES.

    Eine Abfrage je Block statt je Item war der groesste Hebel der Laufzeit;
    die Blockgroesse haengt an der Gegenstelle (SPARQL vertraegt ~200,
    wbgetentities nimmt hoechstens 50)."""
    werte = list(werte)
    for i in range(0, len(werte), block):
        yield werte[i:i + block]


def werte_klausel(qids) -> str:
    """Ein `wd:Q1 wd:Q2 ...`-Rumpf fuer einen VALUES-Block."""
    return " ".join(f"wd:{q}" for q in qids)


def hole_labels_api(qids: list, sprachen: str = "de|en",
                    block: int = 50) -> dict:
    """{qid: Bezeichnung} ueber wbgetentities, erste Sprache gewinnt.

    Getrennt vom Label-Service der Abfrage: wbgetentities liefert die
    Bezeichnung ohne den teuren SERVICE-Block und nimmt bis zu 50 IDs."""
    reihenfolge = sprachen.split("|")
    labels = {}
    for teil in in_bloecken(qids, block):
        daten = api_get(WIKIDATA_API, {
            "action": "wbgetentities", "ids": "|".join(teil),
            "props": "labels", "languages": sprachen,
            "format": "json", "formatversion": "2",
        })
        for q, eintrag in daten.get("entities", {}).items():
            bez = eintrag.get("labels", {})
            labels[q] = next((bez[s]["value"] for s in reihenfolge if s in bez),
                             q)
    return labels
