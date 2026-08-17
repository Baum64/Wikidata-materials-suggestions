"""
P279-Struktur der Werkstoffe pruefen und Aenderungen als QuickStatements entwerfen
=================================================================================

Der Benchmark in benchmark/ misst, welche MESSWERTE an den Werkstoff-Items
fehlen. Dieses Skript misst etwas anderes: ob die Items ueberhaupt richtig
EINGEHAENGT sind - also wie P279 (Unterklasse von) unterhalb der Werkstoffe
verwendet wird, wo die Kante fehlt, wo sie doppelt ist, wo sie verkehrt herum
zeigt und wo statt P279 faelschlich P31 steht.

Warum ueberhaupt? Aus dem Vorlauf dieses Repos sind drei Befunde bekannt:

  * Wikidata fuehrt "Metall" (Q11426) als UNTERKLASSE von "Legierung"
    (Q37756) - fachlich verkehrt herum. Dadurch haengt jedes Metall samt
    Isotopen unter "Legierung"; materialswiki muss das mit einem Filter
    ausgleichen (LEGIERUNG_OHNE_ELEMENTE). Der Filter kuriert das Symptom,
    die Kante bleibt.
  * Die Gruppierung der benannten Legierungen nach Basismetall, die
    [[en:List of named alloys]] vorgibt (Nickel 13, Silver 11, Iron 9,
    Copper 9, Aluminum 9 ...), existiert in Wikidata so nicht.
  * [[Wikidata:WikiProject Materials/Materials]] wuenscht eine differenzierte
    Einhaengung (Material -> Metallic material -> Alloy -> Ferrous alloy ->
    Steel -> Alloy steel -> ...). Die laesst sich aus dem Basismetall allein
    NICHT ableiten.

Daraus folgt die Arbeitsteilung dieses Skripts, und sie ist die eigentliche
Entwurfsentscheidung: Vorgeschlagen zum Einspielen wird ausschliesslich, was
sich MECHANISCH aus dem Graphen ergibt und keine fachliche Aussage trifft -
also das Entfernen redundanter Kanten. Alles, was eine Einordnung BEHAUPTET,
geht auskommentiert raus. Der Unterschied steht in der Entwurfsdatei als
Abschnittsgrenze, nicht als Fussnote.

Die sieben Pruefungen
---------------------
  1. kennzahlen        Wie wird P279 in der Grundgesamtheit ueberhaupt
                       benutzt: P279, P31, beides, keines; Mehrfacheltern;
                       Tiefe; Wurzeln.
  2. zyklus            Eine Klasse ist ueber P279 ihre eigene Oberklasse.
                       Immer ein Fehler, nie automatisch aufloesbar (welche
                       Kante der Kette falsch ist, sagt der Zyklus nicht).
  3. redundant         Item hat P279 auf A UND auf B, wobei A ueber P279
                       ohnehin bei B landet. Die Kante nach B sagt nichts,
                       was der Graph nicht schon weiss -> ENTFERNEN.
                       Die einzige Pruefung, die einspielbare Zeilen liefert.
                       Aber nur, wenn der Ersatzpfad selbst haelt: laeuft er
                       ueber eine Kante aus Pruefung 4, wird der Befund zu
                       'redundant-unsicher' und bleibt auskommentiert.
  4. verkehrt          Kante n -> p, obwohl unter n mehr haengt als unter p
                       ohne n. Das ist der Metall/Legierung-Fall, generisch
                       gefasst: die Oberklasse haengt unter der Unterklasse.
                       Siehe verkehrt_kandidaten() zur Messgroesse.
  5. instanz-als-klasse  Item hat P31 auf eine Werkstoffklasse, ist aber
                       selbst Oberklasse von etwas. Wer Unterklassen hat, ist
                       eine Klasse und gehoert mit P279 eingehaengt.
  6. ohne-einordnung   Nur fuer die Pruefliste: benannte Legierung ohne jeden
                       P279/P31-Pfad zu "Legierung". Wo es fuer das
                       Basismetall eine Legierungsklasse GIBT, wird sie
                       vorgeschlagen - auskommentiert.
  7. parallelzweig     Item ohne P279*-Pfad zu "material" (Q214609). Kein
                       Fehler (P186 erlaubt mehrere gleichrangige Werttypen,
                       siehe "Kategorie Hirachie/"), aber die Zahl gehoert
                       auf den Tisch.

Alle Pruefungen bleiben in der Werkstoff-Ecke - unterhalb von material
(Q214609) oder Legierung (Q37756), plus die Grundgesamtheit selbst. Das ist
keine Bequemlichkeit: die P279-Huelle nach oben endet zwangslaeufig in der
obersten Ontologie, und dort finden dieselben Pruefungen dieselben Fehler bei
"Begriff", "Typ" oder "Kunstgewerbe". Die Befunde waeren richtig und trotzdem
nicht unsere Sache - eine dort eingespielte Aenderung trifft hunderttausende
Items ausserhalb jedes Werkstoffbezugs.

Ausgabe
-------
  p279_befunde_<Zeitstempel>.csv        alle Befunde, eine Zeile je Befund
  quickstatements_p279_<Zeitstempel>.txt  Entwurf, Abschnitt 1 einspielbar

Aufruf
------
  python "P279-structure/P279benchmark.py"
  python "P279-structure/P279benchmark.py" --population benannte-legierungen
  python "P279-structure/P279benchmark.py" --population material --pruefungen redundant zyklus
  python "P279-structure/P279benchmark.py" --vorsichtig    # nichts einspielbar
"""

