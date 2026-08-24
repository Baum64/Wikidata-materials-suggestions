"""Ableitungen aus dem Item selbst - ohne jede externe Quelle.

Drei Stufen, die nichts holen, sondern nur umformen, was am Item schon
steht:

    formel_proposals_for_item      Summenformel  -> P527 je funktionaler
                                   Gruppe, P2670 je uebrigem Element
    umstellung_proposals_for_item  P527 -> P2670 (samt Loeschzeile)
    punktgruppe_proposals_for_item Raumgruppe    -> P589

Die chemische Metaklasse (P31) fuer Legierungen stand hier bis 2026-08-23
daneben. Sie folgt nicht aus einer Quelle, sondern aus der
Klassenzugehoerigkeit, und ist deshalb in "Material class structure/
Vorschläge generieren.py" gewandert (Pruefung 'metaklasse') - dort liegt der
P279-Graph ohnehin im Speicher. Die Klassenlage (metaklassen()) bleibt hier:
die Formel-Stufe braucht sie, um Stoffe von Aufzaehlungen zu trennen.

Alle drei gehen OHNE S-Beleg raus: es gibt keine externe Quelle zu
zitieren, und die Herkunft steht in der Notiz. Begruendungen je Stufe im
README.
"""

import collections
import re
from typing import Optional

import requests

from . import netz, wikidata
from .ausgabe import Reference, make_row
from .formeln import elemente_aus_formel, gruppen_aus_formel
from .gruppen import LEGIERUNG_QID
from .konfiguration import WIKIDATA_SPARQL
from .properties import PROPERTY_MAP

# ---------------------------------------------------------------------------
# Funktionale Gruppen -> Wikidata-Items
# ---------------------------------------------------------------------------
#
# Welche Gruppen die Formel hergibt, entscheidet formeln.gruppen_aus_formel -
# reine Chemie ohne Wikidata-Wissen. Erst hier bekommt jede Gruppe ihr Item.
# Gewaehlt ist jeweils das ION bzw. MOLEKUEL, nicht die Verbindungsklasse:
# in Brucit sitzt ein Hydroxidion (Q199877), "hydroxy compound" (Q71421787)
# waere die Klasse der Verbindungen, die eines enthalten - also das Mineral
# selbst und nicht sein Bestandteil.
#
# Alle QIDs sind gegen die Formel am Item (P274) geprueft. Genau daran ist
# silicate(2−) (Q32854872) aufgefallen und deshalb draussen geblieben - es
# traegt SO₃²⁻ statt SiO₃²⁻; siehe formeln.GRUPPEN_SIGNATUREN.
GRUPPEN_QIDS = {
    "H2O":   ("Q283", "Wasser"),
    "OH":    ("Q199877", "Hydroxidion"),
    "NH4":   ("Q190901", "Ammoniumion"),
    "CN":    ("Q185076", "Cyanidion"),
    "CO3":   ("Q27104479", "Carbonation"),
    "C2O4":  ("Q27088221", "Oxalation"),
    "NO3":   ("Q182168", "Nitration"),
    "SO4":   ("Q172290", "Sulfation"),
    "SO3":   ("Q413363", "Sulfition"),
    "PO4":   ("Q177811", "Phosphation"),
    "HPO4":  ("Q27104508", "Hydrogenphosphation"),
    "SiO4":  ("Q21206420", "Silicat(4-)-Ion"),
    "Si2O7": ("Q27110035", "Disilicat(6-)-Ion"),
    "AsO4":  ("Q409221", "Arsenation"),
    "VO4":   ("Q27104568", "Vanadat(3-)-Ion"),
    "CrO4":  ("Q355615", "Chromation"),
    "MoO4":  ("Q27104351", "Molybdation"),
    "WO4":   ("Q27104569", "Wolframation"),
    "SeO4":  ("Q27109020", "Selenation"),
    "IO3":   ("Q27109976", "Iodation"),
    "ClO3":  ("Q217813", "Chloration"),
    "B4O7":  ("Q27077623", "Tetraborat(2-)-Ion"),
    "UO2":   ("Q421141", "Uranylion"),
}


