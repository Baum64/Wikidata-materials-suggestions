"""
Anwendungen von Werkstoffen als QuickStatements entwerfen
=========================================================

materialswiki holt MESSWERTE (Dichte, Raumgruppe, Moduln), P279-structure
prueft die EINORDNUNG. Dieses Skript nimmt sich das Dritte vor: wozu ein
Werkstoff GEBRAUCHT wird - P366 (Verwendung) am Werkstoff, P186 (Material)
am Anwendungsitem, P2079 (Herstellungsverfahren) am Werkstoff.

Woher soll das Wissen kommen?
-----------------------------
Nicht aus einer handgeschriebenen Liste "Bronze -> Glocke". Die waere
schnell getippt, aber unbelegt, und dieses Repo schlaegt nichts vor, was es
nicht zeigen kann. Die Quelle ist Wikidata selbst, und zwar die eine Kante,
die dort schon massenhaft gepflegt ist: P186 an den Objekten.

  * P366 am Werkstoff:  1082 Legierungen, davon tragen die wenigsten eine
    Verwendung.
  * P186 an Objekten:   4739 Werkstoffe werden von irgendeinem Item als
    Material genannt - Skulpturen, Muenzen, Glocken, Fahrzeugtypen.
    (beides gemessen 2026-08-22)

Aus dieser Schieflage kommt die Hauptableitung: wenn 30 roemische Muenzen
P186 -> Oreichalkos tragen, dann ist "Muenze" eine Verwendung von
Oreichalkos. Nicht geraten, sondern aus 30 vorhandenen Aussagen aggregiert,
und jede Vorschlagszeile nennt ihre Belegzahl.

Warum die Rueckrichtung NICHT symmetrisch ist
---------------------------------------------
Der naheliegende Umkehrschluss - "Neusilber P366 Muenze, also Muenze P186
Neusilber" - ist falsch, und zwar nicht am Rand, sondern im Regelfall. Er
verwechselt zwei Quantoren:

    P366 am Werkstoff:  MANCHE Muenzen sind aus Neusilber.   (richtig)
    P186 an der Klasse: ALLE Muenzen sind aus Neusilber.     (Unsinn)

Deshalb wird die Rueckkante nur dort vorgeschlagen, wo das Anwendungsitem
ein EINZELDING ist (keine Instanzen, keine Unterklassen) - bei einer
konkreten Glocke stimmt die Aussage. Bei einer Klasse geht dieselbe Zeile
auskommentiert raus, mit dem Quantorenhinweis daneben.

Zwei weitere Faelle faengt die Vorpruefung ab:
  * Der P366-Wert ist eine TAETIGKEIT (Schweissen, Loeten, Giessen,
    Halbleitertechnik). Ein Vorgang besteht aus keinem Material - hier gibt
    es keine Rueckkante, das ist kein Mangel.
  * Der P366-Wert ist ein FERTIGUNGSVERFAHREN. Dann ist moeglicherweise
    P2079 gemeint und nicht P366. Das ist eine Frage, keine Aussage, und
    landet im Klaerungsabschnitt.

P2079 ist fast leer
-------------------
Unter den Legierungen tragen 13 Items ueberhaupt ein P2079 (gemessen
2026-08-22). Damit gibt es fuer P2079 keine Datenbasis, aus der sich etwas
aggregieren liesse - nur die Vererbung entlang P279 (die Unterklasse eines
Stahls wird wie der Stahl erzeugt), und die ist eine Behauptung, keine
Ableitung. Sie geht deshalb vollstaendig auskommentiert raus. Die Zahl
selbst ist das eigentliche Ergebnis fuer P2079: hier fehlt nicht ein
Vorschlag, hier fehlt die Grundgesamtheit.

Die fuenf Pruefungen
--------------------
  1. p366-aus-p186   Objekte mit P186 -> Werkstoff, gruppiert nach ihrer
                     Klasse (P31). Ab --min-belege Objekten wird die Klasse
                     als Verwendung vorgeschlagen. EINSPIELBAR.
                     Vier Filter haengen daran, und sie sind der
                     eigentliche Inhalt der Pruefung:
                       KLASSEN_SPERRE  wirft die Klassen raus, die keine
                         Verwendung bezeichnen, sondern einen Fundumstand
                         oder Schutzstatus ("archaeologischer Fund",
                         "Kulturdenkmal").
                       VERBUND         wirft raus, was nur zu einem kleinen
                         Teil aus dem Werkstoff besteht - Gebaeude, Bruecke,
                         Turm, Fahrzeug, Maschine. Siehe VERBUND_WURZELN,
                         auch dazu, warum das nicht am Anteil gemessen wird.
                       ZU SPEZIELL     wirft raus, was in weniger als
                         --min-sprachen Wikipedias existiert und damit als
                         Verwendung zu eng gefasst ist ("Carteluhr",
                         "NHCP historical marker").
                       UEBERDECKUNG    wirft raus, was eine allgemeinere
                         Klasse mit mindestens so vielen Belegen schon
                         abdeckt - sonst stuenden neben "Bronze fuer
                         Skulpturen" noch Statue, Statuette, Portraetbueste
                         und Gedenkbueste.
                     Nur der erste Filter loescht. Was die drei anderen
                     aussortieren, steht auskommentiert in den Abschnitten
                     2 bis 4 - zum Nachsehen, nicht zum Wegwerfen.
  2. p186-einzelding P366 am Werkstoff vorhanden, Rueckkante P186 fehlt,
                     und das Anwendungsitem ist ein Einzelding. EINSPIELBAR.
  3. p186-klasse     dasselbe, aber das Anwendungsitem ist eine Klasse.
                     Auskommentiert - siehe Quantoren oben.
  4. p2079-vererbt   Werkstoff ohne P2079, eine P279-Oberklasse hat eines.
                     Auskommentiert.
  5. p366-verfahren  P366 zeigt auf ein Fertigungsverfahren. Klaerung:
                     vielleicht war P2079 gemeint.

Zusaetzlich zaehlt der Bericht die Werkstoffe ohne jede Anwendungsangabe -
ohne P366 und ohne einen einzigen P186-Rueckverweis. Fuer die kann dieses
Skript nichts tun; die Zahl sagt, wie gross die Luecke wirklich ist.

Ausgabe
-------
  anwendungen_befunde_<Zeitstempel>.csv        alle Befunde
  quickstatements_anwendungen_<Zeitstempel>.txt  Entwurf, Abschnitt 1
                                                 einspielbar

Aufruf
------
  python "Anwendung/Anwendung.py"
  python "Anwendung/Anwendung.py" --population metallischer-werkstoff
  python "Anwendung/Anwendung.py" --min-belege 5 --pruefungen p366-aus-p186
  python "Anwendung/Anwendung.py" --vorsichtig    # nichts einspielbar
"""