import argparse
import csv
import datetime as dt
import os
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
              "instanz-als-klasse", "ohne-einordnung", "parallelzweig"]

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
    "Kategorie Hirachie/material_hierarchy_check.py".

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
MELDE_ABSCHNITTE = [
    ("verkehrt", "VERDACHT AUF VERKEHRTE KANTE",
     ["Die weitere Klasse haengt unter der engeren. Ob die Kante zu",
      "entfernen oder umzudrehen ist, sagt der Graph nicht."]),
    ("redundant-unsicher", "REDUNDANT, ABER NICHT SICHER",
     ["Formal redundant, aber der Ersatzpfad laeuft ueber eine Kante aus",
      "Abschnitt 2. Faellt die, faellt mit der hier entfernten zusammen die",
      "ganze Einordnung. Erst die Kante oben klaeren, dann diese Zeilen."]),
    ("zyklus", "P279-ZYKLUS",
     ["Immer ein Fehler, aber der Zyklus sagt nicht, welche Kante der",
      "Kette ihn verursacht."]),
    ("instanz-als-klasse", "P31 STATT P279",
     ["Das Item hat Unterklassen, ist also eine Klasse. Beides zugleich",
      "ist trotzdem moeglich - dann ist die Zeile hier gegenstandslos."]),
    ("ohne-einordnung", "OHNE EINORDNUNG ALS LEGIERUNG",
     ["Die Einhaengung in die Klassenhierarchie ist eine fachliche",
      "Entscheidung. [[Wikidata:WikiProject Materials/Materials]] verlangt",
      "eine differenzierte Einordnung, die sich aus dem Basismetall allein",
      "nicht ableiten laesst."]),
    ("parallelzweig", "OHNE PFAD ZU MATERIAL (Q214609)",
     ["Kein Fehler: P186 erlaubt mehrere gleichrangige Werttypen",
      "nebeneinander. Nur zur Kenntnis."]),
]


def abschnitt_kopf(titel: str, anzahl: int, erklaerung: list) -> list:
    zeilen = ["", _TRENNER,
              f"# {titel} ({anzahl} {'Befund' if anzahl == 1 else 'Befunde'})"]
    zeilen += [f"# {z}" for z in erklaerung]
    zeilen.append(_TRENNER)
    return zeilen