def formel_proposals_for_item(wd_match: dict, formel: str,
                              skip_pids: Optional[set] = None) -> list:
    """Vorschlaege aus der Summenformel des Items - Gruppen und Elemente.

    Anders als alle uebrigen Stufen holt diese NICHTS von aussen: der Wert
    wird aus einer Angabe abgeleitet, die am Item schon steht. Deshalb geht
    die Aussage OHNE S-Beleg raus - siehe OHNE_BELEG_DATENTYPEN, dieselbe
    Ueberlegung wie bei den Identifikatoren. Ein "importiert aus Wikidata"
    waere zirkulaer, und die Ableitung ist am Item selbst nachpruefbar: die
    Formel steht in der Notiz.

    Zwei Stufen, in dieser Reihenfolge:

      P527  je funktionaler Gruppe, so gross wie die Formel sie hergibt -
            Gips (CaSO₄·2H₂O) besteht aus einem Sulfation und zwei Molekuelen
            Wasser, nicht aus losem Schwefel.
      P2670 je Element, das nach Abzug der Gruppen uebrig bleibt - bei Gips
            also nur noch Calcium.

    Was in einer Gruppe gebunden ist, wird also nicht noch einmal als Element
    behauptet. Erkennt die Formel keine Gruppe, bleibt es bei der reinen
    Elementableitung wie bisher.

    Elemente, die nur EINE Moeglichkeit einer Mischreihe sind, werden nicht
    vorgeschlagen, sondern zur Klaerung ausgewiesen - bei "(Fe,Mg)₂SiO₄"
    haengt es vom Glied der Reihe ab, ob Eisen oder Magnesium drinsteckt.
    """
    skip_pids = skip_pids or set()
    gruppen, rest = gruppen_aus_formel(formel)
    return (_gruppen_zeilen(wd_match, formel, gruppen, skip_pids)
            + _element_zeilen(wd_match, formel, rest, skip_pids))


def _gruppen_zeilen(wd_match: dict, formel: str, gruppen: dict,
                    skip_pids: set) -> list:
    """P527-Zeilen fuer die erkannten funktionalen Gruppen."""
    prop_info = PROPERTY_MAP["has_part"]
    if not gruppen or prop_info["pid"] in skip_pids:
        return []

    # Wertgenau pruefen, nicht nur "traegt das Item irgendein P527": die
    # Elementaussagen, die die Umstellung gerade abraeumt, sind ja auch P527.
    vorhandene_werte = p527_werte(wd_match["qid"])
    proposals = []
    for name in sorted(gruppen):
        qid, label = GRUPPEN_QIDS[name]
        anzahl = gruppen[name]
        qualifiers = ([("P1114", str(anzahl), f"Anzahl {anzahl}")]
                      if anzahl is not None else [])
        hinweis = "" if anzahl is not None else ", Anzahl nicht bestimmbar"
        proposals.append(make_row(
            "BEREITS_VORHANDEN" if qid in vorhandene_werte else "VORSCHLAG",
            "Formel", wd_match, prop_info, qid, label,
            Reference(
                url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P274",
                note=f"funktionale Gruppe {name} aus der Summenformel "
                     f"{formel} (P274 am Item){hinweis}",
            ),
            formula=formel, entry_id=f"gruppe-{name}",
            qualifiers=qualifiers, ohne_beleg=True,
        ))
    return proposals


