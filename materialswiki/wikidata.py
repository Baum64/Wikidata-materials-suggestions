"""Was Wikidata selbst schon weiss.

Zwei Sorten Wissen:

  VOKABULAR   Elementtabelle, die 230 Raumgruppen samt Punktgruppe - Tabellen,
              die Wikidata pflegt und die dieses Werkzeug nur nachschlaegt,
              statt sie selbst zu fuehren.
  ITEMZUSTAND welche Aussagen ein Item schon traegt, sein Siedepunkt, seine
              CAS-Nummer, seine Raumgruppe.

Der Itemzustand wird CHARGENWEISE geholt (claims_vorladen und die uebrigen
*_vorladen): eine Anfrage je 50 bis 200 Items statt je Item. Warum das der
groesste Hebel der Laufzeit war: README, "Laufzeit".
"""

import collections
import re
import sys
from typing import Optional

import requests

from .formeln import formula_candidates, parse_formula
from .konfiguration import WIKIDATA_API, WIKIDATA_SPARQL
from . import netz
from .properties import (
    PROPERTY_MAP, RAUMTEMPERATUR_K, STUFEN_PIDS, TEMPERATUR_NACH_KELVIN,
)

# Zuordnung Raumgruppennummer -> Kristallsystem, normativ aus den
# International Tables for Crystallography (Bd. A). KEINE Heuristik: die
# Bereiche sind so definiert. Dient nur als Rueckfall - primaer wird das
# Kristallsystem am Raumgruppen-Item selbst abgelesen (P556), und das deckt
# 229 der 230 Raumgruppen ab.
KRISTALLSYSTEM_BEREICHE = [
    (1, 2, "triclinic"), (3, 15, "monoclinic"), (16, 74, "orthorhombic"),
    (75, 142, "tetragonal"), (143, 167, "trigonal"), (168, 194, "hexagonal"),
    (195, 230, "cubic"),
]


def kristallsystem_aus_nummer(nummer: int) -> Optional[str]:
    for von, bis, name in KRISTALLSYSTEM_BEREICHE:
        if von <= nummer <= bis:
            return name
    return None


_SPACE_GROUP_CACHE = None


def fetch_space_group_qids() -> dict:
    """{Raumgruppennummer: {qid, label, cs_qid, cs_label, pg_qid, pg_label}}.

    Aufgeloest ueber P9733 (Raumgruppennummer) statt ueber Labels - die
    Raumgruppen-Items sind uneinheitlich benannt ("Raumgruppe 227" neben
    "space group C2/m"), die Nummer ist der einzige verlaessliche Schluessel.

    Kristallsystem (P556) und Punktgruppe (P589) kommen vom Raumgruppen-Item
    selbst: Wikidata weiss dort bereits, dass Raumgruppe 227 kubisch ist und
    zur Punktgruppe m-3m gehoert. Das erspart zwei gepflegte Tabellen - und
    die Punktgruppe kostet nicht einmal eine eigene Abfrage, sie faellt in
    derselben ab. 230 der 236 Raumgruppen-Items fuehren sie (2026-08-19).

    Sechs Nummern haben mehr als ein Item (Dubletten in Wikidata, am
    2026-08-16: 40, 122, 146, 147, 148, 160). Gewaehlt wird deterministisch
    das Item MIT Kristallsystem, bei Gleichstand die kleinere Q-Nummer.
    """
    global _SPACE_GROUP_CACHE
    if _SPACE_GROUP_CACHE is not None:
        return _SPACE_GROUP_CACHE

    query = """
    SELECT ?nummer ?sg ?sgLabel ?cs ?csLabel ?pg ?pgLabel WHERE {
      ?sg wdt:P9733 ?nummer .
      OPTIONAL { ?sg wdt:P556 ?cs . }
      OPTIONAL { ?sg wdt:P589 ?pg . }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
    }
    """
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"query": query, "format": "json"})
    gefunden = {}
    for b in resp.json()["results"]["bindings"]:
        nummer = int(float(b["nummer"]["value"]))
        qid = b["sg"]["value"].rsplit("/", 1)[-1]
        eintrag = {
            "qid": qid,
            "label": b.get("sgLabel", {}).get("value", qid),
            "cs_qid": (b["cs"]["value"].rsplit("/", 1)[-1] if "cs" in b else ""),
            "cs_label": b.get("csLabel", {}).get("value", ""),
            "pg_qid": (b["pg"]["value"].rsplit("/", 1)[-1] if "pg" in b else ""),
            "pg_label": b.get("pgLabel", {}).get("value", ""),
        }
        bisher = gefunden.get(nummer)
        if bisher is None or _sg_besser(eintrag, bisher):
            gefunden[nummer] = eintrag
    _SPACE_GROUP_CACHE = gefunden
    return gefunden