import argparse
import collections
import csv
import datetime as dt
import os
import sys
import time
from typing import Optional

import requests

# Repo-Wurzel in den Pfad - dasselbe Vorgehen wie in P279-structure: die
# Grundgesamtheiten werden aus materialswiki importiert, nicht kopiert,
# sonst meinen die Werkzeuge irgendwann verschiedene Mengen.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import konfig  # noqa: E402
from materialswiki.cli import (  # noqa: E402
    LEGIERUNG_OHNE_ELEMENTE, LEGIERUNG_PATTERN,
)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
# Kontaktadresse aus .env - siehe .env.beispiel.
USER_AGENT = ("MaterialsWikidataApplicationBot/0.1 "
              f'(mailto:{konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")})')
HEADERS = {"User-Agent": USER_AGENT}

MATERIAL_QID = "Q214609"           # material
METALL_WERKSTOFF_QID = "Q1924900"  # metallischer Werkstoff

# Wurzeln fuer die Vorpruefung eines P366-Wertes. Die Auswahl ist gemessen,
# nicht geraten: gegen die tatsaechlich vorkommenden Werte geprueft
# (2026-08-22), und dort trennen genau diese Wurzeln sauber.
#   Schweissen, Loeten, Giessen, Messung, Halbleitertechnik -> Taetigkeit
#   Muenze, Thermometer, Mauer, Dauermagnet, Feder          -> Objekt
AKTIVITAET_WURZELN = {
    "Q1914636": "Tätigkeit",
    "Q3249551": "Prozess",
    "Q2695280": "Technik",
}
OBJEKT_WURZELN = {
    "Q223557": "physisches Objekt",
}
# Fertigungsverfahren: Teilmenge der Taetigkeiten, bei der die Verwechslung
# mit P2079 naheliegt.
VERFAHREN_WURZELN = {
    "Q1408657": "Herstellungsverfahren",
    "Q2695280": "Technik",
}

# Verbundgegenstaende: Klassen, bei denen KEIN Werkstoff den Gegenstand
# ausmacht. Ein Wolkenkratzer hat ein Stahlskelett, ein Kameragehaeuse eine
# Magnesiumschale - der Werkstoff ist dort ein Bauteil, nicht das Ding.
#
# Warum ueber Wurzeln und nicht ueber den gemessenen Anteil? Weil der Anteil
# in Wikidata nirgends steht. Von 127.000 P186-Aussagen an diesen Werkstoffen
# traegt KEINE EINZIGE den Qualifikator P518 "bezogen auf" (gemessen
# 2026-08-22), und die Zahl der Materialien am Objekt trennt auch nicht: 92
# bis 99 % der Objekte nennen hoechstens drei. Ein Wolkenkratzer steht dort
# mit "Stahl" allein, genau wie eine Muenze mit "Bronze". Die Unterscheidung
# muss deshalb an der KLASSE haengen.
#
# Die Wurzeln sind eng gewaehlt, und zwar gegen die Vorgaenger-Fassung
# geprueft: "Bauwerk" (Q811979) als Wurzel faengt Gedenktafel, Flurkreuz und
# Zierbrunnen mit - die sind vollstaendig aus dem Werkstoff und gehoeren
# nicht hierher. Gebaeude, Bruecke, Turm, Fahrzeug und Maschine trennen
# sauber (Wolkenkratzer, Leuchtturm, Strassenbruecke, U-Boot, Torpedo ja;
# Muenze, Glocke, Skulptur, Astrolabium, Leuchter, Tisch nein).
VERBUND_WURZELN = {
    "Q41176": "Gebäude",
    "Q12280": "Brücke",
    "Q12518": "Turm",
    "Q42889": "Fahrzeug",
    "Q11019": "Maschine",
}

# "Bauwerk" selbst ist der Oberbegriff der Verbundwurzeln und damit erst
# recht einer - nur haengt es nicht UNTER ihnen, sondern darueber. Die
# Subtree-Pruefung findet es deshalb nicht; es wird exakt verglichen.
VERBUND_EXAKT = {
    "Q811979": "Bauwerk",
}

# Klassen, bei denen der Werkstoff regelmaessig nur das Beiwerk ist. Die
# Hierarchie sagt das nicht - ein Gemaelde ist kein Gebaeude -, die Sache
# schon. Jeder Eintrag nennt, WO der Werkstoff sitzt; ohne diese Begruendung
# gehoert hier nichts hinein.
TEILWERKSTOFF_KLASSEN = {
    "Q3305213": "Gemälde - das Metall ist Bildträger, Pigment oder Rahmen, "
                "nicht das Bild",
    "Q11460":   "Kleidung - das Metall sitzt an Knöpfen, Schnallen und "
                "Reißverschlüssen",
}

# Klassen, die als P366-Wert nie gemeint sein koennen, mit dem Grund. Die
# Liste ist nicht theoretisch zusammengestellt, sondern aus einem Lauf ueber
# die Legierungen gezogen (2026-08-22): das sind die Klassen, die oben in der
# Aggregation stehen und trotzdem keine VERWENDUNG bezeichnen.
#
# Der gemeinsame Nenner: sie beschreiben, was mit dem Objekt PASSIERT IST -
# gefunden, unter Schutz gestellt, ins Depot gelegt, zerbrochen - oder sie
# sagen gar nichts ("Objekt"). Wozu der Werkstoff gebraucht wird, steht in
# keiner von ihnen. Ohne den Filter waere "Bronze wird fuer archaeologische
# Funde verwendet" ein Vorschlag mit 647 Belegen.
KLASSEN_SPERRE = {
    # Wikimedia-Innenleben
    "Q4167410":  "Begriffsklärungsseite",
    "Q13406463": "Wikimedia-Liste",
    "Q11266439": "Wikimedia-Vorlage",
    "Q4167836":  "Wikimedia-Kategorie",
    "Q17442446": "Wikimedia-internes Objekt",
    # nichtssagend: trifft auf jeden Gegenstand zu
    "Q488383":   "Objekt - sagt nichts über die Verwendung",
    "Q220659":   "Artefakt - jeder gefertigte Gegenstand ist einer",
    "Q1204499":  "Ding - sagt nichts über die Verwendung",
    "Q386724":   "Werk - sagt nichts über die Verwendung",
    "Q32880":    "Baustil - ein Stil, kein Gegenstand",
    "Q1232589":  "Nachbildung - Herstellungsanlass, nicht Verwendung",
    # Fundumstand, nicht Zweck
    "Q10855061": "archäologischer Fund - Fundumstand, nicht Verwendung",
    "Q2686349":  "archäologischer Befund - Fundumstand",
    "Q814254":   "Befund - Fundumstand",
    "Q164099":   "Depotfund - Fundumstand",
    "Q272937":   "Schatz - Fundumstand",
    # Erhaltungs- und Entwicklungszustand
    "Q11086567": "Fragment - Erhaltungszustand",
    "Q15893266": "ehemalige Entität - Zustand, nicht Zweck",
    "Q207977":   "Prototyp - Entwicklungsstand",
    # Schutzstatus und Verwahrung
    "Q61058374": "Monument historique (Objekt) - Denkmalschutzstatus",
    "Q2065736":  "Kulturdenkmal - Denkmalschutzstatus",
    "Q210272":   "Kulturerbe - Schutzstatus",
    "Q2342494":  "Sammlungsobjekt - Verwahrort",
    # Metaklassen: ihre Instanzen sind Typen, keine Gegenstände
    "Q16887380": "Gruppe - Gruppierungsklasse, kein Gegenstand",
    "Q3331189":  "Ausgabe oder Version - Metaklasse",
    "Q63981612": "Produktkategorie - Metaklasse",
    "Q128889633": "Produkttyp - Metaklasse",
}