def _element_zeilen(wd_match: dict, formel: str, rest: str,
                    skip_pids: set) -> list:
    """P2670-Zeilen fuer die Elemente, die keine Gruppe gebunden hat.

    `rest` ist die Formel ohne die erkannten Gruppen; ist sie leer, steckt
    jedes Atom schon in einer Gruppe und es bleibt nichts zu sagen. Die
    NOTIZ nennt weiterhin die vollstaendige Formel - nur so ist die Zeile
    am Item nachpruefbar.
    """
    prop_info = PROPERTY_MAP["has_part_of_class"]
    if not rest or prop_info["pid"] in skip_pids:
        return []

    zerlegt = elemente_aus_formel(rest)
    if zerlegt is None:
        return []
    sicher, unsicher = zerlegt
    if not sicher and not unsicher:
        return []

    symbole = wikidata.element_qids()
    # Das Item traegt P2670 schon: dann wird nichts ergaenzt - wer die
    # Zusammensetzung dort von Hand gepflegt hat, weiss mehr als diese
    # Ableitung. Ein bestehendes P527 blockiert dagegen NICHT mehr: zeigt es
    # auf Elemente, stellt die Umstellungsstufe es um (siehe
    # umstellung_proposals_for_item); zeigt es auf Verbindungen (Quarz ->
    # Siliciumdioxid), ist es eine andere Aussage und steht daneben.
    vorhanden = wikidata.item_has_statement(wd_match["qid"], prop_info["pid"])
    # Was die Umstellungsstufe schon aus P527 uebernimmt, hier nicht doppeln.
    schon_umgestellt = {e for e in p527_elemente(wd_match["qid"])}
    proposals = []

    for symbol in sorted(sicher):
        element = symbole.get(symbol)
        if element is None:
            continue  # Elementsymbol ohne Wikidata-Item - nicht raten
        if element["qid"] in schon_umgestellt:
            continue
        anzahl = sicher[symbol]
        qualifiers = ([("P1114", str(anzahl), f"Anzahl {anzahl}")]
                      if anzahl is not None else [])
        hinweis = "" if anzahl is not None else ", Anzahl nicht bestimmbar"
        proposals.append(make_row(
            "BEREITS_VORHANDEN" if vorhanden else "VORSCHLAG",
            "Formel", wd_match, prop_info, element["qid"], element["label"],
            Reference(
                url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P274",
                note=f"abgeleitet aus der Summenformel {formel} "
                     f"(P274 am Item){hinweis}",
            ),
            formula=formel, entry_id=f"formel-{symbol}",
            qualifiers=qualifiers, ohne_beleg=True,
        ))

    if unsicher:
        # Nicht still verschlucken: dass die Formel eine Mischreihe enthaelt,
        # ist die interessanteste Aussage ueber sie.
        namen = ", ".join(
            symbole[s]["label"] if s in symbole else s for s in sorted(unsicher)
        )
        proposals.append(make_row(
            f"MANUELLE_KLAERUNG_NOETIG (Mischreihe in {formel}: {namen} "
            f"stehen zur Wahl, nicht nebeneinander)",
            "Formel", wd_match, prop_info, "", namen,
            Reference(
                url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P274",
                note=f"Mischreihe in {formel} - Elemente nicht ableitbar",
            ),
            formula=formel, entry_id="formel-mischreihe",
            qualifiers=[], ohne_beleg=True,
        ))
    return proposals


# ---------------------------------------------------------------------------
# Umstellung P527 -> P2670 an bestehenden Aussagen
# ---------------------------------------------------------------------------
#
# 24538 Aussagen im Bestand sagen "Stoff P527 Element" (gemessen 2026-08-21).
# Sie meinen die Zusammensetzung, sagen aber mereologisch etwas anderes: das
# Item eines Elements ist die KLASSE seiner Atome. Richtig ist P2670. Diese
# Stufe stellt bestehende Aussagen um - als EINZIGE im ganzen Werkzeug
# erzeugt sie dabei auch Loeschzeilen.
#
# Uebernommen wird nur, was QuickStatements verlustfrei umsetzen kann:
# Anzahl (P1114) ja, Belege und andere Qualifikatoren nein - die liessen sich
# nicht mitnehmen, deshalb gehen solche Aussagen zur Klaerung statt zur
# Umstellung. Zahlen: README, "Umstellung P527 -> P2670".

_P527_CACHE = {}
# Alle P527-WERTE je Item, nicht nur die Elemente: die Gruppenstufe muss
# wissen, ob genau ihr Ion schon am Item steht. "Traegt das Item irgendein
# P527?" (item_has_statement) reicht dafuer nicht - die Altaussagen auf
# Elemente, die die Umstellung gerade abraeumt, sind ja auch P527.
_P527_WERTE: dict = {}
P527_CHARGE = 200