def raumgruppen_nach_qid() -> dict:
    """Dieselbe Tabelle, aber nach der QID des Raumgruppen-Items geschluesselt.

    Gebraucht fuer den umgekehrten Weg: am Item steht eine Raumgruppe, und
    gesucht ist ihre Punktgruppe - da ist die Nummer gar nicht bekannt.
    """
    return {e["qid"]: e for e in fetch_space_group_qids().values()}


def _sg_besser(neu: dict, alt: dict) -> bool:
    """Dubletten aufloesen: Kristallsystem schlaegt kein Kristallsystem,
    danach die kleinere Q-Nummer."""
    if bool(neu["cs_qid"]) != bool(alt["cs_qid"]):
        return bool(neu["cs_qid"])
    return int(neu["qid"][1:]) < int(alt["qid"][1:])



# Echte Elementsymbole haben ein oder zwei Zeichen; die systematischen
# IUPAC-Platzhalter fuer unentdeckte Elemente immer drei (siehe unten).
_ECHTES_ELEMENTSYMBOL = re.compile(r"[A-Z][a-z]?")


def fetch_element_qids() -> dict:
    """{Elementsymbol: {qid, label, name_en}} fuer alle chemischen Elemente.

    name_en adressiert die englische Vorlage "Template:Infobox <name>",
    title_de den deutschen Artikel (per Sitelink, nicht geraten).

    Ueber das Symbol (P246) statt ueber die Summenformel - fuer Reinstoffe
    ist das eindeutig und umgeht die Formel-Normalisierung (Datenbanken
    schreiben "O2Ti", Wikidata P274 "TiO₂") vollstaendig.

    Geprueft am 2026-08-14: 174 Items mit P31=Q11344 und P246, KEIN Symbol
    doppelt vergeben - die Abbildung ist damit kollisionsfrei.

    ABER: 56 dieser 174 sind gar keine Elemente, sondern systematische
    IUPAC-Platzhalter fuer UNENTDECKTE Elemente - "Ubb" (Unbibium, Z=122),
    "Uue" (Ununennium, Z=119) und so fort. Wikidata fuehrt sie voellig
    korrekt als P31=Q11344, es gibt sie nur nicht. Materials Project
    beantwortet eine Abfrage danach mit HTTP 400 ("Please provide a
    comma-seperated list of elements") und riss so einen Periodensystem-Lauf
    bei Element 112 von 174 ab.

    Aussortiert werden sie an der Symbollaenge: echte Elementsymbole haben
    ein oder zwei Zeichen, die systematischen Platzhalter immer drei. Am
    Bestand geprueft (2026-08-15) trennt das exakt - 118 echte Elemente,
    genau die Zahl der bekannten, und 56 Platzhalter.
    """
    query = """
    SELECT ?e ?sym ?eLabel ?enLabel ?deTitle WHERE {
      ?e wdt:P31 wd:Q11344 ; wdt:P246 ?sym ; rdfs:label ?enLabel .
      FILTER(LANG(?enLabel) = "en")
      OPTIONAL {
        ?art schema:about ?e ;
             schema:isPartOf <https://de.wikipedia.org/> ;
             schema:name ?deTitle .
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
    }
    """
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"query": query, "format": "json"})
    out = {}
    platzhalter = []
    for b in resp.json()["results"]["bindings"]:
        qid = b["e"]["value"].rsplit("/", 1)[-1]
        symbol = b["sym"]["value"]
        if not _ECHTES_ELEMENTSYMBOL.fullmatch(symbol):
            platzhalter.append(symbol)
            continue
        out[symbol] = {
            "qid": qid,
            "label": b.get("eLabel", {}).get("value", qid),
            "name_en": b["enLabel"]["value"],
            # Sitelink statt geratenem Titel: Titan liegt unter
            # "Titan (Element)".
            "title_de": b.get("deTitle", {}).get("value", ""),
        }
    if platzhalter:
        print(
            f"  {len(platzhalter)} systematische Platzhalter fuer unentdeckte "
            f"Elemente uebersprungen ({', '.join(sorted(platzhalter)[:3])} ...)",
            file=sys.stderr,
        )
    return out