SUBTREE_PATTERN = (
    "{{ ?i wdt:P31/wdt:P279* wd:{root} }} UNION {{ ?i wdt:P279* wd:{root} }}"
)

POPULATIONEN = {
    "legierungen": {
        "pattern": LEGIERUNG_PATTERN,
        "beschreibung": "Legierungen (Q37756, ohne Elemente und Isotope)",
    },
    "metallischer-werkstoff": {
        "pattern": (SUBTREE_PATTERN.format(root=METALL_WERKSTOFF_QID)
                    + " " + LEGIERUNG_OHNE_ELEMENTE),
        "beschreibung": "unterhalb von metallischer Werkstoff (Q1924900)",
    },
    "material": {
        "pattern": (SUBTREE_PATTERN.format(root=MATERIAL_QID)
                    + " " + LEGIERUNG_OHNE_ELEMENTE),
        "beschreibung": "unterhalb von material (Q214609)",
    },
}

PRUEFUNGEN = ["p366-aus-p186", "p186-einzelding", "p186-klasse",
              "p2079-vererbt", "p366-verfahren"]

# VALUES-Bloecke. 150 QIDs sind der Kompromiss aus P279-structure: gross
# genug, dass die Zahl der Anfragen ertraeglich bleibt, klein genug, dass
# der Query-Service nicht ins 60s-Timeout laeuft.
BLOCK = 150


# ---------------------------------------------------------------------------
# HTTP mit Drosselung und Backoff
# ---------------------------------------------------------------------------
#
# Woertlich wie in P279-structure/P279benchmark.py. Bewusst kopiert statt
# importiert: dieses Skript soll nicht networkx mitziehen, nur weil das
# andere es braucht.

REQUEST_DELAY_SEC = 1.0
_LETZTE_ANFRAGE = 0.0