def fetch_p527_elemente(qids: list) -> dict:
    """{QID: {Element-QID: {anzahl, beleg, andere, schon_p2670}}}.

    Nur Werte, die ein chemisches Element sind - ein P527 auf eine Verbindung
    (Quarz -> Siliciumdioxid) ist eine andere Aussage und bleibt unberuehrt.
    """
    if not qids:
        return {}
    nach_qid = {info["qid"] for info in wikidata.element_qids().values()}
    werte = " ".join(f"wd:{q}" for q in qids)
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT ?i ?e ?anzahl ?beleg ?anderer ?p2670 WHERE {{
      VALUES ?i {{ {werte} }}
      {{
        ?i p:P527 ?st . ?st ps:P527 ?e .
        OPTIONAL {{ ?st pq:P1114 ?anzahl }}
        OPTIONAL {{ ?st prov:wasDerivedFrom ?beleg }}
        OPTIONAL {{
          ?st ?q ?qv .
          FILTER(STRSTARTS(STR(?q), "http://www.wikidata.org/prop/qualifier/"))
          # Ohne diese Zeile zaehlt der Wertknoten JEDER Mengenangabe als
          # fremder Qualifikator: P1114 haengt zusaetzlich unter
          # .../qualifier/value/P1114, und daran ist die Umstellung von
          # Wasser (Q283) zuerst gescheitert.
          FILTER(!STRSTARTS(STR(?q), "http://www.wikidata.org/prop/qualifier/value"))
          FILTER(?q != pq:P1114)
          BIND(?q AS ?anderer)
        }}
      }} UNION {{
        ?i wdt:P2670 ?e . BIND(true AS ?p2670)
      }}
    }}
    """})
    out = {q: {} for q in qids}
    for q in qids:
        _P527_WERTE.setdefault(q, set())
    for b in resp.json()["results"]["bindings"]:
        qid = b["i"]["value"].rsplit("/", 1)[-1]
        element = b["e"]["value"].rsplit("/", 1)[-1]
        if "p2670" not in b:
            _P527_WERTE[qid].add(element)
        if element not in nach_qid:
            continue  # keine Elementaussage - geht diese Stufe nichts an
        eintrag = out[qid].setdefault(
            element, {"anzahl": None, "beleg": False, "andere": False,
                      "schon_p2670": False, "p527": False})
        if "p2670" in b:
            eintrag["schon_p2670"] = True
            continue
        eintrag["p527"] = True
        if "anzahl" in b:
            eintrag["anzahl"] = b["anzahl"]["value"]
        eintrag["beleg"] = eintrag["beleg"] or "beleg" in b
        eintrag["andere"] = eintrag["andere"] or "anderer" in b
    return out


def p527_vorladen(qids: list) -> None:
    """Elementaussagen vieler Items auf einmal holen und merken."""
    offen = [q for q in qids if q not in _P527_CACHE]
    for start in range(0, len(offen), P527_CHARGE):
        _P527_CACHE.update(
            fetch_p527_elemente(offen[start:start + P527_CHARGE]))


def p527_elemente(qid: str) -> dict:
    """Elementaussagen EINES Items, aus dem Zwischenspeicher oder frisch."""
    if qid not in _P527_CACHE:
        _P527_CACHE.update(fetch_p527_elemente([qid]))
    return _P527_CACHE.get(qid, {})


def p527_werte(qid: str) -> set:
    """Alle QIDs, die am Item schon als P527 stehen."""
    if qid not in _P527_WERTE:
        p527_elemente(qid)
    return _P527_WERTE.get(qid, set())


def umstellung_proposals_for_item(wd_match: dict, formel: str = "",
                                  skip_pids: Optional[set] = None) -> list:
    """Bestehende P527-Elementaussagen auf P2670 umstellen.

    Je Aussage zwei Zeilen: die neue P2670-Aussage samt Anzahl und die
    Loeschzeile fuer die alte. Beide gehoeren zusammen - wer nur die eine
    einspielt, hat entweder eine Dublette oder eine Luecke.

    Umgestellt wird nur an STOFFEN, erkennbar an einer Summenformel oder an
    der Einordnung als Legierung. Der Grund steht im Bestand: "Alkalimetalle"
    (Q19557) fuehrt seine MITGLIEDER mit P527 - Caesium, Lithium und so fort.
    Das ist dort die richtige Aussage; "Alkalimetalle enthaelt Teile der
    Klasse Caesium" waere es nicht. Solche Sammelbegriffe haengen wegen des
    bekannten Modellierungsfehlers mitten in der Legierungsgruppe.
    """
    skip_pids = skip_pids or set()
    if not formel and not metaklassen(wd_match["qid"])["legierung"]:
        return []
    neu_info = PROPERTY_MAP["has_part_of_class"]
    alt_info = PROPERTY_MAP["has_part"]
    if neu_info["pid"] in skip_pids:
        return []

    symbole = {info["qid"]: info for info in wikidata.element_qids().values()}
    proposals = []
    for element, lage in sorted(p527_elemente(wd_match["qid"]).items()):
        if not lage["p527"]:
            continue
        name = symbole.get(element, {}).get("label", element)
        beleg = Reference(
            url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P527",
            note=f"Umstellung der bestehenden Aussage P527 -> {name} auf "
                 f"P2670; das Element-Item ist die Klasse seiner Atome",
        )

        if lage["beleg"] or lage["andere"]:
            # QuickStatements kann Belege und Qualifikatoren einer
            # bestehenden Aussage nicht mitnehmen. Umstellen hiesse hier,
            # sie zu verlieren - das entscheidet ein Mensch.
            fehlt = " und ".join(
                t for t in (("Beleg" if lage["beleg"] else ""),
                            ("weitere Qualifikatoren" if lage["andere"] else ""))
                if t)
            proposals.append(make_row(
                f"MANUELLE_KLAERUNG_NOETIG (P527 -> {name} traegt {fehlt}; "
                f"eine Umstellung per QuickStatements wuerde das verlieren - "
                f"von Hand umhaengen)",
                "Umstellung", wd_match, alt_info, element, name, beleg,
                entry_id=f"umstellung-{element}", qualifiers=[],
                ohne_beleg=True,
            ))
            continue

        if not lage["schon_p2670"]:
            anzahl = lage["anzahl"]
            qualifiers = ([("P1114", str(int(float(anzahl))),
                            f"Anzahl {int(float(anzahl))}")]
                          if anzahl and re.fullmatch(r"\d+(\.0*)?", anzahl)
                          else [])
            proposals.append(make_row(
                "VORSCHLAG", "Umstellung", wd_match, neu_info, element, name,
                beleg, entry_id=f"umstellung-{element}",
                qualifiers=qualifiers, ohne_beleg=True,
            ))

        proposals.append(make_row(
            "VORSCHLAG", "Umstellung", wd_match, alt_info, element, name,
            Reference(
                url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P527",
                note=f"ERSETZT durch P2670 -> {name}; diese Zeile ENTFERNT "
                     f"die alte Aussage",
            ),
            entry_id=f"umstellung-{element}", qualifiers=[], ohne_beleg=True,
            entfernen=True,
        ))
    return proposals


# ---------------------------------------------------------------------------
# Klassenlage: ist das Item eine Legierung, und welche P31 traegt es?
# ---------------------------------------------------------------------------
#
# Kein eigener Vorschlag mehr, sondern Vorarbeit fuer die Formel-Stufe: ein
# Item ohne Summenformel gilt nur dann als Stoff, wenn es eine Legierung ist
# (siehe umstellung_proposals_for_item). Die Metaklasse selbst wird hier
# nicht mehr vorgeschlagen - das tut "Material class structure/Vorschläge
# generieren.py", Pruefung 'metaklasse'.

# Wikidata fuehrt Q11426 "Metall" als Unterklasse von Q37756 "Legierung".
# Ueber diesen Knoten haengt alles Metallische unter der Legierung - auch
# Sammelbegriffe wie "Platinmetalle" oder "metals of antiquity", die gar keine
# Werkstoffe sind, sondern Aufzaehlungen. Sie als Legierung zu behandeln waere
# schlicht falsch. Der Knoten wird deshalb beim Pruefen der
# Klassenzugehoerigkeit ausgespart, siehe legierungs_qids.
METALL_QID = "Q11426"


def legierungs_qids(qids: list) -> set:
    """Welche der Items sind Legierungen - ohne den Umweg ueber "Metall"?

    Gefragt ist nicht bloss, ob das Item irgendwie unter Q37756 haengt: das
    tut wegen Q11426 (siehe METALL_QID) jeder Sammelbegriff fuer Metalle. Die
    Kante ueber Q11426 wird deshalb ausgespart und der Rest des Klassenwegs
    hier durchlaufen - in SPARQL laesst sich ein AUSGESPARTER Knoten in einem
    Pfad nicht ausdruecken.

    Ein simples "hat gar keinen Metall-Weg" reicht nicht: Stahl hat einen,
    kommt aber ausserdem ueber Ferrolegierung an die Legierung heran und ist
    selbstverstaendlich eine.
    """
    if not qids:
        return set()
    werte = " ".join(f"wd:{q}" for q in qids)
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT DISTINCT ?von ?nach WHERE {{
      VALUES ?i {{ {werte} }}
      {{ ?i (wdt:P31|wdt:P279) ?nach . BIND(?i AS ?von) }}
      UNION
      {{ ?i (wdt:P31|wdt:P279)/wdt:P279* ?von .
         FILTER(?von != wd:{METALL_QID})
         ?von wdt:P279 ?nach . }}
    }}
    """})
    kanten = collections.defaultdict(set)
    for b in resp.json()["results"]["bindings"]:
        von = b["von"]["value"].rsplit("/", 1)[-1]
        kanten[von].add(b["nach"]["value"].rsplit("/", 1)[-1])

    gefunden = set()
    for qid in qids:
        if qid == METALL_QID:
            # Der Ausgangsknoten selbst: "Metalle" haengt nur ueber die
            # defekte Kante unter der Legierung. Ohne diesen Sonderfall
            # gaelte ausgerechnet Q11426 als Legierung.
            continue
        gesehen, offen = set(), list(kanten.get(qid, ()))
        while offen:
            knoten = offen.pop()
            if knoten == LEGIERUNG_QID:
                gefunden.add(qid)
                break
            if knoten in gesehen or knoten == METALL_QID:
                continue
            gesehen.add(knoten)
            offen.extend(kanten.get(knoten, ()))
    return gefunden