def schreibe_quickstatements(befunde: list, pfad: str, population: str,
                             vorsichtig: bool) -> None:
    """QuickStatements-V1-Entwurf. Abschnitt 1 ist einspielbar, alles danach
    ist durchgehend auskommentiert.

    Dieselbe Bauart wie in materialswiki: die Datei laesst sich komplett nach
    QuickStatements kopieren, ohne dass aus einer der Meldezeilen
    versehentlich eine Aussage wird.
    """
    einspielbar = [] if vorsichtig else [
        b for b in befunde if b["befund"] == "redundant"]
    ids = {id(b) for b in einspielbar}

    zeilen = [
        _TRENNER,
        "# ENTWURF - vor Verwendung jede Zeile manuell pruefen!",
        f"# P279-Struktur, Grundgesamtheit '{population}', "
        f"erzeugt {dt.datetime.now():%Y-%m-%d %H:%M}",
        "#",
        "# Aufbau dieser Datei:",
        f"#   ABSCHNITT 1  EINSPIELBAR ........ {len(einspielbar):4d}  "
        "(die einzigen ausfuehrbaren Zeilen)",
    ]
    for i, (art, titel, _) in enumerate(MELDE_ABSCHNITTE, 2):
        anzahl = sum(1 for b in befunde if b["befund"] == art)
        zeilen.append(f"#   ABSCHNITT {i}  {titel[:28]:<28} {anzahl:4d}  "
                      "(auskommentiert)")
    zeilen += [
        "#",
        "# Ausserhalb von Abschnitt 1 beginnt jede Zeile mit '#'.",
        "#",
        "# Warum steht so wenig in Abschnitt 1? Weil nur das Entfernen einer",
        "# redundanten Kante MECHANISCH aus dem Graphen folgt und dabei nichts",
        "# behauptet: nach dem Entfernen gilt dieselbe Klassenzugehoerigkeit,",
        "# nur abgeleitet statt doppelt notiert. Jede Aussage darueber, wo ein",
        "# Werkstoff HINGEHOERT, ist dagegen fachlich und steht auskommentiert.",
        "#",
        "# '-QID<TAB>P279<TAB>QID' entfernt eine Aussage, ohne Minus setzt sie.",
        _TRENNER,
    ]

    zeilen += abschnitt_kopf(
        "ABSCHNITT 1: EINSPIELBAR", len(einspielbar),
        ["Nur diese Zeilen sind QuickStatements-Syntax. Trotzdem gilt:",
         "erst nach zeilenweiser Pruefung einspielen."]
        + (["(--vorsichtig gesetzt: Abschnitt bleibt bewusst leer)"]
           if vorsichtig else []))
    for b in einspielbar:
        zeilen.append(b["quickstatements"])
        zeilen.append(f"# {b['label']}: {b['begruendung']}")
    if not einspielbar:
        zeilen.append("# (keine)")

    for i, (art, titel, erklaerung) in enumerate(MELDE_ABSCHNITTE, 2):
        teil = [b for b in befunde if b["befund"] == art and id(b) not in ids]
        zeilen += abschnitt_kopf(f"ABSCHNITT {i}: {titel} - NICHT EINSPIELEN",
                                 len(teil), erklaerung)
        if not teil:
            zeilen.append("# (keine)")
        for b in teil:
            for qs in (b["quickstatements"] or "").splitlines():
                zeilen.append(f"# {qs}")
            zeilen.append(f"# {b['qid']} {b['label']}: {b['begruendung']}")
            zeilen.append(f"#     -> {b['entscheidung']}")

    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"QuickStatements-Entwurf geschrieben nach: {pfad}", file=sys.stderr)


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
    kz = [b for b in befunde if b["befund"] == "kennzahl"]
    if kz:
        print()
        print("Wie P279 hier benutzt wird")
        print("-" * 52)
        for b in kz:
            print(f"  {b['label']:<44}{b['kennzahl']:>6}")

    print()
    print("Befunde")
    print("-" * 52)
    for art in [a for a, _, _ in MELDE_ABSCHNITTE] + ["redundant"]:
        teil = [b for b in befunde if b["befund"] == art]
        entwurf = sum(1 for b in teil if b["quickstatements"])
        if not teil:
            continue
        marke = ("einspielbar" if art == "redundant" and not vorsichtig
                 else "auskommentiert")
        if art == "redundant" and vorsichtig:
            marke += " (--vorsichtig)"
        art = art if art != "redundant-unsicher" else "redundant (unsicher)"
        print(f"  {art:<22}{len(teil):>5}   davon mit Entwurf {entwurf:>4}  "
              f"({marke})")

    if luecken:
        print()
        print("Basismetalle ohne Legierungsklasse in Wikidata")
        print("-" * 52)
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
    parser.add_argument("--csv", default=None,
                        help="Ziel der Befund-CSV (Default: "
                             "p279_befunde_<Zeitstempel>.csv)")
    parser.add_argument("--qs-out", default=None,
                        help="Ziel des Entwurfs (Default: "
                             "quickstatements_p279_<Zeitstempel>.txt)")
    args = parser.parse_args(argv)

    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_pfad = args.csv or f"p279_befunde_{stempel}.csv"
    qs_pfad = args.qs_out or f"quickstatements_p279_{stempel}.txt"

    items, ohne_item = hole_population(args.population, args.limit)
    if not items:
        raise SystemExit("Grundgesamtheit ist leer - nichts zu pruefen.")
    qids = sorted(items)

    # Ein Graph fuer alles: die Huelle wird einmal geholt, danach laufen
    # Zyklen-, Redundanz- und Verkehrt-Pruefung lokal. Per SPARQL waere jede
    # davon eine eigene teure Abfrage.
    print("Hole P279-Huelle nach oben ...", file=sys.stderr)
    kanten = hole_p279_huelle(qids)
    graph = nx.DiGraph()
    graph.add_nodes_from(qids)
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

    braucht_p31 = {"instanz-als-klasse", "kennzahlen", "ohne-einordnung"}
    p31_kanten = (hole_p31_kanten(qids)
                  if braucht_p31 & set(args.pruefungen) else [])
    # Ueber P31 eingeordnet zaehlt genauso: "X ist ein/e Legierung".
    ueber_p31 = {i for i, k in p31_kanten if k in unter_legierung}
    eingeordnet = (unter_legierung | ueber_p31) & set(qids)

    braucht_kinder = {"instanz-als-klasse", "kennzahlen"}
    kinder = (hole_kinder(qids)
              if braucht_kinder & set(args.pruefungen) else {})

    # Die Verkehrt-Pruefung braucht einen ZWEITEN Graphen: die vollstaendige
    # Huelle nach UNTEN unter der Bereichswurzel. Grund steht bei
    # verkehrt_kandidaten - in der Aufwaerts-Huelle sind die Unterbaugroessen
    # der oberen Klassen ein Artefakt der Abfrage, und das Ergebnis besteht
    # dann fast nur aus Entitaet, Objekt, Materie und Substanz.
    # Auch fuer 'redundant' noetig, nicht nur fuer 'verkehrt': ein
    # Ersatzpfad ueber eine beanstandete Kante taugt nicht als Nachweis, dass
    # eine Kante entbehrlich ist. Siehe pruefe_redundant.
    verkehrt = []
    if {"verkehrt", "redundant"} & set(args.pruefungen):
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
                      | {q for n, p, _, _ in verkehrt for q in (n, p)})
    print(f"Hole {len(zu_beschriften)} Bezeichnungen ...", file=sys.stderr)
    labels = hole_labels(sorted(zu_beschriften))

    befunde, luecken = [], {}
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
    if "parallelzweig" in args.pruefungen:
        befunde += pruefe_parallelzweig(items, unter_material, labels)

    bericht(befunde, luecken, ohne_item, args.vorsichtig)
    schreibe_csv(befunde, csv_pfad)
    schreibe_quickstatements(befunde, qs_pfad, args.population,
                             args.vorsichtig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