def request_with_retry(method: str, url: str, attempts: int = 5,
                       timeout: int = 120, **kwargs):
    """Einziger HTTP-Einstiegspunkt: drosselt auf 1 Anfrage/s und wiederholt
    bei 429/5xx.

    Der Query-Service antwortet unter Last sporadisch mit 429/502; ohne
    Retry reisst ein einzelner Ausfall den ganzen Lauf ab.
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


def bloecke(qids: list, groesse: int = BLOCK):
    for i in range(0, len(qids), groesse):
        yield qids[i:i + groesse]


def values(qids: list, variable: str = "?i") -> str:
    return f"VALUES {variable} {{ " + " ".join(f"wd:{q}" for q in qids) + " }"


# ---------------------------------------------------------------------------
# Abfragen
# ---------------------------------------------------------------------------

def hole_population(name: str, limit: Optional[int] = None) -> dict:
    """{qid: label} der Grundgesamtheit."""
    grenze = f"LIMIT {limit}" if limit else ""
    zeilen = sparql(f"""
    SELECT DISTINCT ?i ?iLabel WHERE {{
      {POPULATIONEN[name]["pattern"]}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }} {grenze}
    """)
    return {qid_aus(b, "i"): b.get("iLabel", {}).get("value", "")
            for b in zeilen}


def hole_p366(qids: list) -> dict:
    """{werkstoff: {anwendung, ...}} - die bereits vorhandenen Verwendungen."""
    treffer = collections.defaultdict(set)
    for teil in bloecke(qids):
        for b in sparql(f"""SELECT ?i ?a WHERE {{
          {values(teil)}
          ?i wdt:P366 ?a .
        }}"""):
            treffer[qid_aus(b, "i")].add(qid_aus(b, "a"))
    return treffer


def hole_p186_rueck(qids: list) -> tuple:
    """({werkstoff: {klasse: {objekt, ...}}}, {werkstoff: anzahl_objekte}).

    Ein Objekt ohne P31 zaehlt fuer die Gesamtzahl mit, aber nicht fuer eine
    Klasse - es belegt, dass der Werkstoff verbaut wird, sagt aber nicht
    wozu.
    """
    nach_klasse = collections.defaultdict(lambda: collections.defaultdict(set))
    objekte = collections.defaultdict(set)
    for teil in bloecke(qids):
        for b in sparql(f"""SELECT ?i ?a ?c WHERE {{
          {values(teil)}
          ?a wdt:P186 ?i .
          OPTIONAL {{ ?a wdt:P31 ?c }}
        }}"""):
            werkstoff, objekt = qid_aus(b, "i"), qid_aus(b, "a")
            objekte[werkstoff].add(objekt)
            if "c" in b:
                nach_klasse[werkstoff][qid_aus(b, "c")].add(objekt)
    return nach_klasse, objekte


def hole_p186_vorhanden(paare: list) -> set:
    """{(objekt, werkstoff)} - welche Rueckkanten es schon gibt."""
    vorhanden = set()
    ziele = sorted({a for a, _ in paare})
    for teil in bloecke(ziele):
        for b in sparql(f"""SELECT ?a ?m WHERE {{
          {values(teil, "?a")}
          ?a wdt:P186 ?m .
        }}"""):
            vorhanden.add((qid_aus(b, "a"), qid_aus(b, "m")))
    return vorhanden


def hole_p2079(qids: list) -> dict:
    """{werkstoff: {verfahren, ...}}."""
    treffer = collections.defaultdict(set)
    for teil in bloecke(qids):
        for b in sparql(f"""SELECT ?i ?v WHERE {{
          {values(teil)}
          ?i wdt:P2079 ?v .
        }}"""):
            treffer[qid_aus(b, "i")].add(qid_aus(b, "v"))
    return treffer


def hole_p279_eltern(qids: list) -> dict:
    """{kind: {elter, ...}} - nur die direkten Kanten."""
    treffer = collections.defaultdict(set)
    for teil in bloecke(qids):
        for b in sparql(f"""SELECT ?i ?p WHERE {{
          {values(teil)}
          ?i wdt:P279 ?p .
        }}"""):
            treffer[qid_aus(b, "i")].add(qid_aus(b, "p"))
    return treffer


def klassifiziere(qids: list) -> dict:
    """{qid: {'aktivitaet', 'objekt', 'verfahren', 'material'}} als Mengen von
    Wurzeln, die das Item erreicht.

    Ein Item kann mehrere Rollen treffen (Mokume-Gane ist Technik UND
    Objekt) - deshalb Mengen statt einer Entscheidung. Wer entscheidet,
    steht bei den Pruefungen, nicht hier.
    """
    wurzeln = (list(AKTIVITAET_WURZELN) + list(OBJEKT_WURZELN)
               + list(VERFAHREN_WURZELN) + list(VERBUND_WURZELN)
               + [MATERIAL_QID])
    rollen = {q: set() for q in qids}
    for teil in bloecke(qids, 80):   # zwei VALUES-Bloecke: kleiner halten
        for b in sparql(f"""SELECT DISTINCT ?a ?w WHERE {{
          {values(teil, "?a")}
          {values(sorted(set(wurzeln)), "?w")}
          {{ ?a wdt:P279* ?w }} UNION {{ ?a wdt:P31/wdt:P279* ?w }}
        }}"""):
            rollen[qid_aus(b, "a")].add(qid_aus(b, "w"))
    return rollen


def hole_hat_nachfolger(qids: list) -> set:
    """{qid} derer, die Instanzen oder Unterklassen haben - also Klassen.

    Das Gegenteil ist die Definition von 'Einzelding' in diesem Skript: was
    nichts unter sich hat, ist ein konkretes Ding, und fuer das laesst sich
    P186 ohne Quantorensprung behaupten.
    """
    klassen = set()
    for teil in bloecke(qids, 80):
        for b in sparql(f"""SELECT DISTINCT ?a WHERE {{
          {values(teil, "?a")}
          {{ ?x wdt:P31 ?a }} UNION {{ ?x wdt:P279 ?a }}
        }}"""):
            klassen.add(qid_aus(b, "a"))
    return klassen


def hole_sitelinks(qids: list) -> dict:
    """{qid: Zahl der Wikipedia-Sprachversionen}.

    Das Mass fuer "wie allgemein ist dieser Begriff". Kein perfektes, aber
    ein billiges und erstaunlich trennscharfes: Muenze 129, Bruecke 202,
    Werkzeug 137 - Carteluhr 4, "National Historical Commission of the
    Philippines historical marker" 3, Digitalkamera-Modell 0 (gemessen
    2026-08-22). Wo eine Klasse nur in einer Handvoll Wikipedias existiert,
    ist sie als VERWENDUNG eines Werkstoffs zu eng gefasst.

    Die Schwaeche steht im README: "Skulptur" hat nur 26. Eine hoehere
    Schwelle als 10 wuerde also anfangen, gute Verwendungen zu treffen.
    """
    treffer = {}
    for teil in bloecke(qids):
        for b in sparql(f"""SELECT ?i ?n WHERE {{
          {values(teil)}
          ?i wikibase:sitelinks ?n .
        }}"""):
            treffer[qid_aus(b, "i")] = int(b["n"]["value"])
    return treffer


def hole_oberklassen(qids: list) -> dict:
    """{qid: {oberklasse, ...}} - die volle P279-Huelle nach oben.

    Unbeschraenkt geholt und erst lokal auf die Kandidaten eingeengt. Die
    Alternative - beide Seiten als VALUES-Block - waere bei knapp tausend
    Kandidaten ein Kreuzprodukt, das der Query-Service abbricht.
    """
    huelle = collections.defaultdict(set)
    for teil in bloecke(qids, 60):
        for b in sparql(f"""SELECT DISTINCT ?a ?o WHERE {{
          {values(teil, "?a")}
          ?a wdt:P279+ ?o .
        }}"""):
            huelle[qid_aus(b, "a")].add(qid_aus(b, "o"))
    return huelle


def hole_labels(qids: list) -> dict:
    labels = {}
    for teil in bloecke(qids):
        for b in sparql(f"""SELECT ?i ?iLabel WHERE {{
          {values(teil)}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
        }}"""):
            labels[qid_aus(b, "i")] = b.get("iLabel", {}).get("value", "")
    return labels


# ---------------------------------------------------------------------------
# Pruefungen
# ---------------------------------------------------------------------------

def befund(art: str, qid: str, ziel: str, kennzahl, qs: str,
           begruendung: str, entscheidung: str) -> dict:
    return {"befund": art, "qid": qid, "ziel_qid": ziel, "kennzahl": kennzahl,
            "quickstatements": qs, "begruendung": begruendung,
            "entscheidung": entscheidung}


def pruefe_p366_aus_p186(nach_klasse: dict, p366: dict, rollen: dict,
                         oberklassen: dict, sitelinks: dict, min_belege: int,
                         min_sprachen: int) -> list:
    """Aggregation: >= min_belege Objekte einer Klasse aus demselben
    Werkstoff -> die Klasse ist eine Verwendung des Werkstoffs.

    Danach die Ueberdeckung: liefert ein Werkstoff Vorschlaege fuer Skulptur
    (11353 Belege), Statue (3168), Statuette (915) und Portraetbueste (636),
    ist die erste Zeile die Aussage und der Rest ihr Echo. Weg kommt, wozu
    es eine ALLGEMEINERE Kandidatenklasse mit mindestens so vielen Belegen
    gibt: die deckt den Fall bereits ab, und die engere Zeile behauptet mehr,
    ohne besser belegt zu sein.

    Bewusst nur in diese Richtung. Die naheliegende Variante - jede
    P279-Kette auf ihr bestbelegtes Glied zusammenziehen - wuerde ueber
    kaputte Kanten hinweg zusammenziehen, und davon gibt es hier reichlich:
    Wikidata fuehrt "Muenze" als Unterklasse von "Skulptur" (siehe
    P279-structure). Ueber diese Kante wuerde die Skulptur-Zeile geloescht,
    weil die Muenz-Zeile mehr Belege hat. So herum kann das nicht passieren:
    die bestbelegte Klasse einer Kette faellt nie.

    Davor liegen zwei Aussortierungen, die nichts mit Redundanz zu tun
    haben, sondern damit, was ueberhaupt eine brauchbare Verwendung ist:

      * VERBUND - der Gegenstand besteht nur zu einem kleinen Teil aus dem
        Werkstoff (Wolkenkratzer, Bruecke, U-Boot, Kameragehaeuse). Die
        Aussage ist nicht falsch, aber sie behauptet mehr, als das Objekt
        hergibt.
      * ZU SPEZIELL - die Klasse existiert in weniger als --min-sprachen
        Wikipedias und ist als Verwendung zu eng gefasst (Carteluhr,
        Tuellenbeil, "NHCP historical marker"). Statt ihrer taugt die
        Oberklasse, die es hier oft gar nicht als Kandidat gibt.

    Beide loeschen nichts: die Zeilen stehen auskommentiert in ihren
    eigenen Abschnitten. Und beide werden VOR der Ueberdeckung angewandt,
    damit eine aussortierte Klasse nie eine gute verdraengt.
    """
    treffer, ueberdeckt, verbund, speziell = [], [], [], []
    for werkstoff, klassen in nach_klasse.items():
        kandidaten = {}
        for klasse, objekte in klassen.items():
            if len(objekte) < min_belege:
                continue
            if klasse in p366.get(werkstoff, ()):
                continue            # steht schon da
            if klasse == werkstoff:
                continue            # "X wird als X verwendet"
            if klasse in KLASSEN_SPERRE:
                continue
            if MATERIAL_QID in rollen.get(klasse, ()):
                # Ein Werkstoff als Verwendung eines Werkstoffs ist keine
                # Anwendung, sondern eine Materialbeziehung - dafuer gibt es
                # P527 (materialswiki) und P186.
                continue
            rolle = rollen.get(klasse, set())
            if (rolle & set(AKTIVITAET_WURZELN)
                    and not rolle & set(OBJEKT_WURZELN)):
                # Die Kandidaten kommen aus dem P31 von GEGENSTAENDEN. Steht
                # dort eine Taetigkeit ("Metallverarbeitung"), ist die
                # P31-Aussage am Objekt falsch - daraus laesst sich keine
                # Verwendung ableiten.
                continue
            kandidaten[klasse] = objekte

        def belegtext(objekte):
            belege = ", ".join(sorted(objekte)[:5])
            if len(objekte) > 5:
                belege += f", ... (+{len(objekte) - 5})"
            return (f"{len(objekte)} Items dieser Klasse nennen den Werkstoff "
                    f"per P186: {belege}")

        for klasse in sorted(kandidaten, key=lambda k: -len(kandidaten[k])):
            objekte = kandidaten[klasse]
            wurzeln = rollen.get(klasse, set()) & set(VERBUND_WURZELN)
            if klasse in TEILWERKSTOFF_KLASSEN:
                grund = TEILWERKSTOFF_KLASSEN[klasse]
            elif klasse in VERBUND_EXAKT:
                grund = (f"{VERBUND_EXAKT[klasse]} - der Werkstoff ist dort "
                         f"ein Bauteil, nicht der Gegenstand")
            elif wurzeln:
                art = ", ".join(sorted(VERBUND_WURZELN[w] for w in wurzeln))
                grund = (f"die Klasse haengt unter '{art}': dort ist der "
                         f"Werkstoff ein Bauteil, nicht der Gegenstand")
            else:
                grund = ""
            if grund:
                verbund.append(befund(
                    "p366-verbund", werkstoff, klasse, len(objekte),
                    f"{werkstoff}\tP366\t{klasse}",
                    f"{belegtext(objekte)} - {grund}",
                    "manuell: nur setzen, wenn der Werkstoff das Bauwerk "
                    "bzw. Fahrzeug wirklich praegt (Stahlbruecke ja, "
                    "Messing am Fahrzeug nein)"))
                del kandidaten[klasse]
                continue
            sprachen = sitelinks.get(klasse, 0)
            if sprachen < min_sprachen:
                speziell.append(befund(
                    "p366-zu-speziell", werkstoff, klasse, len(objekte),
                    f"{werkstoff}\tP366\t{klasse}",
                    f"{belegtext(objekte)} - aber die Klasse gibt es in nur "
                    f"{sprachen} Wikipedia-Sprachversionen "
                    f"(Schwelle {min_sprachen})",
                    "manuell: als Verwendung vermutlich zu eng gefasst - "
                    "sonst die Oberklasse setzen"))
                del kandidaten[klasse]
                continue

        for klasse, objekte in kandidaten.items():
            begruendung = belegtext(objekte)
            # Allgemeinere Kandidatenklasse mit mindestens so vielen Belegen?
            decker = [o for o in oberklassen.get(klasse, ())
                      if o in kandidaten and len(kandidaten[o]) >= len(objekte)]
            if decker:
                bester = max(decker, key=lambda o: len(kandidaten[o]))
                ueberdeckt.append(befund(
                    "p366-ueberdeckt", werkstoff, klasse, len(objekte),
                    f"{werkstoff}\tP366\t{klasse}",
                    f"{begruendung} - aber die Oberklasse {bester} steht mit "
                    f"{len(kandidaten[bester])} Belegen in Abschnitt 1",
                    "manuell: nur zusätzlich setzen, wenn gerade diese engere "
                    "Klasse die Verwendung ist"))
                continue
            treffer.append(befund(
                "p366-aus-p186", werkstoff, klasse, len(objekte),
                f"{werkstoff}\tP366\t{klasse}", begruendung, "einspielbar"))

    schluessel = (lambda b: (-b["kennzahl"], b["qid"], b["ziel_qid"]))
    for teil in (treffer, ueberdeckt, verbund, speziell):
        teil.sort(key=schluessel)
    return treffer + ueberdeckt + verbund + speziell


def pruefe_p186_rueckkante(p366: dict, rollen: dict, klassen: set,
                           vorhanden: set) -> tuple:
    """P366 am Werkstoff da, P186 am Anwendungsitem fehlt.

    Liefert (einzeldinge, klassenfaelle, ohne_rueckkante_moeglich). Der
    dritte Teil sind die Taetigkeiten - kein Befund, nur eine Zahl fuer den
    Bericht.
    """
    einzeln, klassenfall, taetigkeiten = [], [], 0
    for werkstoff, anwendungen in sorted(p366.items()):
        for anwendung in sorted(anwendungen):
            if (anwendung, werkstoff) in vorhanden:
                continue
            rolle = rollen.get(anwendung, set())
            ist_aktivitaet = bool(rolle & set(AKTIVITAET_WURZELN))
            ist_objekt = bool(rolle & set(OBJEKT_WURZELN))
            if ist_aktivitaet and not ist_objekt:
                taetigkeiten += 1
                continue
            qs = f"{anwendung}\tP186\t{werkstoff}"
            if anwendung in klassen:
                klassenfall.append(befund(
                    "p186-klasse", anwendung, werkstoff, "",
                    qs,
                    "das Anwendungsitem ist eine Klasse - P186 hier hiesse, "
                    "ALLE ihre Instanzen bestehen aus diesem Werkstoff",
                    "manuell: nur setzen, wenn die Klasse den Werkstoff "
                    "definiert (z. B. Bronzeskulptur)"))
            else:
                einzeln.append(befund(
                    "p186-einzelding", anwendung, werkstoff, "",
                    qs,
                    "Einzelding (keine Instanzen, keine Unterklassen) - die "
                    "Rueckkante zur vorhandenen P366-Aussage fehlt",
                    "einspielbar"))
    return einzeln, klassenfall, taetigkeiten


def pruefe_p2079_vererbt(qids: list, p2079: dict, eltern: dict) -> list:
    """Werkstoff ohne P2079, aber eine direkte P279-Oberklasse hat eines."""
    treffer = []
    for qid in sorted(qids):
        if p2079.get(qid):
            continue
        for elter in sorted(eltern.get(qid, ())):
            for verfahren in sorted(p2079.get(elter, ())):
                treffer.append(befund(
                    "p2079-vererbt", qid, verfahren, "",
                    f"{qid}\tP2079\t{verfahren}",
                    f"die Oberklasse {elter} wird so hergestellt; ob die "
                    f"Unterklasse dasselbe Verfahren teilt, sagt P279 nicht",
                    "manuell: Verfahren gegen die Fachliteratur pruefen"))
    return treffer


def pruefe_p366_verfahren(p366: dict, rollen: dict) -> list:
    """P366 zeigt auf ein Fertigungsverfahren - vielleicht war P2079 gemeint."""
    treffer = []
    for werkstoff, anwendungen in sorted(p366.items()):
        for anwendung in sorted(anwendungen):
            rolle = rollen.get(anwendung, set())
            if not rolle & set(VERFAHREN_WURZELN):
                continue
            if rolle & set(OBJEKT_WURZELN):
                continue   # Mokume-Gane u. ae.: auch ein Ding, nicht nur ein Weg
            treffer.append(befund(
                "p366-verfahren", werkstoff, anwendung, "",
                f"{werkstoff}\tP2079\t{anwendung}\n"
                f"-{werkstoff}\tP366\t{anwendung}",
                "der P366-Wert ist ein Fertigungsverfahren",
                "manuell: 'wird SO hergestellt' -> P2079; 'wird DAFUER "
                "gebraucht' -> P366 bleibt"))
    return treffer


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

_TRENNER = "# " + "=" * 70

MELDE_ABSCHNITTE = [
    ("p366-ueberdeckt", "SCHON DURCH EINE OBERKLASSE ABGEDECKT",
     ["Diese Zeilen sind nicht falsch, nur ueberfluessig: eine allgemeinere",
      "Klasse desselben Werkstoffs steht in Abschnitt 1 und ist mindestens",
      "so gut belegt. Wer die engere Aussage trotzdem will - 'Bronze fuer",
      "Statuetten', nicht nur 'fuer Skulpturen' -, holt sich die Zeile hier."]),
    ("p366-verbund", "VERBUNDGEGENSTAND - ANTEIL UNBEKANNT",
     ["Der Gegenstand besteht nur zum Teil aus dem Werkstoff: Gebaeude,",
      "Bruecke, Turm, Fahrzeug, Maschine. Wie gross der Teil ist, sagt",
      "Wikidata nicht - der Qualifikator P518 'bezogen auf' ist an diesen",
      "127.000 P186-Aussagen kein einziges Mal gesetzt. Deshalb steht die",
      "Zeile hier und nicht oben: 'Stahl fuer Bruecken' stimmt, 'Magnesium-",
      "legierung fuer Digitalkameras' meint nur das Gehaeuse."]),
    ("p366-zu-speziell", "ZU SPEZIELLE KLASSE",
     ["Die Klasse existiert in weniger als --min-sprachen Wikipedias. Als",
      "Verwendung eines Werkstoffs ist das zu eng gefasst - 'Bronze fuer",
      "Carteluhren' beschreibt einen Einzelfall, nicht einen Gebrauch.",
      "Oft waere die Oberklasse richtig; die steht hier aber nur, wenn sie",
      "selbst genug Belege hat."]),
    ("p186-klasse", "P186 AN EINER KLASSE",
     ["Aus 'mancher X ist aus M' folgt nicht 'jedes X ist aus M'. P186 an",
      "der Klasse behauptet das Zweite. Richtig ist die Zeile nur, wenn der",
      "Werkstoff zur Definition der Klasse gehoert - Bronzeskulptur ja,",
      "Muenze nein."]),
    ("p2079-vererbt", "P2079 AUS DER OBERKLASSE",
     ["P279 sagt, dass die Unterklasse dieselbe ART Ding ist, nicht dass sie",
      "denselben WEG nimmt. Legierter Stahl entsteht anders als Roheisen.",
      "Diese Zeilen sind Vorschlaege zum Nachschlagen, keine Ableitung."]),
    ("p366-verfahren", "P366 ODER P2079?",
     ["Der Wert ist ein Fertigungsverfahren. Beides ist moeglich: eine",
      "Giesslegierung wird FUER das Giessen gebraucht (P366), Osemund wird",
      "DURCH sein Verfahren hergestellt (P2079). Der Entwurf zeigt beide",
      "Zeilen - die Umbuchung und die Loeschung der alten Aussage."]),
]


def abschnitt_kopf(titel: str, anzahl: int, erklaerung: list) -> list:
    zeilen = ["", _TRENNER,
              f"# {titel} ({anzahl} {'Befund' if anzahl == 1 else 'Befunde'})"]
    zeilen += [f"# {z}" for z in erklaerung]
    zeilen.append(_TRENNER)
    return zeilen


def schreibe_quickstatements(befunde: list, pfad: str, population: str,
                             min_belege: int, labels: dict,
                             vorsichtig: bool) -> None:
    """QuickStatements-V1-Entwurf. Abschnitt 1 ist einspielbar, alles danach
    ist durchgehend auskommentiert - dieselbe Bauart wie in materialswiki
    und P279-structure, damit sich die Datei komplett kopieren laesst, ohne
    dass aus einer Meldezeile versehentlich eine Aussage wird."""
    einspielbar = [] if vorsichtig else [
        b for b in befunde
        if b["befund"] in ("p366-aus-p186", "p186-einzelding")]
    ids = {id(b) for b in einspielbar}

    def name(qid: str) -> str:
        return f"{qid} {labels.get(qid, '')}".strip()

    zeilen = [
        _TRENNER,
        "# ENTWURF - vor Verwendung jede Zeile manuell pruefen!",
        f"# Anwendungen, Grundgesamtheit '{population}', "
        f"erzeugt {dt.datetime.now():%Y-%m-%d %H:%M}",
        "#",
        "# Aufbau dieser Datei:",
        f"#   ABSCHNITT 1  {'EINSPIELBAR':<38} {len(einspielbar):4d}  "
        "(die einzigen ausfuehrbaren Zeilen)",
    ]
    for i, (art, titel, _) in enumerate(MELDE_ABSCHNITTE, 2):
        anzahl = sum(1 for b in befunde if b["befund"] == art)
        zeilen.append(f"#   ABSCHNITT {i}  {titel:<38} {anzahl:4d}  "
                      "(auskommentiert)")
    zeilen += [
        "#",
        "# Ausserhalb von Abschnitt 1 beginnt jede Zeile mit '#'.",
        "#",
        "# Keine Zeile traegt einen Beleg (S...). Alle Aussagen sind aus",
        "# Wikidata selbst abgeleitet - aus P186 an den Objekten - und ein",
        "# Import kann sich nicht auf sich selbst berufen. Der Kommentar",
        "# unter jeder Zeile nennt stattdessen die Items, die sie tragen.",
        "#",
        f"# P366 wird ab {min_belege} belegenden Objekten vorgeschlagen",
        "# (--min-belege). Darunter ist eine Klasse nicht die Verwendung",
        "# eines Werkstoffs, sondern ein Zufallstreffer.",
        "#",
        "# '-QID<TAB>P<TAB>QID' entfernt eine Aussage, ohne Minus setzt sie.",
        _TRENNER,
    ]

    zeilen += abschnitt_kopf(
        "ABSCHNITT 1: EINSPIELBAR", len(einspielbar),
        ["Nur diese Zeilen sind QuickStatements-Syntax. Trotzdem gilt:",
         "erst nach zeilenweiser Pruefung einspielen. P366 kommt aus der",
         "Aggregation, P186 nur bei Einzeldingen - beides ohne",
         "Quantorensprung."]
        + (["(--vorsichtig gesetzt: Abschnitt bleibt bewusst leer)"]
           if vorsichtig else []))
    for b in einspielbar:
        zeilen.append(b["quickstatements"])
        zeilen.append(f"# {name(b['qid'])} -> {name(b['ziel_qid'])}: "
                      f"{b['begruendung']}")
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
            ziel = (f" -> {name(b['ziel_qid'])}"
                    if str(b["ziel_qid"]).startswith("Q") else "")
            zeilen.append(f"# {name(b['qid'])}{ziel}: {b['begruendung']}")
            zeilen.append(f"#     -> {b['entscheidung']}")

    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"QuickStatements-Entwurf geschrieben nach: {pfad}", file=sys.stderr)


def schreibe_csv(befunde: list, pfad: str, labels: dict) -> None:
    felder = ["befund", "qid", "label", "ziel_qid", "ziel_label", "kennzahl",
              "quickstatements", "begruendung", "entscheidung"]
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        schreiber = csv.DictWriter(f, fieldnames=felder)
        schreiber.writeheader()
        for b in befunde:
            schreiber.writerow({
                **{k: b.get(k, "") for k in felder},
                "label": labels.get(b["qid"], ""),
                "ziel_label": labels.get(b["ziel_qid"], ""),
                # Der Zeilenumbruch im zweizeiligen Umbuchungsentwurf wuerde
                # die CSV-Zeile sprengen; im Tabellenblatt ist ' | ' lesbarer.
                "quickstatements": (b["quickstatements"] or "").replace(
                    "\n", " | ").replace("\t", " "),
            })
    print(f"Befunde geschrieben nach: {pfad}", file=sys.stderr)


def bericht(items: dict, befunde: list, p366: dict, objekte: dict,
            p2079: dict, taetigkeiten: int, min_belege: int) -> None:
    gesamt = len(items)
    mit_p366 = sum(1 for q in items if p366.get(q))
    mit_rueck = sum(1 for q in items if objekte.get(q))
    mit_p2079 = sum(1 for q in items if p2079.get(q))
    stumm = sum(1 for q in items if not p366.get(q) and not objekte.get(q))

    def anteil(n):
        return f"{n:5d}  ({100 * n / gesamt:4.1f} %)" if gesamt else f"{n:5d}"

    print()
    print("Abdeckung in der Grundgesamtheit")
    print(f"  Werkstoffe insgesamt .................. {gesamt:5d}")
    print(f"  mit P366 (Verwendung) ................. {anteil(mit_p366)}")
    print(f"  mit P186-Rueckverweis von Objekten .... {anteil(mit_rueck)}")
    print(f"  mit P2079 (Herstellungsverfahren) ..... {anteil(mit_p2079)}")
    print(f"  ohne jede Anwendungsangabe ............ {anteil(stumm)}")
    print()
    print("Befunde")
    zaehler = collections.Counter(b["befund"] for b in befunde)
    for art in PRUEFUNGEN + ["p366-ueberdeckt", "p366-verbund",
                             "p366-zu-speziell"]:
        print(f"  {art:<18} {zaehler.get(art, 0):5d}")
    print()
    print(f"  {taetigkeiten} P366-Werte sind Taetigkeiten - fuer die gibt es "
          f"keine Rueckkante,")
    print("  ein Vorgang besteht aus keinem Material. Kein Mangel.")
    if not zaehler.get("p366-aus-p186"):
        print()
        print(f"  Kein P366-Vorschlag bei --min-belege {min_belege}. "
              f"Mit einem kleineren Wert")
        print("  werden es mehr - und schwaecher belegt.")
    print()


# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Entwirft Anwendungsaussagen (P366, P186, P2079) fuer "
                    "Werkstoffe in Wikidata als QuickStatements.")
    parser.add_argument("--population", choices=sorted(POPULATIONEN),
                        default="legierungen",
                        help="Grundgesamtheit (Default: legierungen)")
    parser.add_argument("--pruefungen", nargs="+", choices=PRUEFUNGEN,
                        default=PRUEFUNGEN,
                        help=f"Auswahl der Pruefungen (Default: alle: "
                             f"{', '.join(PRUEFUNGEN)})")
    parser.add_argument("--min-belege", type=int, default=3,
                        help="Pruefung 'p366-aus-p186': ab wie vielen Objekten "
                             "einer Klasse die Verwendung vorgeschlagen wird "
                             "(Default 3). Kleiner heisst mehr Vorschlaege "
                             "und mehr Zufallstreffer.")
    parser.add_argument("--min-sprachen", type=int, default=10,
                        help="Pruefung 'p366-aus-p186': wie viele "
                             "Wikipedia-Sprachversionen die Klasse haben "
                             "muss, um als Verwendung durchzugehen "
                             "(Default 10). 0 schaltet den Filter ab. Ueber "
                             "10 faengt er an, gute Verwendungen zu treffen "
                             "- 'Skulptur' hat nur 26.")
    parser.add_argument("--limit", type=int, default=None,
                        help="nur die ersten N Werkstoffe (fuer Probelaeufe)")
    parser.add_argument("--vorsichtig", action="store_true",
                        help="auch die abgeleiteten Zeilen auskommentieren - "
                             "dann enthaelt die Datei keine ausfuehrbare Zeile")
    parser.add_argument("--csv", default=None,
                        help="Ziel der Befund-CSV (Default: "
                             "anwendungen_befunde_<Zeitstempel>.csv)")
    parser.add_argument("--qs-out", default=None,
                        help="Ziel des Entwurfs (Default: "
                             "quickstatements_anwendungen_<Zeitstempel>.txt)")
    args = parser.parse_args(argv)

    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_pfad = args.csv or f"anwendungen_befunde_{stempel}.csv"
    qs_pfad = args.qs_out or f"quickstatements_anwendungen_{stempel}.txt"

    print(f"Hole Grundgesamtheit '{args.population}' ...", file=sys.stderr)
    items = hole_population(args.population, args.limit)
    if not items:
        raise SystemExit("Grundgesamtheit ist leer - nichts zu pruefen.")
    qids = sorted(items)
    print(f"  {len(qids)} Werkstoffe", file=sys.stderr)

    print("Hole vorhandene P366-Aussagen ...", file=sys.stderr)
    p366 = hole_p366(qids)
    print(f"  {sum(len(v) for v in p366.values())} Aussagen an "
          f"{len(p366)} Werkstoffen", file=sys.stderr)

    print("Hole P186-Rueckverweise der Objekte ...", file=sys.stderr)
    nach_klasse, objekte = hole_p186_rueck(qids)
    print(f"  {sum(len(v) for v in objekte.values())} Objekte nennen einen "
          f"dieser Werkstoffe", file=sys.stderr)

    braucht_p2079 = {"p2079-vererbt"} & set(args.pruefungen)
    p2079, eltern = {}, {}
    if braucht_p2079:
        print("Hole P2079 und P279-Eltern ...", file=sys.stderr)
        eltern = hole_p279_eltern(qids)
        # Auch die Eltern ausserhalb der Grundgesamtheit brauchen ihr P2079 -
        # sonst faellt genau die Vererbung aus, die geprueft werden soll.
        alle_eltern = sorted({p for v in eltern.values() for p in v})
        p2079 = hole_p2079(sorted(set(qids) | set(alle_eltern)))
        print(f"  {sum(len(v) for v in p2079.values())} P2079-Aussagen",
              file=sys.stderr)

    # Zu klassifizieren ist alles, was als Anwendung in Frage kommt: die
    # vorhandenen P366-Werte und die Kandidatenklassen aus der Aggregation.
    # Nur die Kandidaten, die die Belegschwelle reissen - der Rest waere
    # eine Klassifikation fuer Zeilen, die ohnehin nicht gemeldet werden.
    kandidaten = {k for klassen in nach_klasse.values()
                  for k, obj in klassen.items() if len(obj) >= args.min_belege}
    anwendungen = sorted(kandidaten | {a for v in p366.values() for a in v})
    print(f"Klassifiziere {len(anwendungen)} Anwendungsitems ...",
          file=sys.stderr)
    rollen = klassifiziere(anwendungen) if anwendungen else {}

    oberklassen, sitelinks = {}, {}
    if "p366-aus-p186" in args.pruefungen and kandidaten:
        print(f"Hole die P279-Oberklassen von {len(kandidaten)} "
              f"Kandidatenklassen ...", file=sys.stderr)
        oberklassen = hole_oberklassen(sorted(kandidaten))
        if args.min_sprachen > 0:
            print("Hole die Zahl der Sprachversionen ...", file=sys.stderr)
            sitelinks = hole_sitelinks(sorted(kandidaten))

    braucht_klassen = {"p186-einzelding", "p186-klasse"} & set(args.pruefungen)
    p366_werte = sorted({a for v in p366.values() for a in v})
    klassen, vorhanden = set(), set()
    if braucht_klassen and p366_werte:
        print(f"Pruefe {len(p366_werte)} P366-Werte auf Einzelding oder "
              f"Klasse ...", file=sys.stderr)
        klassen = hole_hat_nachfolger(p366_werte)
        vorhanden = hole_p186_vorhanden(
            [(a, m) for m, v in p366.items() for a in v])

    befunde = []
    taetigkeiten = 0
    if "p366-aus-p186" in args.pruefungen:
        befunde += pruefe_p366_aus_p186(nach_klasse, p366, rollen,
                                        oberklassen, sitelinks,
                                        args.min_belege, args.min_sprachen)
    if braucht_klassen:
        einzeln, klassenfall, taetigkeiten = pruefe_p186_rueckkante(
            p366, rollen, klassen, vorhanden)
        if "p186-einzelding" in args.pruefungen:
            befunde += einzeln
        if "p186-klasse" in args.pruefungen:
            befunde += klassenfall
    if braucht_p2079:
        befunde += pruefe_p2079_vererbt(qids, p2079, eltern)
    if "p366-verfahren" in args.pruefungen:
        befunde += pruefe_p366_verfahren(p366, rollen)

    zu_beschriften = sorted(set(items) | {b["qid"] for b in befunde}
                            | {b["ziel_qid"] for b in befunde
                               if str(b["ziel_qid"]).startswith("Q")})
    print(f"Hole {len(zu_beschriften)} Bezeichnungen ...", file=sys.stderr)
    labels = {**items, **hole_labels(zu_beschriften)}

    bericht(items, befunde, p366, objekte, p2079, taetigkeiten,
            args.min_belege)
    schreibe_csv(befunde, csv_pfad, labels)
    schreibe_quickstatements(befunde, qs_pfad, args.population,
                             args.min_belege, labels, args.vorsichtig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
