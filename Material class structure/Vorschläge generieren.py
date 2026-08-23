"""
P279-Struktur der Werkstoffe pruefen und eine gestaffelte Empfehlung entwerfen
=============================================================================

Der Benchmark in benchmark/ misst, welche MESSWERTE an den Werkstoff-Items
fehlen. Dieses Skript misst etwas anderes: ob die Items ueberhaupt richtig
EINGEHAENGT sind - also wie P279 (Unterklasse von) unterhalb der Werkstoffe
verwendet wird, wo die Kante fehlt, wo sie doppelt ist, wo sie verkehrt herum
zeigt und wo statt P279 faelschlich P31 steht.

Hier sind zwei Ansaetze zusammengefuehrt: die Strukturpruefungen auf dem
P279-Graphen und die Label-Heuristik aus dem frueheren
material_subclass_check.py, das darin aufgegangen ist.

Warum ueberhaupt? Aus dem Vorlauf dieses Repos sind drei Befunde bekannt:

  * Wikidata fuehrt "Metall" (Q11426) als UNTERKLASSE von "Legierung"
    (Q37756) - fachlich verkehrt herum. Dadurch haengt jedes Metall samt
    Isotopen unter "Legierung"; materialswiki muss das mit einem Filter
    ausgleichen (LEGIERUNG_OHNE_ELEMENTE). Der Filter kuriert das Symptom,
    die Kante bleibt.
  * Die Gruppierung der benannten Legierungen nach Basismetall, die
    [[en:List of named alloys]] vorgibt, existiert in Wikidata so nicht.
  * [[Wikidata:WikiProject Materials/Materials]] wuenscht eine differenzierte
    Einhaengung (Material -> Metallic material -> Alloy -> Ferrous alloy ->
    Steel -> Alloy steel -> ...). Die laesst sich aus dem Basismetall allein
    NICHT ableiten.

Die Ausgabe: EINE gestaffelte Empfehlung
----------------------------------------
Es entsteht genau eine Datei, und sie ist zum Durchsehen am Bildschirm
gebaut. Vier Stufen, sortiert nach BEWEISKRAFT - nicht nach Wichtigkeit.
Der Leser kann jederzeit aufhoeren; das Gepruefte bleibt gueltig.

  Stufe 1  MECHANISCH SICHER      folgt allein aus dem Graphen und behauptet
                                  nichts. Als einzige ausfuehrbar.
  Stufe 2  STRUKTURELL BEGRUENDET aus dem Graphen abgeleitet, aber mit einer
                                  fachlichen Entscheidung davor.
  Stufe 3  HEURISTISCH            aus Bezeichnungen geraten. Fehltreffer
                                  sind hier die Regel.
  Stufe 4  NUR MELDUNG            beschreibt die Lage, fordert nichts.

Ab Stufe 2 traegt jeder Entwurf die Marke '#!'. QuickStatements liest sie als
Kommentar; wer eine Zeile freigibt, loescht die zwei Zeichen. Alle uebrigen
Zeilen beginnen mit '#'. Die Datei laesst sich dadurch jederzeit als GANZES
nach QuickStatements kopieren, ohne dass eine ungepruefte Zeile zur Aussage
wird - und im Editor findet "#!" genau die Entwuerfe.

Die zehn Pruefungen
-------------------
  1. kennzahlen        Wie wird P279 in der Grundgesamtheit ueberhaupt
                       benutzt: P279, P31, beides, keines; Mehrfacheltern;
                       Tiefe.
  2. redundant         Item hat P279 auf A UND auf B, wobei A ueber P279
                       ohnehin bei B landet -> ENTFERNEN.        [Stufe 1]
                       Aber nur, wenn der Ersatzpfad selbst haelt: laeuft er
                       ueber eine Kante aus Pruefung 4, wird der Befund zu
                       'redundant-unsicher'.                     [Stufe 2]
  3. instanz-als-klasse  Item hat P31 auf eine Werkstoffklasse, ist aber
                       selbst Oberklasse von etwas.              [Stufe 2]
  4. verkehrt          Kante n -> p, obwohl unter n mehr haengt als unter p
                       ohne n - der Metall/Legierung-Fall, generisch
                       gefasst. Siehe verkehrt_kandidaten().     [Stufe 2]
  5. zyklus            Eine Klasse ist ueber P279 ihre eigene Oberklasse.
                       Immer ein Fehler, nie automatisch aufloesbar. [Stufe 2]
  6. zusammensetzung   Der Name nennt die Zusammensetzung ("Nickel brass
                       (70% Copper, 18% Zinc, 12% Nickel)"). Das Element mit
                       dem groessten Anteil IST das Basismetall, damit steht
                       die Legierungsklasse fest - hier Kupferlegierung.
                       Diese Auswertung raet nicht, sie rechnet.  [Stufe 3]
  7. zu-allgemein      Item haengt direkt unter einer sehr allgemeinen
                       Klasse, obwohl seine Bezeichnung eine speziellere
                       nennt. Aus material_subclass_check.py uebernommen,
                       mit drei Filtern, ohne die es nicht traegt - siehe
                       den Block bei ALLGEMEINE_WURZELN.         [Stufe 3]
  8. ohne-einordnung   Benannte Legierung ohne jeden Pfad zu "Legierung".
                       Wo es fuer das Basismetall eine Klasse GIBT, wird sie
                       vorgeschlagen.                            [Stufe 3]
  9. p31-neben-p279    Item haengt direkt unter einer allgemeinen Klasse und
                       hat zusaetzlich P31. Nur Meldung - siehe
                       pruefe_p31_neben_p279() dazu, warum kein Entwurf
                       daraus wird.                              [Stufe 4]
 10. parallelzweig     Item ohne P279*-Pfad zu "material" (Q214609). Kein
                       Fehler (P186 erlaubt mehrere gleichrangige Werttypen,
                       siehe visualisierung.py daneben).        [Stufe 4]

Alle Pruefungen bleiben in der Werkstoff-Ecke - unterhalb von material
(Q214609) oder Legierung (Q37756), plus die Grundgesamtheit selbst. Das ist
keine Bequemlichkeit: die P279-Huelle nach oben endet zwangslaeufig in der
obersten Ontologie, und dort finden dieselben Pruefungen dieselben Fehler bei
"Begriff", "Typ" oder "Kunstgewerbe". Die Befunde waeren richtig und trotzdem
nicht unsere Sache - eine dort eingespielte Aenderung trifft hunderttausende
Items ausserhalb jedes Werkstoffbezugs.

Drei Sperren gegen den eigenen Unsinn
-------------------------------------
Die Pruefungen widersprechen sich, wenn man sie einzeln laufen laesst. Das
faellt beim Bauen nicht auf, beim Einspielen schon:

  * Eine Redundanz, deren Ersatzpfad ueber eine beanstandete Kante laeuft,
    ist keine. Sonst entfernt man die gute Kante und repariert spaeter die
    schlechte - und das Item haengt nirgends mehr.
  * Eine beanstandete Klasse taugt nicht als ZIEL einer Umhaengung. Sonst
    schlaegt dasselbe Skript vor, ein Item unter eine Klasse zu haengen,
    deren Platz es zwei Stufen weiter oben in Frage stellt.
  * Chemische Elemente (P1086) taugen nie als Ziel. Sie stehen nur wegen der
    falschen Metall/Legierung-Kante im Kandidatenpool.

Ausgabe
-------
  p279_empfehlung_<Zeitstempel>.txt   die gestaffelte Empfehlung
  --csv <pfad>                        zusaetzlich, optional

Aufruf
------
  python "Material class structure/Vorschläge generieren.py"
  python "Material class structure/Vorschläge generieren.py" --population legierungen
  python "Material class structure/Vorschläge generieren.py" --pruefungen redundant verkehrt
  python "Material class structure/Vorschläge generieren.py" --tiefe 3 --beleg beides
  python "Material class structure/Vorschläge generieren.py" --vorsichtig   # nichts einspielbar
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys
import time
from typing import Optional

import requests

# Repo-Wurzel in den Pfad: konfig.py und materialswiki liegen dort. Dasselbe
# Vorgehen wie in benchmark/benchmark.py - die Grundgesamtheiten werden
# importiert, nicht kopiert, sonst driften Benchmark und Vorschlagslauf
# auseinander.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import konfig  # noqa: E402
from materialswiki.cli import (  # noqa: E402
    LEGIERUNG_PATTERN, LEGIERUNG_QID, fetch_named_alloys,
)

try:
    import networkx as nx
except ImportError:  # pragma: no cover - Hinweis ist hilfreicher als Traceback
    raise SystemExit(
        "networkx fehlt. Installation: pip install -r requirements.txt")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
# Kontaktadresse aus .env - siehe .env.beispiel.
USER_AGENT = ("MaterialsWikidataStructureBot/0.1 "
              f'(mailto:{konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")})')
HEADERS = {"User-Agent": USER_AGENT}

MATERIAL_QID = "Q214609"        # material
METALL_WERKSTOFF_QID = "Q1924900"  # metallischer Werkstoff

SUBTREE_PATTERN = (
    "{{ ?i wdt:P31/wdt:P279* wd:{root} }} UNION {{ ?i wdt:P279* wd:{root} }}"
)

# Grundgesamtheiten. 'legierungen' kommt woertlich aus materialswiki, damit
# dieses Skript und der Vorschlagslauf garantiert dieselbe Menge meinen.
POPULATIONEN = {
    "legierungen": {
        "pattern": LEGIERUNG_PATTERN,
        "beschreibung": "Legierungen (Q37756, ohne Elemente und Isotope)",
    },
    "benannte-legierungen": {
        "pattern": None,  # kommt aus der Wikipedia-Liste, nicht aus SPARQL
        "beschreibung": "benannte Legierungen aus [[en:List of named alloys]]",
    },
    "metallischer-werkstoff": {
        "pattern": SUBTREE_PATTERN.format(root=METALL_WERKSTOFF_QID),
        "beschreibung": "unterhalb von metallischer Werkstoff (Q1924900)",
    },
    "material": {
        "pattern": SUBTREE_PATTERN.format(root=MATERIAL_QID),
        "beschreibung": "unterhalb von material (Q214609)",
    },
}

PRUEFUNGEN = ["kennzahlen", "zyklus", "redundant", "verkehrt",
              "instanz-als-klasse", "zusammensetzung", "zu-allgemein",
              "ohne-einordnung", "p31-neben-p279", "parallelzweig"]

# ---------------------------------------------------------------------------
# Label-Heuristik: haengt ein Item zu allgemein?
# ---------------------------------------------------------------------------
#
# Uebernommen aus material_subclass_check.py, das in dieses Skript aufgegangen
# ist. Die Idee: ein Item, das DIREKT unter einer sehr allgemeinen Klasse
# haengt, traegt seine eigentliche Oberklasse oft im Namen ("Formgedaechtnis-
# KERAMIK" unter "Material", obwohl es "Keramik" gibt).
#
# Die Idee traegt - aber nur mit drei Filtern. Ohne sie war die Trefferquote
# unbrauchbar (gemessen 2026-08-23 an 325 Vorschlaegen):
#
#   * 42 % zielten auf Q16829513, ein ZWEITES Item namens "material", das
#     selbst unter Q214609 haengt. Formal eine Unterklasse, sachlich ein
#     Synonym - keine Spezialisierung. -> ALLGEMEINE_BEZEICHNUNGEN
#   * 60 % stuetzten sich allein auf die Beschreibung. Dass dort das Wort
#     "material" vorkommt, sagt nichts ueber die Klasse. -> --beleg
#   * Reine Substring-Zufaelle: "Mater" (Q5460003, flong) traf in
#     "MATERial", "compo" in "COMPOsite", "Stoff" in "InhaltsSTOFF".
#     -> Wortgrenzen statt roher Substring-Suche
ALLGEMEINE_WURZELN = {
    MATERIAL_QID: "material",
    LEGIERUNG_QID: "Legierung",
    METALL_WERKSTOFF_QID: "metallischer Werkstoff",
}

# Bezeichnungen, die als ZIEL nichts taugen: Synonyme der Wurzel selbst.
# Ein Vorschlag "haeng es unter 'material' statt unter 'material'" ist keiner.
ALLGEMEINE_BEZEICHNUNGEN = {
    "material", "materials", "werkstoff", "werkstoffe", "stoff", "substanz",
    "substance", "matter", "medium", "mater", "compo", "masse", "mass",
    "produkt", "product", "gegenstand", "objekt", "object", "ware",
}

# Mindestlaenge einer Bezeichnung, damit sie als Suchbegriff taugt.
MIN_LABEL_LEN = 4

# ---------------------------------------------------------------------------
# Zusammensetzung aus dem Namen
# ---------------------------------------------------------------------------
#
# Viele Items tragen ihre Legierungszusammensetzung im Namen:
#   "Nickel brass (70% Copper, 18% Zinc, 12% Nickel)"
# Daraus folgt das Basismetall zwingend - es ist das Element mit dem groessten
# Anteil - und damit die Legierungsklasse: hier Kupferlegierung.
#
# Das ist die belastbarste Namensauswertung im ganzen Skript: sie raet nicht,
# sie RECHNET. Deshalb steht sie in Stufe 3 vor der Namensaehnlichkeit.
#
# Zwei Schreibweisen kommen vor, beide muessen erkannt werden:
#   "90% Copper"     - Anteil zuerst
#   "Aluminium 98%"  - Element zuerst
ZUSAMMENSETZUNG_MUSTER = [
    re.compile(r"([\d]+(?:[.,]\d+)?)\s*%\s*([A-Za-z][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df-]{2,})"),
    re.compile(r"([A-Za-z][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df-]{2,})\s+([\d]+(?:[.,]\d+)?)\s*%"),
]

# Steht das im Namen, beschreiben die Prozente NUR die Auflage, nicht das
# Item: "Brass plated steel (Plating: 72.5% Copper, 27.5% Zinc)" ist kein
# Kupferwerkstoff, sondern Stahl mit Messingauflage. Hier waere die Regel
# falsch angewandt - deshalb wird gar nicht erst vorgeschlagen.
AUFLAGE_MARKER = ("plating:", "plating :", "coating:", "auflage:")

# Verbundbezeichnungen: die Prozente gelten fuer den ganzen Koerper, aber das
# Item ist ein Schichtverbund, keine Legierung. Vorschlag ja - aber mit
# ausdruecklicher Warnung, denn "Copper clad aluminium" ist kein
# Kupferwerkstoff, auch wenn Kupfer den groesseren Anteil haette.
VERBUND_MARKER = ("plated", "clad", "plattiert", "centre in", "center in",
                  "ring", "core")

# Ab welchem Abstand zum Zweitplatzierten das Basismetall als eindeutig gilt
# (in Prozentpunkten). Bei "48% Copper, 52% Aluminium" ist die Zuordnung
# eine Muenze auf der Kante, nicht ein Befund.
MIN_ABSTAND_PROZENT = 5.0

# Bis zu welcher Ebene unter der Wurzel der Kandidatenpool geholt wird.
# Groessenordnung unter material (gemessen 2026-08-23): Ebene 1 -> 392,
# Ebene 2 -> 5.787, Ebene 3 -> 14.974. Der VOLLE Baum hat 936.891 Items, ist
# in einer Abfrage nicht holbar - daran ist material_subclass_check.py mit
# 502 Bad Gateway abgebrochen - und waere als Pool auch nicht sinnvoll:
# weiter unten stehen einzelne Mineralien und Handelsprodukte, ein
# Substring-Treffer gegen die waere fast immer Zufall.
DEFAULT_TIEFE = 2

# ---------------------------------------------------------------------------
# Basismetall -> Legierungsklasse
# ---------------------------------------------------------------------------
#
# [[en:List of named alloys]] gruppiert nach Basismetall. Um daraus einen
# P279-Vorschlag zu machen, braucht es zu jedem Basismetall die passende
# KLASSE in Wikidata. Die wird gesucht, nicht geraten: ueber die englische
# Bezeichnung, und nur was selbst unter Q37756 haengt, zaehlt (siehe
# finde_basisklassen).
#
# Wikidata benennt diese Klassen uneinheitlich - mal "zinc alloy", mal
# "nickel-based alloy". Deshalb mehrere Muster je Basismetall.
KLASSEN_MUSTER = ["{b} alloy", "{b}-based alloy", "{b} based alloy",
                  "{b}-base alloy"]

# Abschnitte der Liste, die KEIN Basismetall benennen. Ohne diesen Filter
# landen "intermetallische Verbindung" und "list of brazing alloys" aus dem
# Abschnitt "See also" in der Grundgesamtheit und werden anschliessend als
# nicht klassifizierte Legierungen gemeldet - beides richtig und beides
# nutzlos, denn sie sollen dort gar nicht stehen.
# ("Alloys by base metal" ist die Einleitung, die nur die Basismetalle selbst
# auffuehrt; materialswiki filtert sie bereits beim Parsen.)
KEIN_BASISMETALL = {"See also", "References", "External links", "Notes",
                    "Further reading", "Bibliography", "Sources"}

# Die englische Wikipedia schreibt "Aluminum", Wikidata "aluminium". Ohne
# diese Umschrift findet die Suche die Klasse Q447725 nicht.
SCHREIBWEISEN = {
    "Aluminum": "aluminium",
    "Sulfur": "sulphur",
}

# Faelle, in denen das Muster nicht greift oder danebengreift. Jeder Eintrag
# braucht eine Begruendung - eine unbegruendete Zuordnung hier waere genau die
# fachliche Behauptung, die das Skript sonst vermeidet.
BASISKLASSEN_FEST = {
    # Amalgam IST die Quecksilberlegierung; "mercury alloy" gibt es nicht.
    "Mercury": ("Q182574", "amalgam"),
}

# Basismetalle, fuer die es in Wikidata KEINE Legierungsklasse gibt, obwohl
# die Projektseite eine verlangt. Nicht als Fehler melden, sondern als
# Luecke - anlegen kann dieses Werkzeug nichts.
#
# "Iron" ist der prominenteste Fall: [[Wikidata:WikiProject Materials]] nennt
# "Ferrous alloy" als Beispiel fuer die gewuenschte Zwischenklasse, in
# Wikidata existiert sie nicht (geprueft 2026-08-17). Q907347 "ferroalloy"
# ist NICHT dasselbe - das sind Vorlegierungen fuer die Stahlherstellung
# (Ferrochrom, Ferromangan), nicht die Oberklasse aller Eisenwerkstoffe.
BASISKLASSEN_BEKANNTE_LUECKE = {
    "Iron": "Ferrous alloy existiert nicht; Q907347 ferroalloy meint die "
            "Vorlegierung, nicht die Werkstoffklasse",
}


# ---------------------------------------------------------------------------
# HTTP mit Drosselung und Backoff
# ---------------------------------------------------------------------------

REQUEST_DELAY_SEC = 1.0
_LETZTE_ANFRAGE = 0.0


def request_with_retry(method: str, url: str, attempts: int = 5,
                       timeout: int = 120, **kwargs):
    """Einziger HTTP-Einstiegspunkt: drosselt auf 1 Anfrage/s und wiederholt
    bei 429/5xx.

    Der Query-Service antwortet unter Last sporadisch mit 429/502; ohne Retry
    reisst ein einzelner Ausfall den ganzen Lauf ab. Ein 504 nach ~60s ist
    dagegen kein transienter Fehler, sondern das Query-Timeout - dagegen hilft
    nur eine kleinere Abfrage (siehe hole_p279_huelle).
    """
    global _LETZTE_ANFRAGE
    delay = 3.0
    for versuch in range(1, attempts + 1):
        wartezeit = REQUEST_DELAY_SEC - (time.monotonic() - _LETZTE_ANFRAGE)
        if wartezeit > 0:
            time.sleep(wartezeit)
        _LETZTE_ANFRAGE = time.monotonic()
        try:
            resp = requests.request(method, url, headers=HEADERS,
                                    timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            if versuch == attempts:
                raise
            print(f"  {type(exc).__name__} - Versuch {versuch}/{attempts}",
                  file=sys.stderr)
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp
            if versuch == attempts:
                resp.raise_for_status()
            print(f"  HTTP {resp.status_code} - Versuch {versuch}/{attempts}, "
                  f"warte {delay:.0f}s", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"nicht erreichbar: {url}")


def sparql(query: str) -> list:
    """SPARQL per POST - GET reisst bei laengeren VALUES-Bloecken die URL."""
    resp = request_with_retry("POST", WIKIDATA_SPARQL,
                              data={"query": query, "format": "json"})
    return resp.json()["results"]["bindings"]


def qid_aus(binding: dict, feld: str) -> str:
    return binding[feld]["value"].rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Grundgesamtheit bestimmen
# ---------------------------------------------------------------------------

def hole_population_sparql(pattern: str, limit: Optional[int] = None) -> dict:
    """{qid: {'qid', 'label', 'basis'}} aus einem SPARQL-Muster."""
    grenze = f"LIMIT {limit}" if limit else ""
    zeilen = sparql(f"""
    SELECT DISTINCT ?i ?iLabel WHERE {{
      {pattern}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }} {grenze}
    """)
    return {qid_aus(b, "i"): {"qid": qid_aus(b, "i"),
                              "label": b.get("iLabel", {}).get("value", ""),
                              "basis": ""}
            for b in zeilen}


def hole_pruefliste(limit: Optional[int] = None) -> tuple:
    """({qid: eintrag}, [Titel ohne Item]) aus [[en:List of named alloys]].

    Die Aufloesung laeuft ueber die enwiki-Seiten-API MIT redirects=1, nicht
    ueber wbgetentities auf dem rohen Listentitel. Der Unterschied ist gross:
    die Liste verlinkt Weiterleitungen (Nitinol -> Nickel titanium, German
    silver -> Nickel silver, Heusler alloy -> Heusler compound, Lockalloy ->
    Beryllium-aluminium alloy), und ohne Aufloesung gelten deren Items als
    "nicht vorhanden". Genau daran sind im Vorlauf 25 Namen als itemlos
    gemeldet worden, die laengst ein Item haben.

    Ein Labelabgleich waere die falsche Alternative: bei "Mulberry" oder
    "Elektron" greift der munter daneben.
    """
    eintraege = [e for e in fetch_named_alloys()
                 if e["basis"] not in KEIN_BASISMETALL]
    if limit:
        eintraege = eintraege[:limit]
    nach_titel = {e["titel"]: e for e in eintraege}
    titel = list(nach_titel)

    # Schritt 1: Titel -> aufgeloester Titel -> QID, in Bloecken zu 50.
    ziel_von = {}   # Listentitel -> Titel nach Weiterleitung
    qid_von = {}    # aufgeloester Titel -> QID
    for start in range(0, len(titel), 50):
        block = titel[start:start + 50]
        daten = request_with_retry("GET", ENWIKI_API, params={
            "action": "query", "titles": "|".join(block), "redirects": 1,
            "prop": "pageprops", "ppprop": "wikibase_item",
            "format": "json", "formatversion": "2",
        }, timeout=60).json().get("query", {})
        for norm in daten.get("normalized", []):
            ziel_von[norm["from"]] = norm["to"]
        for weiter in daten.get("redirects", []):
            # Weiterleitungen koennen verkettet sein; erst am Ende aufloesen.
            ziel_von[weiter["from"]] = weiter["to"]
        for seite in daten.get("pages", []):
            wd = seite.get("pageprops", {}).get("wikibase_item")
            if wd:
                qid_von[seite["title"]] = wd

    def aufloesen(t: str, tiefe: int = 5) -> str:
        while t in ziel_von and tiefe:
            t, tiefe = ziel_von[t], tiefe - 1
        return t

    items, ohne_item = {}, []
    for t in titel:
        ziel = aufloesen(t)
        qid = qid_von.get(ziel)
        if not qid:
            ohne_item.append(t)
            continue
        # Zwei Listentitel koennen auf dasselbe Item zeigen (Weiterleitung
        # plus Zielartikel). Der erste gewinnt, das Basismetall des zweiten
        # geht dabei nicht verloren - es steht ohnehin im selben Abschnitt.
        items.setdefault(qid, {
            "qid": qid,
            "label": ziel,
            "basis": nach_titel[t]["basis"],
            "listentitel": t,
        })
    return items, sorted(ohne_item)


def hole_population(name: str, limit: Optional[int] = None) -> tuple:
    """(Items, Liste der Listennamen ohne Item)."""
    info = POPULATIONEN[name]
    if info["pattern"] is None:
        items, ohne_item = hole_pruefliste(limit)
    else:
        items, ohne_item = hole_population_sparql(info["pattern"], limit), []
    print(f"{len(items)} Items in Grundgesamtheit '{name}' - "
          f"{info['beschreibung']}.", file=sys.stderr)
    if ohne_item:
        print(f"  {len(ohne_item)} Listeneintraege haben KEIN Wikidata-Item "
              f"(auch nicht ueber die Weiterleitung): {', '.join(ohne_item)}",
              file=sys.stderr)
    return items, ohne_item


# ---------------------------------------------------------------------------
# Den P279-Graphen holen
# ---------------------------------------------------------------------------

def hole_p279_huelle(start: list, abwaerts: bool = False,
                     max_runden: int = 30, block: int = 200) -> list:
    """Alle P279-Kanten ober- bzw. unterhalb von `start`, als (kind, elter).

    In Runden statt in einer Abfrage: ein einzelnes
    "?i wdt:P279* ?c . ?c wdt:P279 ?p" ueber tausend Startitems laeuft
    zuverlaessig in das 60s-Limit des Query-Service (gemessen: die Kanten
    unterhalb von Legierung sind mit 25s knapp drin, unterhalb von material
    nicht mehr). Rundenweise bleibt jede Abfrage klein, und der Fortschritt
    ist sichtbar.

    Nach oben ist die Huelle klein - ueber "material" hinaus geht es nur noch
    ueber wenige sehr allgemeine Klassen weiter, die Runden versiegen von
    selbst. Nach unten ist sie gross (unter Legierung haengen 3244 Klassen,
    weil der falsch modellierte Metalle-Zweig die Elemente mitbringt), aber
    endlich. max_runden ist die Reissleine gegen einen Zyklus, den der
    Besuchsspeicher nicht ohnehin abfaengt.
    """
    # Aufwaerts sind die abgefragten Knoten die Kinder, abwaerts die Eltern.
    von, nach = ("p", "c") if abwaerts else ("c", "p")
    richtung = "Unterklassen" if abwaerts else "Oberklassen"

    kanten, gesehen, offen = [], set(start), list(start)
    for runde in range(1, max_runden + 1):
        if not offen:
            break
        neu = set()
        for i in range(0, len(offen), block):
            werte = " ".join(f"wd:{q}" for q in offen[i:i + block])
            for b in sparql(f"""SELECT ?c ?p WHERE {{
              VALUES ?{von} {{ {werte} }}
              ?c wdt:P279 ?p .
              FILTER(STRSTARTS(STR(?{nach}), "http://www.wikidata.org/entity/Q"))
            }}"""):
                kanten.append((qid_aus(b, "c"), qid_aus(b, "p")))
                weiter = qid_aus(b, nach)
                if weiter not in gesehen:
                    neu.add(weiter)
        print(f"  Runde {runde}: {len(offen)} Klassen abgefragt, "
              f"{len(neu)} neue {richtung}", file=sys.stderr)
        gesehen |= neu
        offen = sorted(neu)
    return kanten


def hole_p31_kanten(qids: list, block: int = 200) -> list:
    """(item, klasse)-Paare fuer P31 - fuer die Pruefung instanz-als-klasse."""
    kanten = []
    for i in range(0, len(qids), block):
        werte = " ".join(f"wd:{q}" for q in qids[i:i + block])
        for b in sparql(f"""SELECT ?i ?c WHERE {{
          VALUES ?i {{ {werte} }}
          ?i wdt:P31 ?c .
          FILTER(STRSTARTS(STR(?c), "http://www.wikidata.org/entity/Q"))
        }}"""):
            kanten.append((qid_aus(b, "i"), qid_aus(b, "c")))
    return kanten


def hole_kinder(qids: list, block: int = 200) -> dict:
    """{qid: Anzahl direkter Unterklassen}. Nur die ZAHL wird gebraucht -
    fuer instanz-als-klasse zaehlt, DASS etwas darunter haengt."""
    kinder = {q: 0 for q in qids}
    for i in range(0, len(qids), block):
        werte = " ".join(f"wd:{q}" for q in qids[i:i + block])
        for b in sparql(f"""SELECT ?p (COUNT(DISTINCT ?c) AS ?n) WHERE {{
          VALUES ?p {{ {werte} }}
          ?c wdt:P279 ?p .
        }} GROUP BY ?p"""):
            kinder[qid_aus(b, "p")] = int(b["n"]["value"])
    return kinder


def hole_labels(qids: list, block: int = 50) -> dict:
    """{qid: Bezeichnung}, deutsch bevorzugt. wbgetentities nimmt max. 50."""
    labels = {}
    for i in range(0, len(qids), block):
        daten = request_with_retry("GET", WIKIDATA_API, params={
            "action": "wbgetentities", "ids": "|".join(qids[i:i + block]),
            "props": "labels", "languages": "de|en",
            "format": "json", "formatversion": "2",
        }, timeout=60).json()
        for qid, eintrag in daten.get("entities", {}).items():
            bez = eintrag.get("labels", {})
            labels[qid] = (bez.get("de") or bez.get("en")
                           or {"value": qid})["value"]
    return labels


# ---------------------------------------------------------------------------
# Basismetall -> Legierungsklasse
# ---------------------------------------------------------------------------

def hole_ebenen_baum(wurzeln: list, tiefe: int, block: int = 100) -> dict:
    """{qid: {'label_de','label_en','desc_de','desc_en'}} bis Tiefe `tiefe`.

    Rueckgabe: (baum, qids der ersten Ebene). Die erste Ebene sind die DIREKT
    Eingehaengten - genau die, die pruefe_zu_allgemein untersucht. Sie faellt
    beim Aufbau ohnehin an; sie getrennt nachzuholen waere ein zweiter Satz
    Abfragen fuer Daten, die schon da sind.

    Ebenenweise mit VALUES-Bloecken, nicht am Stueck: "?i wdt:P279* ?wurzel"
    mit Labels und Beschreibungen laeuft unter material zuverlaessig in das
    60s-Limit des Query-Service. Siehe DEFAULT_TIEFE.
    """
    leer = {"label_de": "", "label_en": "", "desc_de": "", "desc_en": ""}
    baum, gesehen = {}, set(wurzeln)
    ebene = list(wurzeln)
    erste_ebene = set()

    for stufe in range(1, tiefe + 1):
        neu_auf_ebene = set()
        for i in range(0, len(ebene), block):
            werte = " ".join(f"wd:{q}" for q in ebene[i:i + block])
            for row in sparql(f"""SELECT ?item ?label ?desc WHERE {{
              VALUES ?parent {{ {werte} }}
              ?item wdt:P279 ?parent .
              OPTIONAL {{ ?item rdfs:label ?label .
                          FILTER(LANG(?label) IN ("de", "en")) }}
              OPTIONAL {{ ?item schema:description ?desc .
                          FILTER(LANG(?desc) IN ("de", "en")) }}
            }}"""):
                qid = qid_aus(row, "item")
                eintrag = baum.setdefault(qid, dict(leer))
                if qid not in gesehen:
                    neu_auf_ebene.add(qid)
                # Die Sprache haengt am Literal, nicht an der Projektion.
                for feld, praefix in (("label", "label"), ("desc", "desc")):
                    if feld in row:
                        lang = row[feld].get("xml:lang", "")
                        if lang in ("de", "en"):
                            eintrag[f"{praefix}_{lang}"] = row[feld]["value"]
        gesehen |= neu_auf_ebene
        if stufe == 1:
            erste_ebene = set(baum)
        print(f"  Ebene {stufe}: +{len(neu_auf_ebene)} Klassen "
              f"({len(baum)} insgesamt)", file=sys.stderr)
        if not neu_auf_ebene:
            break
        ebene = sorted(neu_auf_ebene)
    return baum, erste_ebene


def hole_elemente(qids: list, block: int = 200) -> set:
    """Die QIDs mit Ordnungszahl (P1086) - Elemente und ihre Isotope.

    Genau der Schnitt, den materialswiki seit jeher macht
    (LEGIERUNG_OHNE_ELEMENTE): weil Wikidata "Metall" faelschlich unter
    "Legierung" haengt, steht das halbe Periodensystem im Legierungsbaum.

    Als ZIEL einer Einordnung taugen sie nie: ein Werkstoff ist keine
    Unterklasse des Elements Kupfer. Ohne diesen Filter zielten 32 % der
    Heuristik-Vorschlaege auf copper, aluminium oder nickel (gemessen
    2026-08-23 an 118 Vorschlaegen).
    """
    elemente = set()
    for i in range(0, len(qids), block):
        werte = " ".join(f"wd:{q}" for q in qids[i:i + block])
        for b in sparql(f"""SELECT ?i WHERE {{
          VALUES ?i {{ {werte} }}
          ?i wdt:P1086 ?ordnungszahl .
        }}"""):
            elemente.add(qid_aus(b, "i"))
    return elemente


def baue_suchbegriffe(baum: dict, elemente: set = frozenset()) -> list:
    """[(qid, bezeichnung, sprache, muster)] - der Kandidatenpool.

    Vorberechnet, weil der Pool fuer JEDES zu pruefende Item durchlaufen wird:
    ohne das wuerde jede Bezeichnung tausendfach neu kleingeschrieben und neu
    zu einem regulaeren Ausdruck uebersetzt.

    Gesucht wird auf WORTGRENZEN. Die rohe Substring-Suche der Vorlage fand
    "Mater" in "Material" und "compo" in "composite" - beides Zufall, beides
    ein Vorschlag, der eine bestehende Einordnung ersetzt haette.

    `elemente` fliegt raus - siehe hole_elemente.
    """
    begriffe = []
    for qid, eintrag in baum.items():
        if qid in ALLGEMEINE_WURZELN or qid in elemente:
            continue
        for lang in ("de", "en"):
            bez = (eintrag.get(f"label_{lang}") or "").strip()
            if len(bez) < MIN_LABEL_LEN:
                continue
            if bez.lower() in ALLGEMEINE_BEZEICHNUNGEN:
                continue
            begriffe.append((qid, bez, lang,
                             re.compile(r"\b" + re.escape(bez.lower()) + r"\b")))
    return begriffe


def pruefe_zu_allgemein(kandidaten: dict, begriffe: list, graph,
                        labels: dict, verdaechtige_ziele: set,
                        nur_name: bool = True) -> list:
    """Item haengt direkt unter einer sehr allgemeinen Klasse, obwohl seine
    Bezeichnung eine speziellere nennt.

    `kandidaten` sind die direkten Kinder der allgemeinen Wurzeln, mit Label
    und Beschreibung. Vorgeschlagen wird, die allgemeine Kante durch die
    speziellere zu ERSETZEN - also zwei Zeilen, und die erste entfernt etwas.
    Genau deshalb steht das Ganze in der heuristischen Stufe: bei einem
    Fehltreffer haengt das Item ersatzlos aus dem Baum.

    Uebersprungen wird, was das Item ohnehin schon erfuellt: fuehrt im
    Graphen bereits ein P279-Pfad zum Treffer, gibt es nichts vorzuschlagen.

    Ebenfalls uebersprungen: `verdaechtige_ziele`, also Klassen, die
    pruefe_verkehrt selbst beanstandet. Sonst schlaegt dieses Skript vor,
    ein Item unter eine Klasse zu haengen, deren Platz es zwei Stufen weiter
    oben in Frage stellt - beobachtet an "Orgelmetall", das von Legierung
    nach Metall (Q11426) umgehaengt werden sollte, ausgerechnet der Klasse
    mit der falsch modellierten Kante.
    """
    treffer = []
    for qid, eintrag in sorted(kandidaten.items()):
        name = " ".join(filter(None, (eintrag.get("label_de"),
                                      eintrag.get("label_en")))).lower()
        beschreibung = " ".join(filter(None, (eintrag.get("desc_de"),
                                              eintrag.get("desc_en")))).lower()
        anzeige = (eintrag.get("label_de") or eintrag.get("label_en")
                   or labels.get(qid, qid))

        gefunden = []
        for kand_qid, bez, lang, muster in begriffe:
            if kand_qid == qid or kand_qid in verdaechtige_ziele:
                continue
            im_namen = bool(muster.search(name))
            in_beschreibung = bool(muster.search(beschreibung))
            if not im_namen and (nur_name or not in_beschreibung):
                continue
            # Schon eingeordnet? Dann ist nichts zu tun.
            if qid in graph and kand_qid in graph:
                try:
                    if nx.has_path(graph, qid, kand_qid):
                        continue
                except nx.NodeNotFound:
                    pass
            gefunden.append((len(bez), kand_qid, bez,
                             "Name" if im_namen else "Beschreibung"))
        if not gefunden:
            continue

        # Laengster Treffer zuerst - er ist der spezifischste.
        gefunden.sort(reverse=True)
        _, ziel_qid, ziel_bez, beleg = gefunden[0]
        weitere = "; ".join(f"{q} ({b})" for _, q, b, _ in gefunden[1:4])

        for wurzel_qid, wurzel_name in ALLGEMEINE_WURZELN.items():
            if not (qid in graph and graph.has_edge(qid, wurzel_qid)):
                continue
            treffer.append(befund(
                "zu-allgemein", qid, anzeige,
                f"-{qid}\tP279\t{wurzel_qid}\n{qid}\tP279\t{ziel_qid}",
                f"haengt direkt unter {wurzel_qid} ({wurzel_name}), obwohl "
                f"{beleg.lower()} '{ziel_bez}' nennt - dafuer gibt es "
                f"{ziel_qid}."
                + (f" Weitere Treffer: {weitere}." if weitere else ""),
                "Heuristik auf Wortgrenzen. Erst pruefen, ob der Treffer "
                "sachlich passt - die erste Zeile ENTFERNT die bestehende "
                "Einordnung.",
                ziel_qid=ziel_qid, ziel_label=ziel_bez, kennzahl=beleg))
    # Nach ZIELKLASSE gruppiert ausgeben, nicht nach QID. Beim Durchsehen
    # stehen damit alle "-> bronze" beieinander: die Entscheidung faellt
    # einmal fuer die Gruppe statt zwoelfmal einzeln, und ein systematischer
    # Fehlgriff der Heuristik faellt als Block auf statt verstreut.
    return sorted(treffer, key=lambda t: (t["ziel_label"].lower(), t["label"]))


def hole_elementnamen() -> dict:
    """{bezeichnung in Kleinschreibung: kanonischer englischer Name} fuer die
    chemischen Elemente - inklusive Aliassen und Symbolen.

    Kanonisch ist die englische BEZEICHNUNG (rdfs:label), nicht der kuerzeste
    Alias. Das klingt nach einer Formalie, ist aber der Unterschied zwischen
    "copper" und "Cu": nur mit der Bezeichnung findet finde_basisklassen
    anschliessend die Klasse "copper-based alloy".

    Die Aliasse sind als SCHLUESSEL noetig, nicht als Wert: Wikidata fuehrt
    das Element als "aluminium", die Muenz-Items schreiben "Aluminum", und
    manche Zusammensetzung nennt nur das Symbol. Ohne die Aliasse faellt
    jede dieser Schreibweisen durch.

    Geholt statt gepflegt: eine handgeschriebene Elementliste im Quelltext
    waere eine zweite Wahrheit neben Wikidata, und dieses Skript soll gegen
    Wikidata pruefen, nicht gegen eine Kopie davon.
    """
    namen = {}
    for b in sparql("""SELECT ?label ?name WHERE {
      ?e wdt:P31 wd:Q11344 ; wdt:P1086 ?z .
      FILTER(?z <= 118)
      ?e rdfs:label ?label .
      FILTER(LANG(?label) = "en")
      { ?e rdfs:label ?name . FILTER(LANG(?name) IN ("en", "de")) }
      UNION
      { ?e skos:altLabel ?name . FILTER(LANG(?name) IN ("en", "de")) }
    }"""):
        kanonisch = b["label"]["value"].strip()
        schluessel = b["name"]["value"].strip().lower()
        # Erster Treffer gewinnt: ein Alias, den sich zwei Elemente teilen,
        # waere ohnehin nicht eindeutig aufloesbar.
        namen.setdefault(schluessel, kanonisch)
    return namen


def lies_zusammensetzung(text: str, elementnamen: dict) -> tuple:
    """([(anteil, element)], [nicht erkannte Bestandteile]).

    Erkennt beide Schreibweisen (siehe ZUSAMMENSETZUNG_MUSTER) und wirft
    weg, was kein chemisches Element ist - "27.5% Steel" und "Other Metals
    2%" kommen in den Daten vor und sind als Basismetall unbrauchbar.
    Sie gehen nicht verloren, sondern in die zweite Rueckgabe: dass ein
    Bestandteil nicht zugeordnet werden konnte, gehoert in die Begruendung.
    """
    gefunden, unbekannt = {}, []
    for i, muster in enumerate(ZUSAMMENSETZUNG_MUSTER):
        for a, b in muster.findall(text):
            anteil_roh, name = (a, b) if i == 0 else (b, a)
            name = name.strip().strip("-").lower()
            try:
                anteil = float(anteil_roh.replace(",", "."))
            except ValueError:
                continue
            element = elementnamen.get(name)
            if element is None:
                if name not in unbekannt and len(name) > 2:
                    unbekannt.append(name)
                continue
            # Dasselbe Element kann in beiden Mustern anschlagen; der
            # groessere Fund gewinnt, doppelt gezaehlt wird nichts.
            gefunden[element] = max(gefunden.get(element, 0.0), anteil)
    anteile = sorted(((a, e) for e, a in gefunden.items()), reverse=True)
    return anteile, unbekannt


def pruefe_zusammensetzung(kandidaten: dict, elementnamen: dict,
                           basisklassen: dict, graph, labels: dict) -> list:
    """Basismetall aus der Zusammensetzung im Namen ableiten.

    "Nickel brass (70% Copper, 18% Zinc, 12% Nickel)" ist eine
    Kupferlegierung - das Element mit dem groessten Anteil ist definitionsgemaess
    das Basismetall. Diese Auswertung raet nicht, sie rechnet; sie ist die
    belastbarste Namensauswertung im Skript.

    Drei Faelle bekommen trotzdem KEINEN Vorschlag:

      * "Plating: ..." - die Prozente gelten nur der Auflage. "Brass plated
        steel (Plating: 72.5% Copper, 27.5% Zinc)" ist Stahl mit
        Messingauflage, kein Kupferwerkstoff.
      * Kein klarer Sieger (siehe MIN_ABSTAND_PROZENT). Bei "48% Copper,
        52% Aluminium" entscheidet die Zuordnung eine Nachkommastelle.
      * Kein Legierungsklasse fuer das Basismetall in Wikidata - dann ist
        nichts vorzuschlagen, nur zu melden.

    Ein vierter Fall bekommt einen Vorschlag MIT Warnung: Schichtverbunde
    ("clad", "plated"). Die Prozente stimmen dort fuer den Koerper, aber ein
    Verbund ist keine Legierung.
    """
    treffer = []
    for qid, eintrag in sorted(kandidaten.items()):
        anzeige = (eintrag.get("label_de") or eintrag.get("label_en")
                   or labels.get(qid, qid))
        text = " ".join(filter(None, (eintrag.get("label_de"),
                                      eintrag.get("label_en"))))
        if "%" not in text:
            continue

        klein = text.lower()
        if any(m in klein for m in AUFLAGE_MARKER):
            treffer.append(befund(
                "zusammensetzung", qid, anzeige, "",
                f"Der Name nennt eine Zusammensetzung, aber als 'Plating' - "
                f"die Prozente gelten der AUFLAGE, nicht dem Item.",
                "Kein Vorschlag: das Basismetall der Auflage sagt nichts "
                "ueber die Klasse des Werkstoffs. Von Hand entscheiden.",
                kennzahl="Auflage"))
            continue

        anteile, unbekannt = lies_zusammensetzung(text, elementnamen)
        if not anteile:
            continue

        zerlegung = ", ".join(f"{a:g}% {e}" for a, e in anteile)
        rest = (f" Nicht zugeordnet: {', '.join(unbekannt)}."
                if unbekannt else "")
        spitze, basis = anteile[0]
        zweiter = anteile[1][0] if len(anteile) > 1 else 0.0

        if spitze - zweiter < MIN_ABSTAND_PROZENT:
            treffer.append(befund(
                "zusammensetzung", qid, anzeige, "",
                f"Zusammensetzung {zerlegung}.{rest} Kein klares Basismetall: "
                f"{basis} fuehrt nur mit {spitze - zweiter:g} Prozentpunkten.",
                f"Kein Vorschlag - unter {MIN_ABSTAND_PROZENT:g} "
                f"Prozentpunkten Abstand entscheidet eine Nachkommastelle.",
                kennzahl=f"{spitze:g}:{zweiter:g}"))
            continue

        eintrag_klasse = basisklassen.get(basis.capitalize()) or \
            basisklassen.get(basis)
        if not eintrag_klasse:
            treffer.append(befund(
                "zusammensetzung", qid, anzeige, "",
                f"Zusammensetzung {zerlegung}.{rest} Basismetall {basis} "
                f"({spitze:g}%), aber dafuer gibt es in Wikidata keine "
                f"Legierungsklasse.",
                "Kein Vorschlag moeglich - die Klasse muesste erst angelegt "
                "werden, und das tut dieses Werkzeug nicht.",
                kennzahl=f"{spitze:g}%"))
            continue

        ziel_qid, ziel_label = eintrag_klasse
        if qid in graph and ziel_qid in graph:
            try:
                if nx.has_path(graph, qid, ziel_qid):
                    continue  # laengst eingeordnet
            except nx.NodeNotFound:
                pass

        verbund = [m for m in VERBUND_MARKER if m in klein]
        warnung = ""
        if verbund:
            warnung = (f" ACHTUNG: '{verbund[0]}' im Namen - das Item ist "
                       f"vermutlich ein Schichtverbund, keine Legierung. "
                       f"Dann trifft die Zuordnung nicht zu.")

        quickstatements = f"{qid}\tP279\t{ziel_qid}"
        # Die allgemeine Kante nur entfernen, wenn es sie ueberhaupt gibt.
        for wurzel_qid in ALLGEMEINE_WURZELN:
            if qid in graph and graph.has_edge(qid, wurzel_qid):
                quickstatements = (f"-{qid}\tP279\t{wurzel_qid}\n"
                                   + quickstatements)
                break

        treffer.append(befund(
            "zusammensetzung", qid, anzeige, quickstatements,
            f"Zusammensetzung {zerlegung}.{rest} Basismetall ist {basis} mit "
            f"{spitze:g}%, also {ziel_qid} ({ziel_label}).",
            ("Gerechnet, nicht geraten - der Anteil steht im Namen." + warnung
             if not verbund else warnung.strip()),
            ziel_qid=ziel_qid, ziel_label=ziel_label,
            kennzahl=f"{spitze:g}%"))
    return treffer


def pruefe_p31_neben_p279(p31_kanten: list, kinder: dict, direkt_allgemein: set,
                          labels: dict) -> list:
    """Item haengt direkt unter einer allgemeinen Klasse UND hat P31.

    Die Vorlage (material_subclass_check.py, "Fall B") schloss daraus auf ein
    physisches Einzelobjekt und empfahl P186 statt P279. Diese Praemisse
    haelt nicht: die tatsaechlichen P31-Werte sind ganz ueberwiegend
    KLASSENmarkierungen - "type of material" (6x), "class of chemical
    substances by use" (4x), "Stoffgruppe" (3x), "Produktkategorie" (2x),
    gemessen an 68 Items am 2026-08-23. Das sind keine Einzelobjekte.

    Deshalb hier nur noch Meldung, kein Entwurf. Wer P31 UND Unterklassen
    hat, wird ohnehin von pruefe_instanz_als_klasse erfasst - das ist der
    Teil des Gedankens, der strukturell traegt.
    """
    nach_item = {}
    for item, klasse in p31_kanten:
        if item in direkt_allgemein and not kinder.get(item):
            nach_item.setdefault(item, []).append(klasse)

    return [befund(
        "p31-neben-p279", qid, labels.get(qid, qid), "",
        "haengt direkt unter einer allgemeinen Klasse und hat zusaetzlich "
        "P31 auf: " + ", ".join(f"{k} ({labels.get(k, k)})" for k in werte[:4]),
        "Nur zur Kenntnis. Ist der P31-Wert eine Klassenmarkierung (type of "
        "material, Stoffgruppe), ist alles in Ordnung. Meint er ein "
        "Einzelobjekt, gehoert das Material ueber P186 daran - das laesst "
        "sich hier nicht entscheiden.",
        kennzahl=len(werte))
        for qid, werte in sorted(nach_item.items())]


def finde_basisklassen(basen: list) -> tuple:
    """({Basismetall: (qid, label)}, {Basismetall: Grund fuer die Luecke}).

    Gesucht wird ueber die englische Bezeichnung nach KLASSEN_MUSTER, und es
    zaehlt nur, was selbst unter Q37756 haengt. Diese Bedingung ist der Kern
    der Pruefung: sonst faende "silicon bronze" oder ein gleichnamiges
    Handelsprodukt genauso wie eine echte Werkstoffklasse.
    """
    kandidaten = {}   # Bezeichnung -> Basismetall
    for basis in basen:
        wort = SCHREIBWEISEN.get(basis, basis).lower()
        for muster in KLASSEN_MUSTER:
            kandidaten[muster.format(b=wort)] = basis

    gefunden = {}
    namen = list(kandidaten)
    for i in range(0, len(namen), 100):
        werte = " ".join(f'"{n}"@en' for n in namen[i:i + 100])
        for b in sparql(f"""SELECT ?c ?l WHERE {{
          VALUES ?l {{ {werte} }}
          ?c rdfs:label ?l .
          ?c wdt:P279* wd:{LEGIERUNG_QID} .
        }}"""):
            basis = kandidaten[b["l"]["value"]]
            # Erster Treffer gewinnt - KLASSEN_MUSTER steht nach Haeufigkeit
            # der Wikidata-Schreibweise sortiert.
            gefunden.setdefault(basis, (qid_aus(b, "c"), b["l"]["value"]))

    for basis, eintrag in BASISKLASSEN_FEST.items():
        if basis in basen:
            gefunden[basis] = eintrag

    luecken = {}
    for basis in basen:
        if basis in gefunden:
            continue
        luecken[basis] = BASISKLASSEN_BEKANNTE_LUECKE.get(
            basis, "keine Klasse '<Basismetall> alloy' unter Q37756 gefunden")
    return gefunden, luecken


# ---------------------------------------------------------------------------
# Die Pruefungen
# ---------------------------------------------------------------------------

def befund(art: str, qid: str, label: str, quickstatements: str,
           begruendung: str, entscheidung: str, **extra) -> dict:
    """Ein Befund. `quickstatements` leer heisst: hier gibt es nichts zu
    entwerfen, der Befund ist reine Meldung."""
    return {"befund": art, "qid": qid, "label": label,
            "quickstatements": quickstatements, "begruendung": begruendung,
            "entscheidung": entscheidung,
            "ziel_qid": extra.get("ziel_qid", ""),
            "ziel_label": extra.get("ziel_label", ""),
            "kennzahl": extra.get("kennzahl", "")}


def pruefe_zyklen(graph, im_bereich: set, labels: dict,
                  max_zyklen: int = 50) -> list:
    """P279-Zyklen: eine Klasse ist ueber P279 ihre eigene Oberklasse.

    Immer ein Fehler, aber nie automatisch aufloesbar: der Zyklus sagt, DASS
    eine Kante der Kette falsch ist, nicht WELCHE. Deshalb nur Meldung.

    Lokal gerechnet statt per SPARQL - eine transitive Selbstreferenz
    ("?a wdt:P279+ ?b . ?b wdt:P279+ ?a") ist fuer den Query-Service teuer,
    fuer networkx auf dem bereits geholten Graphen fast umsonst.

    Auf die Werkstoff-Ecke begrenzt, aus demselben Grund wie bei
    pruefe_redundant: die Huelle nach oben endet in der Oberontologie, und
    ein Zyklus zwischen "Kunstgewerbe" und "angewandte Kunst" ist zwar ein
    echter Fehler, aber keiner, den dieses Projekt zu reparieren hat.
    """
    treffer = []
    for i, zyklus in enumerate(
            z for z in nx.simple_cycles(graph) if im_bereich.issuperset(z)):
        if i >= max_zyklen:
            break
        kette = " -> ".join(f"{q} ({labels.get(q, q)})"
                            for q in zyklus + [zyklus[0]])
        treffer.append(befund(
            "zyklus", zyklus[0], labels.get(zyklus[0], zyklus[0]), "",
            f"P279-Zyklus ueber {len(zyklus)} Klassen: {kette}",
            "Welche Kante der Kette falsch ist, entscheidet die Fachlichkeit "
            "- hier wird nichts vorgeschlagen.",
            kennzahl=len(zyklus)))
    return treffer


def pruefe_redundant(graph, im_bereich: set, verdaechtig: set, labels: dict,
                     max_umweg: int = 4) -> list:
    """Kante n -> p, obwohl n ueber einen anderen Elter ohnehin bei p landet.

    Die einzige Pruefung mit einspielbarem Vorschlag, und zwar aus einem
    Grund: sie behauptet nichts. Entfernt wird eine Kante, die keine
    Information traegt - nach dem Entfernen ist n weiterhin Unterklasse von
    p, nur eben abgeleitet statt doppelt notiert. Das ist gaengige
    Wikidata-Praxis (Redundanz macht Baeume unlesbar und Constraint-Berichte
    laut), und es ist reversibel.

    `max_umweg` begrenzt die Laenge des Ersatzpfades. Ein Umweg ueber zehn
    Klassen ist zwar formal derselbe Befund, laesst sich aber nicht mehr in
    einer Zeile pruefen - und was nicht pruefbar ist, gehoert nicht in den
    einspielbaren Abschnitt.

    `im_bereich` begrenzt auf die Werkstoff-Ecke. Die Huelle nach oben endet
    zwangslaeufig in der obersten Ontologie, und dort findet dieselbe Pruefung
    dieselben Redundanzen bei "Begriff", "Typ", "Ereignis" oder
    "Kunstgewerbe". Die Befunde sind richtig, gehen dieses Projekt aber
    nichts an: wer Werkstoffe pflegt, hat keinen Anlass, an der
    Oberontologie zu schrauben, und eine dort eingespielte Aenderung trifft
    hunderttausende Items.

    `verdaechtig` sind die Kanten, die pruefe_verkehrt beanstandet - und sie
    sind der Grund, warum diese Pruefung nicht so harmlos ist, wie sie
    aussieht. Die Redundanz gilt nur, solange der ERSATZPFAD haelt. Genau das
    ist hier oft nicht der Fall: "Ferrolegierung P279 Legierung" sieht
    redundant aus, weil es ueber ferrous metal -> Metalle -> Legierung auch
    so geht - aber der letzte Schritt ist die falsch modellierte Kante. Wer
    die direkte Kante entfernt und spaeter die falsche repariert, hat
    Ferrolegierung aus dem Legierungsbaum geworfen.

    Solche Befunde bekommen die Art 'redundant-unsicher' und landen damit im
    auskommentierten Teil. Erst die falsche Kante klaeren, dann diese hier.
    """
    treffer = []
    for n in graph.nodes:
        if n not in im_bereich:
            continue
        eltern = list(graph.successors(n))
        if len(eltern) < 2:
            continue
        for p in eltern:
            # Alle Ersatzpfade sammeln: n -> (anderer Elter) -> ... -> p.
            # Die direkte Kante bleibt dabei aussen vor, sonst ist jeder Pfad
            # trivial. Gesammelt statt beim ersten Treffer abgebrochen, weil
            # ein SAUBERER Ersatzpfad einen verdaechtigen schlaegt - und der
            # kann der zweite sein.
            pfade = []
            for q in eltern:
                if q == p or q == n:
                    continue
                try:
                    pfad = nx.shortest_path(graph, q, p)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                if len(pfad) > max_umweg:   # len(pfad) = Kanten ab n
                    continue
                voll = [n] + pfad
                kaputt = [(a, b) for a, b in zip(voll, voll[1:])
                          if (a, b) in verdaechtig]
                pfade.append((bool(kaputt), voll, kaputt))
            if not pfade:
                continue
            # False < True: der ungefaehrdete Pfad gewinnt, danach der kuerzere.
            unsicher, voll, kaputt = min(pfade, key=lambda t: (t[0], len(t[1])))

            kette = " -> ".join(f"{x} ({labels.get(x, x)})" for x in voll)
            q = voll[1]
            grund = (f"{n} hat P279 auf {p} ({labels.get(p, p)}) UND auf "
                     f"{q} ({labels.get(q, q)}); ueber {q} ist {p} ohnehin "
                     f"erreichbar: {kette}")
            if unsicher:
                a, b = kaputt[0]
                treffer.append(befund(
                    "redundant-unsicher", n, labels.get(n, n),
                    f"-{n}\tP279\t{p}", grund,
                    f"NICHT einspielen, solange {a} ({labels.get(a, a)}) -> "
                    f"{b} ({labels.get(b, b)}) ungeklaert ist: der Ersatzpfad "
                    f"laeuft ueber diese beanstandete Kante. Faellt sie, "
                    f"faellt auch die Einordnung von {n}.",
                    ziel_qid=p, ziel_label=labels.get(p, p),
                    kennzahl=len(voll) - 1))
            else:
                treffer.append(befund(
                    "redundant", n, labels.get(n, n),
                    f"-{n}\tP279\t{p}", grund,
                    "Entfernen aendert nichts an der abgeleiteten "
                    "Klassenzugehoerigkeit - nur die doppelte Notation faellt weg.",
                    ziel_qid=p, ziel_label=labels.get(p, p),
                    kennzahl=len(voll) - 1))
    return treffer


def verkehrt_kandidaten(graph, im_bereich: set,
                        min_unterbau: int = 25) -> list:
    """[(n, p, |unter n|, |eigener Unterbau von p|)] - Kandidaten fuer eine
    verkehrte Kante.

    Die Messgroesse: die naive Fassung "Unterbau von n groesser als Unterbau
    von p" kann nie ausschlagen, denn die Kante n -> p macht alles unter n
    automatisch auch zu etwas unter p. Gemessen wird deshalb der EIGENE
    Unterbau von p, also ohne den Teil, den p nur ueber n hat. Traegt n mehr
    als p selbst, dann haengt die weite Klasse unter der engen.

    Bei Metall (Q11426) unter Legierung (Q37756) faellt das drastisch aus:
    ohne den Metalle-Zweig bleibt Legierung kaum eigener Unterbau, waehrend
    unter Metall die Elemente samt Isotopen haengen. materialswiki gleicht das
    seit jeher mit einem Filter aus (LEGIERUNG_OHNE_ELEMENTE) - die Kante
    selbst bleibt falsch.

    Zwei Bedingungen halten das Ergebnis brauchbar, beide notwendig:

    `im_bereich` sind die Klassen der ABWAERTS vollstaendig geholten Huelle
    unter der Bereichswurzel. Nur fuer sie stimmt die lokal gezaehlte
    Unterbaugroesse mit der echten ueberein - fuer alles darueber zaehlt der
    Graph nur, was zufaellig mitgeholt wurde. Ohne diese Einschraenkung
    besteht das Ergebnis fast ausschliesslich aus der oberen Ontologie
    (Entitaet, Objekt, Materie, Substanz ...), wo die Zahlen ein Artefakt
    der Abfrage sind und keine Aussage.

    `min_unterbau` haelt das Rauschen darunter draussen: bei zwei Klassen mit
    je drei Unterklassen sagt der Vergleich nichts.
    """
    unterbau = {n: nx.ancestors(graph, n) for n in im_bereich if n in graph}
    treffer = []
    for n, p in graph.edges:
        if n not in unterbau or p not in unterbau:
            continue
        unter_n = unterbau[n]
        if len(unter_n) < min_unterbau:
            continue
        eigen_p = unterbau[p] - unter_n - {n}
        if len(unter_n) <= len(eigen_p):
            continue
        treffer.append((n, p, len(unter_n), len(eigen_p)))
    return sorted(treffer, key=lambda t: -t[2])


def pruefe_verkehrt(kandidaten: list, labels: dict) -> list:
    return [befund(
        "verkehrt", n, labels.get(n, n),
        f"-{n}\tP279\t{p}",
        f"Unter {n} ({labels.get(n, n)}) haengen {gross} Klassen, unter "
        f"{p} ({labels.get(p, p)}) ohne diesen Zweig nur {klein}. Die "
        f"weitere Klasse haengt unter der engeren.",
        "Verdacht auf verkehrte Kante. Ob sie zu entfernen oder umzudrehen "
        "ist, ist eine fachliche Entscheidung.",
        ziel_qid=p, ziel_label=labels.get(p, p),
        kennzahl=f"{gross}:{klein}")
        for n, p, gross, klein in kandidaten]


def pruefe_instanz_als_klasse(p31_kanten: list, kinder: dict, im_baum: set,
                              labels: dict) -> list:
    """Item mit P31 auf eine Werkstoffklasse, das SELBST Unterklassen hat.

    Wer Unterklassen hat, ist eine Klasse - und Klassen haengen in Wikidata
    mit P279 ineinander, nicht mit P31. Der Entwurf dreht beides um (P31 weg,
    P279 hin), bleibt aber auskommentiert: es gibt Items, die zu Recht beides
    sind (eine Norm-Legierung kann Instanz eines Normwerks und zugleich
    Oberklasse ihrer Varianten sein).
    """
    treffer = []
    for item, klasse in p31_kanten:
        if klasse not in im_baum or not kinder.get(item):
            continue
        treffer.append(befund(
            "instanz-als-klasse", item, labels.get(item, item),
            f"-{item}\tP31\t{klasse}\n{item}\tP279\t{klasse}",
            f"{item} ist P31 von {klasse} ({labels.get(klasse, klasse)}), hat "
            f"aber selbst {kinder[item]} Unterklassen - wer Unterklassen hat, "
            f"ist eine Klasse.",
            "P31 -> P279 umstellen, wenn das Item wirklich nur Klasse ist. "
            "Beides zugleich ist moeglich und dann kein Fehler.",
            ziel_qid=klasse, ziel_label=labels.get(klasse, klasse),
            kennzahl=kinder[item]))
    return treffer


def pruefe_ohne_einordnung(items: dict, eingeordnet: set, labels: dict) -> list:
    """Benannte Legierung ohne jeden Pfad zu "Legierung" (Q37756).

    Nur fuer die Pruefliste sinnvoll: dort steht durch die HERKUNFT fest,
    dass es sich um eine Legierung handeln soll. In den SPARQL-Gruppen ist
    die Klassifikation per Definition schon erfuellt.

    Wo es fuer das Basismetall eine Klasse gibt, wird sie vorgeschlagen -
    aber auskommentiert, denn die Projektseite verlangt eine differenzierte
    Einhaengung (Ferrous alloy, Alloy steel, ...), und "Nickel" sagt nicht,
    ob etwas Superlegierung, Lotlegierung oder Widerstandslegierung ist. Der
    Vorschlag ist also die GROBE, sichere Einordnung - die feine bleibt
    Handarbeit.

    Und ein Teil der Meldungen ist zu Recht keine Legierung: Titannitrid,
    Titancarbid und Uranhydrid sind Verbindungen. Auch das entscheidet hier
    niemand automatisch.
    """
    basen = sorted({e["basis"] for e in items.values()
                    if e["qid"] not in eingeordnet and e.get("basis")})
    klassen, luecken = finde_basisklassen(basen) if basen else ({}, {})

    treffer = []
    for eintrag in items.values():
        qid = eintrag["qid"]
        if qid in eingeordnet:
            continue
        basis = eintrag.get("basis", "")
        name = labels.get(qid, eintrag.get("label", qid))
        if basis in klassen:
            ziel_qid, ziel_label = klassen[basis]
            treffer.append(befund(
                "ohne-einordnung", qid, name,
                f"{qid}\tP279\t{ziel_qid}",
                f"steht in [[en:List of named alloys]] unter '{basis}', hat "
                f"aber keinen P279/P31-Pfad zu Legierung (Q37756). Passende "
                f"Klasse: {ziel_qid} ({ziel_label}).",
                "Grobe Einordnung. Erst pruefen, ob das Item ueberhaupt eine "
                "Legierung ist (Nitride, Carbide und Hydride stehen auch in "
                "der Liste), dann ob eine engere Klasse besser passt.",
                ziel_qid=ziel_qid, ziel_label=ziel_label))
        else:
            grund = luecken.get(basis, "kein Basismetall in der Liste")
            treffer.append(befund(
                "ohne-einordnung", qid, name, "",
                f"steht in [[en:List of named alloys]] unter "
                f"'{basis or '?'}', hat aber keinen P279/P31-Pfad zu "
                f"Legierung (Q37756). Kein Vorschlag moeglich: {grund}.",
                "Ohne passende Oberklasse in Wikidata bleibt nur, sie "
                "anzulegen - das tut dieses Werkzeug nicht."))
    return treffer, luecken


def pruefe_parallelzweig(items: dict, unter_material: set,
                         labels: dict) -> list:
    """Items ohne P279*-Pfad zu material (Q214609).

    Ausdruecklich KEIN Fehler: P279 erlaubt (und P186 verlangt) mehrere
    gleichrangige Werttypen nebeneinander - alloy, chemical compound,
    substance. Eine Legierung muss nicht unter Q214609 haengen, um richtig
    eingeordnet zu sein. Der ausfuehrliche Nachweis steht in
    visualisierung.py, im selben Ordner.

    Gemeldet wird trotzdem, weil die Zahl die Frage beantwortet, ob sich eine
    Vereinheitlichung ueberhaupt lohnt.
    """
    return [befund(
        "parallelzweig", qid, labels.get(qid, eintrag.get("label", qid)), "",
        "kein P279*-Pfad zu material (Q214609) - laeuft ueber einen "
        "parallelen Zweig (alloy, chemical compound, ...).",
        "Kein Fehler. Nur relevant, wenn die Hierarchie unter Q214609 "
        "vereinheitlicht werden soll.")
        for qid, eintrag in items.items() if qid not in unter_material]


def kennzahlen(items: dict, graph, p31_kanten: list, kinder: dict,
               unter_material: set, eingeordnet: set) -> list:
    """Wie wird P279 in dieser Grundgesamtheit ueberhaupt benutzt?"""
    qids = set(items)
    mit_p279 = {q for q in qids if q in graph and graph.out_degree(q)}
    mit_p31 = {i for i, _ in p31_kanten if i in qids}
    mehrfach = {q for q in mit_p279 if graph.out_degree(q) > 1}
    tiefen = []
    for q in qids & set(graph.nodes):
        try:
            tiefen.append(nx.shortest_path_length(graph, q, MATERIAL_QID))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

    werte = [
        ("Items gesamt", len(qids)),
        ("mit P279 (Unterklasse von)", len(mit_p279)),
        ("mit P31 (ist ein/e)", len(mit_p31)),
        ("mit beidem", len(mit_p279 & mit_p31)),
        ("mit keinem von beiden", len(qids - mit_p279 - mit_p31)),
        ("mit mehreren Oberklassen", len(mehrfach)),
        ("selbst Oberklasse (hat Unterklassen)",
         sum(1 for q in qids if kinder.get(q))),
        ("mit Pfad zu Legierung (Q37756)", len(qids & eingeordnet)),
        ("mit Pfad zu material (Q214609)", len(qids & unter_material)),
        ("kuerzester Abstand zu material, Median",
         sorted(tiefen)[len(tiefen) // 2] if tiefen else 0),
        ("Klassen im geholten Graphen", graph.number_of_nodes()),
        ("P279-Kanten im geholten Graphen", graph.number_of_edges()),
    ]
    return [befund("kennzahl", "", name, "", "", "", kennzahl=wert)
            for name, wert in werte]


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

_TRENNER = "# " + "=" * 70

# Reihenfolge und Ueberschrift der auskommentierten Abschnitte. Der Text
# hinter dem Doppelpunkt sagt, WARUM hier nichts einspielbar ist - das ist
# die Information, die beim Durchsehen zaehlt.
# Die Staffelung. Eine Stufe = EINE Art von Beweiskraft, und der Kopftext
# sagt, was der Mensch an dieser Stufe konkret pruefen muss. Das ist der
# ganze Zweck der Datei: von oben nach unten wird die Pruefung aufwendiger
# und die Trefferquote schlechter, also kann jederzeit aufgehoert werden.
STUFEN = [
    (1, "MECHANISCH SICHER", ["redundant"], True,
     ["Folgt allein aus dem Graphen und behauptet nichts: die entfernte",
      "Kante gilt danach weiter, nur abgeleitet statt doppelt notiert.",
      "Nichts geht verloren, alles ist umkehrbar.",
      "",
      "ZU PRUEFEN: Stimmt der angegebene Ersatzpfad? Ein Blick aufs Item."]),
    (2, "STRUKTURELL BEGRUENDET", ["instanz-als-klasse", "verkehrt",
                                   "redundant-unsicher", "zyklus"], False,
     ["Aus dem Graphen abgeleitet, aber mit einer fachlichen Entscheidung",
      "davor. Der Graph sagt, DASS etwas nicht stimmt - nicht, wie herum",
      "es richtig waere.",
      "",
      "ZU PRUEFEN: Einzelfall. Item oeffnen, Aussage im Kontext ansehen."]),
    (3, "AUS DER BEZEICHNUNG ABGELEITET", ["zusammensetzung", "zu-allgemein",
                                          "ohne-einordnung"], False,
     ["Nicht aus der Struktur, sondern aus dem Namen. Die Beweiskraft ist",
      "je Gruppe SEHR verschieden - der Gruppenkopf sagt jeweils, woran",
      "man ist. Die erste Gruppe rechnet, die zweite raet.",
      "",
      "ACHTUNG: Die meisten Entwuerfe hier haben ZWEI Zeilen, und die erste",
      "ENTFERNT die bestehende Einordnung. Ein Fehltreffer haengt das Item",
      "ersatzlos aus dem Baum. Im Zweifel: liegenlassen.",
      "",
      "ZU PRUEFEN: Passt die vorgeschlagene Oberklasse sachlich? Ist das",
      "Item ueberhaupt eine Legierung - oder ein Schichtverbund, eine",
      "Verbindung, ein Handelsname?"]),
    (4, "NUR MELDUNG - KEIN ENTWURF", ["p31-neben-p279", "parallelzweig"],
     False,
     ["Hier gibt es nichts einzuspielen. Diese Befunde stehen als Zahl auf",
      "dem Tisch, weil sie die Lage beschreiben - nicht, weil etwas zu tun",
      "waere. Ein Teil davon ist ausdruecklich KEIN Fehler."]),
]

# Ueberschrift und Einzeiler je Befundart, fuer die Zwischenkoepfe.
ART_TITEL = {
    "redundant": ("Doppelte Kante", "gilt ueber einen anderen Elter ohnehin"),
    "instanz-als-klasse": ("P31 statt P279",
                           "das Item hat selbst Unterklassen"),
    "verkehrt": ("Kante verkehrt herum",
                 "die weitere Klasse haengt unter der engeren"),
    "redundant-unsicher": ("Doppelt, aber Ersatzpfad wackelt",
                           "der Ersatzpfad laeuft ueber eine Kante von oben"),
    "zyklus": ("Zyklus", "eine Klasse ist ihre eigene Oberklasse"),
    "zusammensetzung": ("Basismetall aus der Zusammensetzung",
                        "GERECHNET: der Anteil steht im Namen, das groesste "
                        "Element ist das Basismetall"),
    "zu-allgemein": ("Zu allgemein eingehaengt",
                     "GERATEN: die Bezeichnung nennt eine speziellere "
                     "Klasse - hier sind Fehltreffer die Regel"),
    "ohne-einordnung": ("Nicht als Legierung eingeordnet",
                        "steht in [[en:List of named alloys]]"),
    "p31-neben-p279": ("P31 neben P279", "nur zur Kenntnis"),
    "parallelzweig": ("Kein Pfad zu material (Q214609)",
                      "kein Fehler - P186 erlaubt parallele Werttypen"),
}

WD = "https://www.wikidata.org/wiki/"


def _stufen_block(nummer: int, titel: str, arten: list, einspielbar: bool,
                  erklaerung: list, befunde: list, zaehler: list) -> list:
    """Ein Stufenblock als Zeilenliste. `zaehler` ist einelementig und
    laeuft ueber alle Stufen durch - die Nummer im Kopf jedes Vorschlags
    ist damit ueber die ganze Datei eindeutig und zitierbar."""
    teil = [b for b in befunde if b["befund"] in arten]
    marke = "   ***EINSPIELBAR***" if einspielbar else ""
    zeilen = [
        "",
        _TRENNER,
        f"# STUFE {nummer} - {titel} ({len(teil)} Befunde){marke}",
        "#",
    ]
    zeilen += [f"# {z}".rstrip() for z in erklaerung]
    zeilen.append(_TRENNER)
    if not teil:
        zeilen.append("# (keine)")
        return zeilen

    for art in arten:
        eintraege = [b for b in teil if b["befund"] == art]
        if not eintraege:
            continue
        kopf, zusatz = ART_TITEL.get(art, (art, ""))
        zeilen += ["", f"# --- {kopf} ({len(eintraege)}) "
                       f"{'- ' + zusatz if zusatz else ''} ---"]
        for b in eintraege:
            zaehler[0] += 1
            name = b["label"] or b["qid"]
            zeilen.append(f"#")
            zeilen.append(f"# [{zaehler[0]:04d}] {name}   {WD}{b['qid']}")
            if b.get("ziel_qid"):
                zeilen.append(f"#        Ziel: {b['ziel_label']}   "
                              f"{WD}{b['ziel_qid']}")
            for satz in _umbrechen(b["begruendung"], 68):
                zeilen.append(f"#        {satz}")
            if b["entscheidung"]:
                for satz in _umbrechen("Pruefen: " + b["entscheidung"], 68):
                    zeilen.append(f"#        {satz}")
            for qs in (b["quickstatements"] or "").splitlines():
                # '#!' markiert einen freigabefaehigen Entwurf: pruefen, dann
                # die zwei Zeichen loeschen. In der einspielbaren Stufe steht
                # die Zeile gleich ohne Marke da.
                zeilen.append(qs if einspielbar else f"#!{qs}")
    return zeilen


def _umbrechen(text: str, breite: int) -> list:
    """Fliesstext auf `breite` Zeichen umbrechen - ohne textwrap, weil der
    lange QIDs und Pfadketten mitten im Bezeichner trennt."""
    zeilen, aktuell = [], ""
    for wort in text.split():
        if aktuell and len(aktuell) + 1 + len(wort) > breite:
            zeilen.append(aktuell)
            aktuell = wort
        else:
            aktuell = f"{aktuell} {wort}".strip()
    if aktuell:
        zeilen.append(aktuell)
    return zeilen or [""]


def schreibe_empfehlung(befunde: list, pfad: str, population: str,
                        luecken: dict, ohne_item: list, vorsichtig: bool,
                        mengengeruest: str) -> None:
    """Die eine gestaffelte Empfehlung.

    Aufbau: Kopf mit Arbeitsanweisung und Inhaltsverzeichnis (mit
    Zeilennummern, damit sich im Editor direkt hinspringen laesst), dann vier
    Stufen nach Beweiskraft.

    Nur Stufe 1 steht als ausfuehrbare QuickStatements-Syntax da. Ab Stufe 2
    traegt jeder Entwurf die Marke '#!' - QuickStatements liest sie als
    Kommentar, der Mensch loescht die zwei Zeichen, wenn er die Zeile
    freigibt. Alle uebrigen Zeilen beginnen mit '#', die Datei laesst sich
    also jederzeit als Ganzes einfuegen, ohne dass eine ungepruefte Zeile
    zur Aussage wird.
    """
    zaehler = [0]
    bloecke = []
    for nummer, titel, arten, einspielbar, erklaerung in STUFEN:
        bloecke.append((nummer, titel, arten,
                        _stufen_block(nummer, titel, arten,
                                      einspielbar and not vorsichtig,
                                      erklaerung, befunde, zaehler)))

    schluss = _schlussblock(luecken, ohne_item)

    # Kopf zweimal bauen: der erste Durchgang liefert nur seine Laenge,
    # damit die Zeilennummern im Inhaltsverzeichnis stimmen.
    def kopf(offsets: dict) -> list:
        z = [
            _TRENNER,
            "# P279-EMPFEHLUNG - Werkstoffe in Wikidata",
            f"# Grundgesamtheit '{population}', erzeugt "
            f"{dt.datetime.now():%Y-%m-%d %H:%M}",
            "#",
            "# SO ARBEITEST DU DAS AB",
            "#   1. Von oben nach unten. Die Stufen sind nach BEWEISKRAFT",
            "#      sortiert, nicht nach Wichtigkeit - du kannst jederzeit",
            "#      aufhoeren, das Gepruefte bleibt gueltig.",
            "#   2. Stufe 1 ist ausfuehrbar und steht ohne Marke da.",
            "#   3. Ab Stufe 2 traegt jeder Entwurf die Marke '#!'. Geprueft",
            "#      und fuer richtig befunden? Dann die zwei Zeichen '#!' am",
            "#      Zeilenanfang loeschen. Sonst stehenlassen.",
            "#      Im Editor: nach '#!' suchen, das sind alle Entwuerfe.",
            "#   4. Jeder Vorschlag hat eine Nummer [0042] und einen Link.",
            "#      Link im Browser oeffnen, Aussage dort pruefen.",
            "#   5. Am Ende die ganze Datei nach QuickStatements kopieren.",
            "#      Alles mit '#' wird ignoriert - nur was du freigegeben",
            "#      hast, wird zur Aussage.",
            "#",
            "# '-QID<TAB>P279<TAB>QID' entfernt eine Aussage, ohne Minus",
            "# setzt sie. Zweizeilige Entwuerfe ersetzen: erst entfernen,",
            "# dann setzen - beide Zeilen gehoeren zusammen.",
            "#",
            "# INHALT",
        ]
        for nummer, titel, arten, block in bloecke:
            anzahl = sum(1 for b in befunde if b["befund"] in arten)
            marke = "  EINSPIELBAR" if nummer == 1 and not vorsichtig else ""
            ort = (f"ab Zeile {offsets[nummer]:>5}" if offsets
                   else "ab Zeile     ?")
            z.append(f"#   Stufe {nummer}  {titel[:30]:<32}{anzahl:>4}   "
                     f"{ort}{marke}")
        if vorsichtig:
            z.append("#   (--vorsichtig: auch Stufe 1 ist nur ein Entwurf)")
        z += ["#", f"# {mengengeruest}", _TRENNER]
        return z

    laenge = len(kopf({}))
    offsets, laufend = {}, laenge
    for nummer, _, _, block in bloecke:
        offsets[nummer] = laufend + 2   # Ueberschrift statt Leerzeile davor
        laufend += len(block)

    zeilen = kopf(offsets)
    for _, _, _, block in bloecke:
        zeilen += block
    zeilen += schluss

    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"Empfehlung geschrieben nach: {pfad}", file=sys.stderr)


def _schlussblock(luecken: dict, ohne_item: list) -> list:
    """Was gar kein Item betrifft und deshalb in keine Stufe passt:
    fehlende Klassen und Listennamen ohne Item. Anlegen kann dieses
    Werkzeug beides nicht - es arbeitet nur an bestehenden Items."""
    zeilen = ["", _TRENNER,
              "# ANHANG - LUECKEN IN WIKIDATA (nichts einzuspielen)",
              "#",
              "# Hier fehlt ein Item, nicht eine Aussage. Anlegen tut dieses",
              "# Werkzeug nichts - das ist eine bewusste Entscheidung.",
              _TRENNER]
    if luecken:
        zeilen.append("#")
        zeilen.append("# Basismetalle ohne Legierungsklasse:")
        for basis, grund in sorted(luecken.items()):
            for i, satz in enumerate(_umbrechen(f"{basis}: {grund}", 66)):
                zeilen.append(f"#   {satz}" if i == 0 else f"#     {satz}")
    if ohne_item:
        zeilen.append("#")
        zeilen.append(f"# Listeneintraege ohne Wikidata-Item "
                      f"({len(ohne_item)}):")
        for satz in _umbrechen(", ".join(ohne_item), 66):
            zeilen.append(f"#   {satz}")
    if not luecken and not ohne_item:
        zeilen.append("# (keine)")
    return zeilen


def schreibe_csv(befunde: list, pfad: str) -> None:
    felder = ["befund", "qid", "label", "ziel_qid", "ziel_label", "kennzahl",
              "quickstatements", "begruendung", "entscheidung"]
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        schreiber = csv.DictWriter(f, fieldnames=felder)
        schreiber.writeheader()
        for b in befunde:
            # Der Zeilenumbruch im zweizeiligen P31->P279-Entwurf wuerde die
            # CSV-Zeile sprengen; im Tabellenblatt ist ' | ' lesbarer.
            schreiber.writerow({**{k: b.get(k, "") for k in felder},
                                "quickstatements":
                                    (b["quickstatements"] or "")
                                    .replace("\n", " | ")})
    print(f"CSV geschrieben nach: {pfad}", file=sys.stderr)


def bericht(befunde: list, luecken: dict, ohne_item: list,
            vorsichtig: bool = False) -> None:
    """Kurzfassung auf der Konsole - nach denselben Stufen wie die Datei,
    damit beim Lesen der Datei nichts neu einsortiert werden muss."""
    kz = [b for b in befunde if b["befund"] == "kennzahl"]
    if kz:
        print()
        print("Wie P279 hier benutzt wird")
        print("-" * 60)
        for b in kz:
            print(f"  {b['label']:<44}{b['kennzahl']:>6}")

    print()
    print("Befunde nach Stufe")
    print("-" * 60)
    for nummer, titel, arten, einspielbar, _ in STUFEN:
        teil = [b for b in befunde if b["befund"] in arten]
        entwuerfe = sum(1 for b in teil if b["quickstatements"])
        marke = ("EINSPIELBAR" if einspielbar and not vorsichtig
                 else "zur Freigabe" if entwuerfe else "nur Meldung")
        print(f"  Stufe {nummer}  {titel[:34]:<36}{len(teil):>5}   "
              f"Entwuerfe {entwuerfe:>4}   {marke}")
        for art in arten:
            anzahl = sum(1 for b in teil if b["befund"] == art)
            if anzahl:
                print(f"           {ART_TITEL.get(art, (art, ''))[0][:32]:<34}"
                      f"{anzahl:>5}")

    if luecken:
        print()
        print("Basismetalle ohne Legierungsklasse in Wikidata")
        print("-" * 60)
        for basis, grund in sorted(luecken.items()):
            print(f"  {basis:<16}{grund}")

    if ohne_item:
        print()
        print(f"{len(ohne_item)} Listeneintraege ohne Wikidata-Item: "
              f"{', '.join(ohne_item)}")
    print()


# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prueft die P279-Struktur der Werkstoffe in Wikidata und "
                    "entwirft Aenderungen als QuickStatements.")
    parser.add_argument("--population", choices=sorted(POPULATIONEN),
                        default="benannte-legierungen",
                        help="Grundgesamtheit (Default: benannte-legierungen, "
                             "die Pruefliste aus [[en:List of named alloys]])")
    parser.add_argument("--pruefungen", nargs="+", choices=PRUEFUNGEN,
                        default=PRUEFUNGEN,
                        help=f"Auswahl der Pruefungen (Default: alle: "
                             f"{', '.join(PRUEFUNGEN)})")
    parser.add_argument("--limit", type=int, default=None,
                        help="nur die ersten N Items (fuer Probelaeufe)")
    parser.add_argument("--vorsichtig", action="store_true",
                        help="auch die redundanten Kanten auskommentieren - "
                             "dann enthaelt die Datei keine ausfuehrbare Zeile")
    parser.add_argument("--min-unterbau", type=int, default=25,
                        help="Pruefung 'verkehrt': ab wie vielen Klassen im "
                             "Unterbau der Vergleich aussagekraeftig ist "
                             "(Default 25)")
    parser.add_argument("--bereichswurzel", default=LEGIERUNG_QID,
                        help="Pruefung 'verkehrt': Wurzel des Bereichs, dessen "
                             "Klassenbaum vollstaendig geholt und geprueft "
                             f"wird (Default {LEGIERUNG_QID}, Legierung). "
                             "Q214609 (material) ist zu gross - der Baum "
                             "umfasst rund 936.000 Klassen.")
    parser.add_argument("--max-umweg", type=int, default=4,
                        help="Pruefung 'redundant': laengster Ersatzpfad, der "
                             "noch als in einer Zeile pruefbar gilt (Default 4)")
    parser.add_argument("--tiefe", type=int, default=DEFAULT_TIEFE,
                        help="Pruefung 'zu-allgemein': bis zu welcher Ebene "
                             "unter den allgemeinen Wurzeln der "
                             f"Kandidatenpool geholt wird (Default "
                             f"{DEFAULT_TIEFE}). Ebene 3 findet mehr, dauert "
                             "aber deutlich laenger und raet oefter daneben.")
    parser.add_argument("--beleg", choices=["name", "beides"], default="name",
                        help="Pruefung 'zu-allgemein': ob nur die Bezeichnung "
                             "als Beleg zaehlt (Default) oder auch die "
                             "Beschreibung. 'beides' verdreifacht die Treffer "
                             "und senkt die Trefferquote deutlich - dass in "
                             "einer Beschreibung ein Wort vorkommt, sagt "
                             "nichts ueber die Klasse.")
    parser.add_argument("--out", default=None,
                        help="Ziel der Empfehlung (Default: "
                             "p279_empfehlung_<Zeitstempel>.txt)")
    parser.add_argument("--csv", default=None,
                        help="zusaetzlich eine Befund-CSV schreiben. Ohne "
                             "diese Angabe entsteht NUR die Empfehlung.")
    args = parser.parse_args(argv)

    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    empfehlung_pfad = args.out or f"p279_empfehlung_{stempel}.txt"

    items, ohne_item = hole_population(args.population, args.limit)
    if not items:
        raise SystemExit("Grundgesamtheit ist leer - nichts zu pruefen.")
    qids = sorted(items)

    # Ein Graph fuer alles: die Huelle wird einmal geholt, danach laufen
    # Zyklen-, Redundanz- und Verkehrt-Pruefung lokal. Per SPARQL waere jede
    # davon eine eigene teure Abfrage.
    # Die Label-Heuristik prueft die direkten Kinder der allgemeinen Wurzeln.
    # Die gehoeren mit in die Huelle: nur so laesst sich spaeter feststellen,
    # ob ein Vorschlag laengst erfuellt ist (pruefe_zu_allgemein).
    direkt_allgemein, allgemein_baum = {}, {}
    if {"zu-allgemein", "p31-neben-p279", "zusammensetzung"} & set(args.pruefungen):
        print(f"Hole Kandidatenpool bis Tiefe {args.tiefe} unter "
              f"{', '.join(ALLGEMEINE_WURZELN)} ...", file=sys.stderr)
        allgemein_baum, ebene1 = hole_ebenen_baum(
            sorted(ALLGEMEINE_WURZELN), args.tiefe)
        # Ebene 1 sind genau die direkt Eingehaengten - die zu Pruefenden.
        direkt_allgemein = {q: allgemein_baum[q] for q in ebene1}

    print("Hole P279-Huelle nach oben ...", file=sys.stderr)
    huelle_start = sorted(set(qids) | set(direkt_allgemein))
    kanten = hole_p279_huelle(huelle_start)
    graph = nx.DiGraph()
    graph.add_nodes_from(huelle_start)
    graph.add_edges_from(kanten)   # Richtung: Kind -> Elter
    print(f"  {graph.number_of_nodes()} Klassen, "
          f"{graph.number_of_edges()} P279-Kanten", file=sys.stderr)

    def erreichbar(ziel: str) -> set:
        """Alle Knoten mit P279*-Pfad zu `ziel` - inklusive ziel selbst."""
        if ziel not in graph:
            return set()
        return nx.ancestors(graph, ziel) | {ziel}

    unter_material = erreichbar(MATERIAL_QID)
    unter_legierung = erreichbar(LEGIERUNG_QID)
    # Die Werkstoff-Ecke: alles unter material oder Legierung, plus die
    # Grundgesamtheit selbst (die haengt nicht zwingend unter beidem - genau
    # das misst die Pruefung 'parallelzweig'). Ausserhalb davon wird nichts
    # vorgeschlagen, siehe pruefe_redundant.
    im_bereich = unter_material | unter_legierung | set(qids)

    braucht_p31 = {"instanz-als-klasse", "kennzahlen", "ohne-einordnung",
                   "p31-neben-p279"}
    p31_kanten = (hole_p31_kanten(sorted(set(qids) | set(direkt_allgemein)))
                  if braucht_p31 & set(args.pruefungen) else [])
    # Ueber P31 eingeordnet zaehlt genauso: "X ist ein/e Legierung".
    ueber_p31 = {i for i, k in p31_kanten if k in unter_legierung}
    eingeordnet = (unter_legierung | ueber_p31) & set(qids)

    braucht_kinder = {"instanz-als-klasse", "kennzahlen", "p31-neben-p279"}
    kinder = (hole_kinder(sorted(set(qids) | set(direkt_allgemein)))
              if braucht_kinder & set(args.pruefungen) else {})

    # Die Verkehrt-Pruefung braucht einen ZWEITEN Graphen: die vollstaendige
    # Huelle nach UNTEN unter der Bereichswurzel. Grund steht bei
    # verkehrt_kandidaten - in der Aufwaerts-Huelle sind die Unterbaugroessen
    # der oberen Klassen ein Artefakt der Abfrage, und das Ergebnis besteht
    # dann fast nur aus Entitaet, Objekt, Materie und Substanz.
    # Auch fuer 'redundant' und 'zu-allgemein' noetig, nicht nur fuer
    # 'verkehrt': ein Ersatzpfad ueber eine beanstandete Kante taugt nicht
    # als Nachweis (pruefe_redundant), und unter eine beanstandete Klasse
    # haengt man nichts Neues (pruefe_zu_allgemein).
    verkehrt = []
    if {"verkehrt", "redundant", "zu-allgemein"} & set(args.pruefungen):
        print(f"Hole P279-Huelle nach unten unter {args.bereichswurzel} ...",
              file=sys.stderr)
        ab_kanten = hole_p279_huelle([args.bereichswurzel], abwaerts=True)
        ab_graph = nx.DiGraph()
        ab_graph.add_nodes_from([args.bereichswurzel])
        ab_graph.add_edges_from(ab_kanten)
        # Im Bereich ist nur, was WIRKLICH unter der Wurzel haengt: die
        # Abwaerts-Huelle bringt ueber die Kanten auch Eltern ausserhalb mit,
        # und fuer die stimmt die gezaehlte Unterbaugroesse nicht.
        im_bereich = nx.ancestors(ab_graph, args.bereichswurzel) | {args.bereichswurzel}
        print(f"  {ab_graph.number_of_nodes()} Klassen, davon "
              f"{len(im_bereich)} im Bereich", file=sys.stderr)
        verkehrt = verkehrt_kandidaten(ab_graph, im_bereich, args.min_unterbau)

    # Labels erst jetzt, und nur fuer das, was gemeldet werden kann: der
    # ganze Graph waere ein Vielfaches an Abfragen fuer Klassen, die in
    # keinem Befund auftauchen. Bei der Abwaerts-Huelle waeren das ueber 3000
    # Klassen fuer eine Handvoll Treffer.
    zu_beschriften = (set(qids) | {p for _, p in kanten}
                      | {k for _, k in p31_kanten}
                      | {q for n, p, _, _ in verkehrt for q in (n, p)}
                      | set(direkt_allgemein))
    print(f"Hole {len(zu_beschriften)} Bezeichnungen ...", file=sys.stderr)
    labels = hole_labels(sorted(zu_beschriften))

    befunde, luecken = [], {}   # luecken sammelt Basismetalle ohne Klasse
    if "kennzahlen" in args.pruefungen:
        befunde += kennzahlen(items, graph, p31_kanten, kinder,
                              unter_material, eingeordnet)
    if "zyklus" in args.pruefungen:
        befunde += pruefe_zyklen(graph, im_bereich, labels)
    if "redundant" in args.pruefungen:
        befunde += pruefe_redundant(graph, im_bereich,
                                    {(n, p) for n, p, _, _ in verkehrt},
                                    labels, args.max_umweg)
    if "verkehrt" in args.pruefungen:
        befunde += pruefe_verkehrt(verkehrt, labels)
    if "instanz-als-klasse" in args.pruefungen:
        befunde += pruefe_instanz_als_klasse(p31_kanten, kinder,
                                             unter_material | unter_legierung,
                                             labels)
    if "ohne-einordnung" in args.pruefungen:
        if POPULATIONEN[args.population]["pattern"] is None:
            treffer, luecken = pruefe_ohne_einordnung(items, eingeordnet, labels)
            befunde += treffer
        else:
            print("  'ohne-einordnung' uebersprungen: nur fuer die Pruefliste "
                  "sinnvoll, in den SPARQL-Gruppen ist die Klassifikation "
                  "per Definition erfuellt.", file=sys.stderr)
    if "zusammensetzung" in args.pruefungen:
        print("Hole Elementbezeichnungen ...", file=sys.stderr)
        elementnamen = hole_elementnamen()
        # Erst alle Zusammensetzungen lesen, dann EINMAL die Legierungsklassen
        # zu den vorkommenden Basismetallen suchen. Andersherum waere es eine
        # SPARQL-Abfrage je Item.
        basen = set()
        for eintrag in direkt_allgemein.values():
            text = " ".join(filter(None, (eintrag.get("label_de"),
                                          eintrag.get("label_en"))))
            if "%" not in text:
                continue
            anteile, _ = lies_zusammensetzung(text, elementnamen)
            if anteile:
                basen.add(anteile[0][1])
        print(f"  {len(elementnamen)} Elementbezeichnungen, "
              f"{len(basen)} Basismetalle in den Namen", file=sys.stderr)
        if basen:
            klassen, element_luecken = finde_basisklassen(sorted(basen))
            luecken.update({b: g for b, g in element_luecken.items()})
            befunde += pruefe_zusammensetzung(direkt_allgemein, elementnamen,
                                              klassen, graph, labels)

    if "zu-allgemein" in args.pruefungen:
        elemente = hole_elemente(sorted(allgemein_baum))
        begriffe = baue_suchbegriffe(allgemein_baum, elemente)
        print(f"  {len(begriffe)} Suchbegriffe im Kandidatenpool "
              f"({len(elemente)} Elemente/Isotope ausgeschlossen), "
              f"{len(direkt_allgemein)} Items zu pruefen", file=sys.stderr)
        befunde += pruefe_zu_allgemein(
            direkt_allgemein, begriffe, graph, labels,
            {n for n, p, _, _ in verkehrt}, nur_name=args.beleg == "name")
    if "p31-neben-p279" in args.pruefungen:
        befunde += pruefe_p31_neben_p279(p31_kanten, kinder,
                                         set(direkt_allgemein), labels)
    if "parallelzweig" in args.pruefungen:
        befunde += pruefe_parallelzweig(items, unter_material, labels)

    mengengeruest = (
        f"Mengengeruest: {len(items)} Items der Grundgesamtheit, "
        f"{graph.number_of_nodes()} Klassen, {graph.number_of_edges()} "
        f"P279-Kanten"
        + (f", {len(direkt_allgemein)} direkt unter einer allgemeinen Wurzel"
           if direkt_allgemein else "") + ".")

    bericht(befunde, luecken, ohne_item, args.vorsichtig)
    schreibe_empfehlung(befunde, empfehlung_pfad, args.population,
                        luecken, ohne_item, args.vorsichtig, mengengeruest)
    if args.csv:
        schreibe_csv(befunde, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