# ---------------------------------------------------------------------------
# "enthaelt Elemente von" (P2670) aus der Summenformel ableiten
# ---------------------------------------------------------------------------
#
# Welche Elemente ein Stoff enthaelt, steht schon in seiner Summenformel - es
# braucht dafuer keine externe Quelle. Erzeugt wird Element + Anzahl (P1114),
# nach dem Vorbild von Kohlenstoffdioxid (Q1997).
#
# Warum dafuer ein ZWEITER Parser neben parse_formula noetig ist, wie
# Mischreihen behandelt werden und wie weit das traegt (gemessen an 5700
# Formeln): README, "enthaelt Elemente von (P2670) aus der Summenformel".
#

_ELEMENT_QID_CACHE = None


def element_qids() -> dict:
    """fetch_element_qids mit Zwischenspeicher.

    Die Ableitung laeuft ueber Tausende Items; ohne Cache ginge je Item eine
    SPARQL-Abfrage fuer dieselbe unveraenderliche Elementtabelle raus.
    """
    global _ELEMENT_QID_CACHE
    if _ELEMENT_QID_CACHE is None:
        _ELEMENT_QID_CACHE = fetch_element_qids()
    return _ELEMENT_QID_CACHE


_CAS_CACHE = {}
CAS_CHARGE = 200


def fetch_cas_nummern(qids: list) -> dict:
    """{QID: CAS-Nummer oder ""} - der Suchschluessel des WebBook.

    Traegt ein Item mehrere CAS-Nummern (verschiedene Hydrate, Modifikationen),
    wird KEINE genommen: welche den Stoff des Items meint, entscheidet das
    Werkzeug nicht.
    """
    if not qids:
        return {}
    werte = " ".join(f"wd:{q}" for q in qids)
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT ?i ?cas WHERE {{
      VALUES ?i {{ {werte} }}
      ?i wdt:P231 ?cas .
    }}
    """})
    gefunden = collections.defaultdict(set)
    for b in resp.json()["results"]["bindings"]:
        gefunden[b["i"]["value"].rsplit("/", 1)[-1]].add(b["cas"]["value"])
    return {q: (list(gefunden[q])[0] if len(gefunden.get(q, ())) == 1 else "")
            for q in qids}


def cas_vorladen(qids: list) -> None:
    offen = [q for q in qids if q not in _CAS_CACHE]
    for start in range(0, len(offen), CAS_CHARGE):
        _CAS_CACHE.update(fetch_cas_nummern(offen[start:start + CAS_CHARGE]))


def cas_nummer(qid: str) -> str:
    if qid not in _CAS_CACHE:
        _CAS_CACHE.update(fetch_cas_nummern([qid]))
    return _CAS_CACHE.get(qid, "")


_ITEM_RAUMGRUPPE_CACHE = {}
# Wie bei den Bestandteilen: eine Abfrage je 200 Items statt je Item.
RAUMGRUPPE_CHARGE = 200


def fetch_item_raumgruppen(qids: list) -> dict:
    """{QID: [Raumgruppen-QID, ...]} - die P690-Werte der Items."""
    if not qids:
        return {}
    werte = " ".join(f"wd:{q}" for q in qids)
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT ?i ?sg WHERE {{
      VALUES ?i {{ {werte} }}
      ?i wdt:P690 ?sg .
    }}
    """})
    out = {q: [] for q in qids}
    for b in resp.json()["results"]["bindings"]:
        qid = b["i"]["value"].rsplit("/", 1)[-1]
        sg = b["sg"]["value"].rsplit("/", 1)[-1]
        if sg not in out[qid]:
            out[qid].append(sg)
    return out