def fetch_metaklassen(qids: list) -> dict:
    """{QID: {"p31": [QID, ...], "legierung": bool}} fuer die Items.

    Eine Abfrage fuer die P31-Werte, eine fuer die Klassenzugehoerigkeit -
    beide fuer die ganze Charge statt je Item.
    """
    if not qids:
        return {}
    werte = " ".join(f"wd:{q}" for q in qids)
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT ?i ?klasse WHERE {{
      VALUES ?i {{ {werte} }}
      ?i wdt:P31 ?klasse .
    }}
    """})
    p31 = {q: [] for q in qids}
    for b in resp.json()["results"]["bindings"]:
        qid = b["i"]["value"].rsplit("/", 1)[-1]
        klasse = b["klasse"]["value"].rsplit("/", 1)[-1]
        if klasse not in p31[qid]:
            p31[qid].append(klasse)

    legierungen = legierungs_qids(qids)
    return {q: {"p31": p31[q], "legierung": q in legierungen} for q in qids}


_METAKLASSE_CACHE = {}
# 200 Items je Abfrage - wie bei den Raumgruppen.
METAKLASSE_CHARGE = 200


def metaklassen_vorladen(qids: list) -> None:
    """Metaklassen vieler Items auf einmal holen und merken."""
    offen = [q for q in qids if q not in _METAKLASSE_CACHE]
    for start in range(0, len(offen), METAKLASSE_CHARGE):
        _METAKLASSE_CACHE.update(
            fetch_metaklassen(offen[start:start + METAKLASSE_CHARGE]))


def metaklassen(qid: str) -> dict:
    """Metaklassen-Lage EINES Items, aus dem Zwischenspeicher oder frisch."""
    if qid not in _METAKLASSE_CACHE:
        _METAKLASSE_CACHE.update(fetch_metaklassen([qid]))
    return _METAKLASSE_CACHE.get(qid, {"p31": [], "legierung": False})


# ---------------------------------------------------------------------------
# Punktgruppe (P589) aus der Raumgruppe (P690) am Item
# ---------------------------------------------------------------------------
#
# Dieselbe Bauart wie die beiden Ableitungen davor: der Wert steht schon am
# Item, nur in einer anderen Property. Jede der 230 Raumgruppen gehoert zu
# genau einer der 32 kristallographischen Punktgruppen, und Wikidata fuehrt
# diese Zuordnung bereits an den Raumgruppen-Items selbst (230 von 236 tragen
# P589). Es ist also nichts abzuleiten, sondern nur nachzuschlagen.
#
# Warum das lohnt (gemessen 2026-08-19): 2876 Items tragen eine Raumgruppe,
# aber nur 18 davon auch eine Punktgruppe. Fuer 2851 laesst sie sich
# nachschlagen, darunter 2602 Mineralarten. Zahlen und Grenzen: README,
# "Punktgruppe (P589) aus der Raumgruppe".

def punktgruppe_proposals_for_item(wd_match: dict,
                                   skip_pids: Optional[set] = None) -> list:
    """P589-Vorschlag aus der Raumgruppe (P690), die am Item schon steht.

    Holt nichts von aussen ausser dem Nachschlagewerk selbst und geht deshalb
    - wie die uebrigen abgeleiteten Aussagen - OHNE S-Beleg raus.

    Traegt das Item MEHRERE Raumgruppen (56 Items am Bestand, meist mehrere
    Modifikationen an einem Item), wird nichts vorgeschlagen: welche gemeint
    ist, entscheidet die Fachfrage, nicht das Skript.
    """
    skip_pids = skip_pids or set()
    prop_info = PROPERTY_MAP["point_group"]
    if prop_info["pid"] in skip_pids:
        return []

    raumgruppen = wikidata.item_raumgruppen(wd_match["qid"])
    if not raumgruppen:
        return []
    tabelle = wikidata.raumgruppen_nach_qid()

    if len(raumgruppen) > 1:
        namen = ", ".join(
            tabelle[q]["label"] if q in tabelle else q for q in raumgruppen)
        return [make_row(
            f"MANUELLE_KLAERUNG_NOETIG (mehrere Raumgruppen am Item: {namen} "
            f"- welche Modifikation gemeint ist, entscheidet die Fachfrage)",
            "Raumgruppe", wd_match, prop_info, "", namen,
            Reference(
                url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P690",
                note=f"mehrere Raumgruppen am Item ({namen}) - Punktgruppe "
                     f"nicht eindeutig",
            ),
            entry_id="punktgruppe", qualifiers=[], ohne_beleg=True,
        )]

    sg = tabelle.get(raumgruppen[0])
    if sg is None or not sg["pg_qid"]:
        return []  # Raumgruppe ohne Punktgruppe am Item - nicht raten

    vorhanden = wikidata.item_has_statement(wd_match["qid"], prop_info["pid"])
    return [make_row(
        "BEREITS_VORHANDEN" if vorhanden else "VORSCHLAG",
        "Raumgruppe", wd_match, prop_info, sg["pg_qid"], sg["pg_label"],
        Reference(
            url=f"https://www.wikidata.org/wiki/{wd_match['qid']}#P690",
            note=f"aus der Raumgruppe {sg['label']} (P690 am Item); die "
                 f"Punktgruppe steht am Raumgruppen-Item selbst (P589)",
        ),
        entry_id="punktgruppe", qualifiers=[], ohne_beleg=True,
    )]