def item_raumgruppen_vorladen(qids: list) -> None:
    """Raumgruppen vieler Items auf einmal holen und merken."""
    offen = [q for q in qids if q not in _ITEM_RAUMGRUPPE_CACHE]
    for start in range(0, len(offen), RAUMGRUPPE_CHARGE):
        _ITEM_RAUMGRUPPE_CACHE.update(
            fetch_item_raumgruppen(offen[start:start + RAUMGRUPPE_CHARGE]))


def item_raumgruppen(qid: str) -> list:
    """Raumgruppen EINES Items, aus dem Zwischenspeicher oder frisch."""
    if qid not in _ITEM_RAUMGRUPPE_CACHE:
        _ITEM_RAUMGRUPPE_CACHE.update(fetch_item_raumgruppen([qid]))
    return _ITEM_RAUMGRUPPE_CACHE.get(qid, [])


# ---------------------------------------------------------------------------
# Schritt 2b: Bestehendes Wikidata-Item ueber Formel finden
# ---------------------------------------------------------------------------

def find_wikidata_item_by_formula(formula: str) -> Optional[dict]:
    """Sucht ein BESTEHENDES Wikidata-Item mit passender chemischer Formel
    (P274). Legt NIEMALS ein neues Item an.
    """
    if not formula:
        return None

    # Ueber die Zusammensetzung statt ueber den rohen String suchen - sonst
    # scheitert der Vergleich an Ziffernart und Elementreihenfolge (siehe
    # Abschnitt "Formel-Normalisierung"). Laesst sich die Formel nicht
    # deuten, bleibt der urspruengliche Wortlaut als einziger Kandidat.
    zusammensetzung = parse_formula(formula)
    kandidaten = (formula_candidates(zusammensetzung) if zusammensetzung
                  else [formula])
    values = " ".join(f'"{k}"' for k in kandidaten)

    # Die Sitelinks werden gleich mitgeholt: die Wikipedia-Fallbackstufen
    # brauchen den echten Artikeltitel, und geraten werden darf er nicht
    # (Titan liegt unter "Titan (Element)"). Ein zweiter Abruf je Item
    # waere reine Verschwendung.
    sparql = f"""
    SELECT ?item ?itemLabel ?formel ?deTitle ?enTitle WHERE {{
      VALUES ?formel {{ {values} }}
      ?item wdt:P274 ?formel .
      OPTIONAL {{
        ?deArt schema:about ?item ;
               schema:isPartOf <https://de.wikipedia.org/> ;
               schema:name ?deTitle .
      }}
      OPTIONAL {{
        ?enArt schema:about ?item ;
               schema:isPartOf <https://en.wikipedia.org/> ;
               schema:name ?enTitle .
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    LIMIT 50
    """
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"query": sparql, "format": "json"})
    bindings = resp.json().get("results", {}).get("bindings", [])

    # Gegenprobe: die gefundene Formel zurueckparsen und die Zusammensetzung
    # vergleichen. Ein Kandidat kann durch eine Nachlaessigkeit auf beiden
    # Seiten danebenliegen; die Zusammensetzung luegt nicht.
    if zusammensetzung:
        bindings = [
            b for b in bindings
            if parse_formula(b.get("formel", {}).get("value", ""))
            == zusammensetzung
        ]
    if not bindings:
        return None

    # Nach ITEMS unterscheiden, nicht nach Zeilen: mehrere Schreibweisen
    # desselben Items und die OPTIONAL-Bloecke wuerden es sonst faelschlich
    # als mehrdeutig erscheinen lassen.
    treffer = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        treffer.setdefault(qid, b)

    # Stichentscheid bei Mehrdeutigkeit: Isotopologe tragen dieselbe Formel
    # UND dieselbe P31 wie der echte Stoff ("Carbon-13C dioxide",
    # "sodium chloride na-24", "Sodium (³⁵Cl)chloride" - alle P31
    # Q113145171 "definierte chemische Substanz"). Ueber die Klasse sind sie
    # also nicht auszusortieren, wohl aber ueber den Artikel: diese
    # Bot-Anlagen haben keinen.
    #
    # Greift nur, WENN es mehrdeutig ist und mindestens ein Item mit Artikel
    # dabei ist. Ein einzelner artikelloser Treffer bleibt damit gueltig -
    # gefiltert wird nur, wo ohnehin eine Auswahl noetig waere. Loest die
    # Filterung auf genau ein Item auf, ist die Sache klar; sonst bleibt es
    # mehrdeutig, aber wenigstens ohne Rauschen in der Kandidatenliste.
    if len(treffer) > 1:
        mit_artikel = {q: b for q, b in treffer.items()
                       if b.get("deTitle") or b.get("enTitle")}
        if mit_artikel:
            treffer = mit_artikel

    if len(treffer) > 1:
        # Mehrdeutig (z. B. Polymorphe, Minerale) -> zur manuellen Klaerung.
        # Die Kandidaten kommen mit in die Zeile, sonst ist sie nicht
        # abarbeitbar.
        return {
            "ambiguous": True,
            "candidates": [
                f"{qid} ({b.get('itemLabel', {}).get('value', qid)})"
                for qid, b in treffer.items()
            ],
        }
    qid, b = next(iter(treffer.items()))
    return {
        "qid": qid,
        "label": b.get("itemLabel", {}).get("value", qid),
        "ambiguous": False,
        "formel_wikidata": b.get("formel", {}).get("value", ""),
        "title_de": b.get("deTitle", {}).get("value", ""),
        "title_en": b.get("enTitle", {}).get("value", ""),
    }


# ---------------------------------------------------------------------------
# Schritt 3: Pruefen, ob das Statement schon existiert
# ---------------------------------------------------------------------------

_UEBERSPRUNGEN = collections.Counter()


def stufe_kann_nichts_beitragen(qid: str, stufe: str) -> bool:
    """True, wenn das Item alle Properties dieser Stufe schon traegt."""
    return STUFEN_PIDS[stufe] <= fetch_item_pids(qid)


def melde_uebersprungene_stufen() -> None:
    """Was der Lauf sich gespart hat - und was dadurch NICHT in Abschnitt 2
    des Entwurfs steht."""
    if not _UEBERSPRUNGEN:
        return
    text = ", ".join(f"{stufe} {n}x" for stufe, n in
                     sorted(_UEBERSPRUNGEN.items()))
    print(f"  Quellen uebersprungen, weil das Item alle ihre Properties "
          f"schon traegt: {text} (--auch-vorhandene fragt trotzdem)",
          file=sys.stderr)


_CLAIM_CACHE: dict = {}
# wbgetentities nimmt bis zu 50 Items je Anfrage.
CLAIM_CHARGE = 50


def claims_vorladen(qids: list) -> None:
    """Aussagenbestand vieler Items auf einmal holen.

    Eine Anfrage je 50 Items statt je Item - bei 6301 Mineralen sind das
    127 Anfragen statt 6301. Nebenbei faellt der Siedepunkt mit ab: die
    Antwort enthaelt die vollstaendigen Aussagen samt Einheit, wofuer sonst
    eine eigene SPARQL-Abfrage JE ITEM noetig war.
    """
    offen = [q for q in qids if q not in _CLAIM_CACHE]
    for start in range(0, len(offen), CLAIM_CHARGE):
        teil = offen[start:start + CLAIM_CHARGE]
        resp = netz.get_with_retry(WIKIDATA_API, {
            "action": "wbgetentities", "ids": "|".join(teil),
            "props": "claims", "format": "json", "formatversion": "2",
        })
        entities = resp.json().get("entities", {})
        for qid in teil:
            claims = (entities.get(qid) or {}).get("claims", {})
            _CLAIM_CACHE[qid] = set(claims)
            _SIEDEPUNKT_CACHE[qid] = _siedepunkt_aus_claims(claims)


def _siedepunkt_aus_claims(claims: dict) -> Optional[float]:
    """Niedrigster Siedepunkt in Kelvin aus den Rohaussagen, oder None."""
    kelvin = []
    for aussage in claims.get("P2102", []):
        wert = aussage.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(wert, dict):
            continue
        umrechnen = TEMPERATUR_NACH_KELVIN.get(
            str(wert.get("unit", "")).rsplit("/", 1)[-1])
        if umrechnen is None:
            continue
        try:
            kelvin.append(umrechnen(float(wert["amount"])))
        except (TypeError, ValueError):
            continue
    return min(kelvin) if kelvin else None


def fetch_item_pids(qid: str) -> set:
    """Alle P-Nummern, zu denen das Item bereits eine Aussage hat.

    Einmal pro Item statt einmal pro Property abfragen - im
    Periodensystem-Lauf spart das rund drei Viertel der Requests. Im
    Gruppenbetrieb ist der Bestand ohnehin schon chargenweise vorgeladen
    (siehe claims_vorladen), dann kostet diese Funktion gar nichts mehr.
    """
    if qid not in _CLAIM_CACHE:
        claims_vorladen([qid])
    return _CLAIM_CACHE.get(qid, set())


def item_has_statement(qid: str, pid: str) -> bool:
    return pid in fetch_item_pids(qid)


# ---------------------------------------------------------------------------
# Keine Festkoerper-Kennwerte an Stoffen, die bei Raumtemperatur Gas sind
# ---------------------------------------------------------------------------
#
# Diese Groessen beschreiben den FESTKOERPER und gehoeren nicht an ein Item,
# dessen Stoff bei Normalbedingungen ein Gas ist - MP rechnet dann die
# Tieftemperaturphase. Welche Groesse aus welchem Grund gesperrt ist und warum
# Schallgeschwindigkeit und COD-ID BEWUSST fehlen: README, "Keine
# Festkoerper-Kennwerte an Gasen".

from .properties import (  # noqa: E402,F401
    CHEMBOX_FIELDS, NUR_FESTKOERPER, RAUMTEMPERATUR_K, STUFEN_PIDS,
    TEMPERATUR_NACH_KELVIN, WIKIPEDIA_DE_CHEM_FIELDS, WIKIPEDIA_DE_FIELDS,
    WIKIPEDIA_NUMERIC_FIELDS,
)

_SIEDEPUNKT_CACHE = {}


def siedepunkt_kelvin(qid: str) -> Optional[float]:
    """Siedepunkt des Items in Kelvin, oder None wenn nicht ermittelbar.

    Gibt es mehrere Angaben (verschiedene Quellen oder Druecke), gilt die
    niedrigste - fuer die Frage "bei Raumtemperatur schon gasfoermig?" ist
    das die vorsichtige Richtung.
    """
    if qid not in _SIEDEPUNKT_CACHE:
        # Fuellt beide Zwischenspeicher: der Siedepunkt steckt in denselben
        # Rohaussagen, eine eigene Abfrage dafuer waere verschenkt.
        claims_vorladen([qid])
    return _SIEDEPUNKT_CACHE.get(qid)


def ist_bei_raumtemperatur_gas(qid: str) -> bool:
    """True, wenn der Stoff bei 20 C sicher gasfoermig ist.

    Ohne Siedepunkt wird NICHTS behauptet und damit auch nichts unterdrueckt:
    nur 70 der 118 Elemente fuehren P2102, unter den fehlenden sind Sauerstoff
    und die schweren Edelgase. Lieber ein Vorschlag zu viel, der beim
    Durchsehen auffaellt, als eine still verschluckte Zeile.
    """
    siede = siedepunkt_kelvin(qid)
    return siede is not None and siede <= RAUMTEMPERATUR_K
