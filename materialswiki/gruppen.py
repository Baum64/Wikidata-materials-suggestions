"""Werkstoffgruppen: welche Items ein Lauf ueberhaupt anfasst.

Die Muster der Gruppen, die Prueflisten-Gruppe aus [[en:List of named
alloys]] und die Frage, was ueberhaupt eine Legierung ist. Der Filter der
Legierungsgruppe ist der heikelste Teil: Wikidata fuehrt "Metalle" als
Unterklasse von "Legierung", ohne Filter ist die Grundgesamtheit Muell.
Zahlen und Begruendungen: README, "Werkstoffgruppen".
"""

import collections
import re
import sys
from typing import Optional

import requests

from . import netz, wikidata
from .konfiguration import WIKIDATA_API, WIKIDATA_SPARQL

# ---------------------------------------------------------------------------
# Schritt 2a: Elemente des Periodensystems -> bestehende Wikidata-Items
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Metalle und Halbmetalle
# ---------------------------------------------------------------------------
#
# Feste Liste statt Wikidata-Abfrage, weil Wikidatas Klassifikation dafuer zu
# lueckenhaft ist (die Messung dazu: README, "Auswahl im Periodensystem-Modus").
# Definiert wird ueber die NICHT-Metalle - die kuerzere, stabilere Liste;
# alles andere ist Metall oder Halbmetall.
#
# Grenzfaelle, bewusst so entschieden:
#   Po, At   Halbmetall (Po) bzw. Nichtmetall (At), wie im gaengigen
#            Periodensystem farblich dargestellt
#   Ts, Og   Zuordnung ist rein theoretisch (nie in Substanzmenge erzeugt);
#            als Nichtmetalle gefuehrt, praktisch ohnehin ohne Datenlage
HALBMETALLE = frozenset({"B", "Si", "Ge", "As", "Sb", "Te", "Po"})
NICHTMETALLE = frozenset({
    "H", "He", "C", "N", "O", "F", "Ne", "P", "S", "Cl", "Ar",
    "Se", "Br", "Kr", "I", "Xe", "At", "Rn", "Ts", "Og",
})


def ist_metall_oder_halbmetall(symbol: str) -> bool:
    """True fuer Metalle und Halbmetalle, False fuer Nichtmetalle."""
    return symbol not in NICHTMETALLE


# ---------------------------------------------------------------------------
# Legierungen
# ---------------------------------------------------------------------------
#
# Ohne Filter ist die Grundgesamtheit Muell: Wikidata fuehrt Q11426 "Metalle"
# als Unterklasse von Q37756 "Legierung", also haengt jedes Metall und jedes
# Isotop darunter. Ausgeschlossen wird, was eine ORDNUNGSZAHL traegt - warum
# genau dieser Schnitt und nicht der naheliegendere: README,
# "Werkstoffgruppen".
LEGIERUNG_QID = "Q37756"

# Ohne diesen Filter ist die Grundgesamtheit Muell - siehe oben.
LEGIERUNG_OHNE_ELEMENTE = "FILTER NOT EXISTS { ?i wdt:P1086 ?ordnungszahl }"
LEGIERUNG_PATTERN = (
    f"{{ ?i wdt:P31/wdt:P279* wd:{LEGIERUNG_QID} }} UNION "
    f"{{ ?i wdt:P279* wd:{LEGIERUNG_QID} }} {LEGIERUNG_OHNE_ELEMENTE}"
)

# Mineralarten: Instanzen von Q12089225, also die von der IMA gefuehrten
# Arten - NICHT der Subtree unter Q7946 "Mineral", der auch Gruppen und
# Sammelbegriffe enthaelt. Mit Abstand die ergiebigste Gruppe fuer COD:
# 5694 der 6301 Arten tragen eine Summenformel, aber KEINE EINZIGE eine
# COD-ID, und 3916 fehlt die Raumgruppe (gemessen 2026-08-16).
MINERAL_PATTERN = "?i wdt:P31 wd:Q12089225 ."

# Oxide: der Subtree unter Q50690 umfasst 27670 Items, davon sind die
# allermeisten labellose Massenimporte ohne jede Angabe (Q37807585 ff.).
# Brauchbar sind die mit Summenformel - 154 Stueck, davon 151 ohne
# Raumgruppe. Die Formel ist hier also Teil der DEFINITION, nicht bloss ein
# Filter: ohne sie ist ein Item fuer diesen Zweck wertlos.
OXID_PATTERN = (
    "{ ?i wdt:P31/wdt:P279* wd:Q50690 } UNION { ?i wdt:P279* wd:Q50690 } "
    "?i wdt:P274 ?pflichtformel ."
)

# Carbide: der Subtree unter Q241906 ist mit 27 Items winzig, aber sauber -
# fast durchweg technisch relevante Hartstoffe (SiC, WC, TiC, B4C ...), kein
# Massenimport. Deshalb hier KEIN Formelzwang wie bei den Oxiden: die 10
# Items ohne Summenformel (Zementit, Urancarbide, Mangancarbid ...) sind
# gerade die, bei denen etwas vorzuschlagen ist.
CARBID_QID = "Q241906"
CARBID_PATTERN = (
    f"{{ ?i wdt:P31/wdt:P279* wd:{CARBID_QID} }} UNION "
    f"{{ ?i wdt:P279* wd:{CARBID_QID} }}"
)

# Polymere / Kunststoffe: der Subtree unter Q11474 "Kunststoff" (haengt per
# P279 direkt an Q214609 Material). Gemessen 2026-08-30: 795 Items, davon 206
# Klassen; nur 8 tragen eine Summenformel (Polyethylen hat keine), aber 113
# einen de-Wikipedia-Artikel. COD/MP/NIST steuern hier also wenig bei, die
# Infoboxen (Dichte, Schmelzpunkt) mehr. Kein Formelzwang - der Wert des
# Laufs liegt in Struktur und Infobox-Kennzahlen, nicht in der Kristallografie.
#
# Bewusst Q11474 (Kunststoff) statt Q81163 (polymer, der Chemiebegriff): Q81163
# umfasst auch Biopolymere (Proteine, DNA, Cellulose) und ist ein
# heterogener Massenimport - fuer eine WERKSTOFF-Grundgesamtheit ungeeignet.
KUNSTSTOFF_QID = "Q11474"
KUNSTSTOFF_PATTERN = (
    f"{{ ?i wdt:P31/wdt:P279* wd:{KUNSTSTOFF_QID} }} UNION "
    f"{{ ?i wdt:P279* wd:{KUNSTSTOFF_QID} }}"
)

# Magnetwerkstoffe: der Subtree unter Q949573 "Magnetwerkstoffe" (P279 ->
# Q214609 Material). Winzig - mit dem Ordnungszahl-Filter bleiben ~17 Klassen
# (weich-/hartmagnetische Werkstoffe, Ferrite, ferromagnetisches Material,
# Antiferromagnet, Permalloy, Alnico ...). OHNE den Filter zieht Q949573 ueber einen schiefen
# Instanzpfad (Nickel Q744 haengt darunter) rund 40 Nickel-Isotope herein -
# dieselbe Art Fehlkante wie "Metalle unter Legierung". Der Filter ist hier
# also Pflicht, nicht Kosmetik. Wegen der geringen Groesse ist der Ertrag an
# Messwert-Vorschlaegen minimal; der Lauf lohnt vor allem fuer die Struktur.
MAGNETWERKSTOFF_QID = "Q949573"

# Zusaetzliche Anker neben Q949573: "Weichmagnetische Werkstoffe" (Q2554911)
# und "ferromagnetic material" (Q9259184). Beide haengen per P279 direkt unter
# Q949573 - aber genau diese Kante meldet die 'verkehrt'-Heuristik (Baum zu
# duenn besetzt, 48:3) faelschlich zur Loeschung. Als eigene Wurzeln gefuehrt,
# bleibt der ganze ferromagnetische Zweig (Ferrite, ferromagnetische
# Kristalle/Minerale, Permalloy, Alnico ...) in der Grundgesamtheit, egal was
# mit der einen Kante passiert. Kostet nichts, solange die Kanten stehen -
# dann liefern alle drei Wurzeln dieselben Items.
MAGNET_WURZELN = (MAGNETWERKSTOFF_QID, "Q2554911", "Q9259184")
_MAGNET_WURZEL_VALUES = " ".join(f"wd:{q}" for q in MAGNET_WURZELN)
MAGNET_PATTERN = (
    f"VALUES ?magnetwurzel {{ {_MAGNET_WURZEL_VALUES} }} "
    f"{{ {{ ?i wdt:P31/wdt:P279* ?magnetwurzel }} UNION "
    f"{{ ?i wdt:P279* ?magnetwurzel }} }} {LEGIERUNG_OHNE_ELEMENTE}"
)

# ---------------------------------------------------------------------------
# Benannte Legierungen aus der Wikipedia-Liste
# ---------------------------------------------------------------------------
#
# [[en:List of named alloys]] fuehrt die Legierungen mit EIGENEM NAMEN
# (Duralumin, Hastelloy, Nitinol ...), gruppiert nach Basismetall. Sie ist als
# PRUEFLISTE wertvoller denn als Datenquelle - Zahlen dazu im README,
# "Pruefliste statt Datenquelle".
NAMED_ALLOYS_SEITE = "List_of_named_alloys"
NAMED_ALLOYS_API = "https://en.wikipedia.org/w/api.php"

# Der einleitende Abschnitt listet nur die Basismetalle selbst, keine
# Legierungen - er wird uebersprungen.
NAMED_ALLOYS_KEIN_ABSCHNITT = "Alloys by base metal"


def fetch_named_alloys() -> list:
    """[{titel, basis}] aus [[en:List of named alloys]].

    `basis` ist das Basismetall aus der Abschnittsueberschrift (Aluminum,
    Copper, Iron ...) - die Information, aus der sich eine sinnvolle
    P279-Einordnung ableiten liesse.
    """
    resp = netz.request_with_retry("GET", NAMED_ALLOYS_API, params={
        "action": "parse", "page": NAMED_ALLOYS_SEITE, "prop": "wikitext",
        "format": "json", "formatversion": "2",
    })
    daten = resp.json()
    if "error" in daten:
        raise RuntimeError(daten["error"].get("info", "Seite nicht lesbar"))
    wikitext = daten["parse"]["wikitext"]

    eintraege = []
    abschnitt = ""
    for zeile in wikitext.splitlines():
        ueberschrift = re.match(r"^(={2,3})\s*(.+?)\s*\1\s*$", zeile)
        if ueberschrift:
            abschnitt = ueberschrift.group(2)
            continue
        treffer = re.match(r"^\*\s*\[\[([^\]|#]+)", zeile)
        if treffer and abschnitt and abschnitt != NAMED_ALLOYS_KEIN_ABSCHNITT:
            eintraege.append({"titel": treffer.group(1).strip(),
                              "basis": abschnitt})
    return eintraege


def named_alloys_als_items() -> tuple:
    """(Items im Format von fetch_group_items, Liste der Namen OHNE Item).

    Die Zuordnung laeuft ueber den enwiki-Sitelink, nicht ueber die
    Bezeichnung - ein Labelabgleich wuerde bei "Mulberry" oder "Elektron"
    munter danebengreifen.
    """
    eintraege = fetch_named_alloys()
    nach_titel = {e["titel"]: e for e in eintraege}
    items, ohne_item = [], []

    titel = list(nach_titel)
    gefunden_titel = set()
    for start in range(0, len(titel), 50):
        resp = netz.request_with_retry("GET", WIKIDATA_API, params={
            "action": "wbgetentities", "sites": "enwiki",
            "titles": "|".join(titel[start:start + 50]),
            "props": "labels|claims|sitelinks", "languages": "de|en",
            "format": "json", "formatversion": "2",
        })
        for qid, eintrag in resp.json().get("entities", {}).items():
            if not qid.startswith("Q") or "missing" in eintrag:
                continue
            sitelinks = eintrag.get("sitelinks", {})
            en_titel = sitelinks.get("enwiki", {}).get("title", "")
            gefunden_titel.add(en_titel)
            labels = eintrag.get("labels", {})
            claims = eintrag.get("claims", {})
            formeln = claims.get("P274", [])
            items.append({
                "qid": qid,
                "label": (labels.get("de") or labels.get("en")
                          or {"value": qid})["value"],
                "formula": (formeln[0]["mainsnak"].get("datavalue", {})
                            .get("value", "") if formeln else ""),
                "title_de": sitelinks.get("dewiki", {}).get("title", ""),
                "title_en": en_titel,
                "basis": nach_titel.get(en_titel, {}).get("basis", ""),
            })
    ohne_item = sorted(t for t in titel if t not in gefunden_titel)
    items.sort(key=lambda e: int(e["qid"][1:]))
    return items, ohne_item


WERKSTOFFGRUPPEN = {
    "legierungen": {
        "pattern": LEGIERUNG_PATTERN,
        "beschreibung": "Legierungen (Q37756, ohne Elemente und Isotope)",
    },
    "benannte-legierungen": {
        "pattern": None,   # kommt aus der Wikipedia-Liste, nicht aus SPARQL
        "beschreibung": "benannte Legierungen aus [[en:List of named alloys]]",
        "items": named_alloys_als_items,
    },
    "minerale": {
        "pattern": MINERAL_PATTERN,
        "beschreibung": "Mineralarten (Q12089225, IMA-gefuehrt)",
        # Was die Oxidgruppe ohnehin abdeckt, laeuft dort - und dort besser:
        # sie ist klein, jedes ihrer Items traegt eine Summenformel, und ein
        # eigener Aufruf dafuer gibt es. Doppelte Vorschlaege in zwei Dateien
        # helfen niemandem. Gemessen 2026-08-23: die Ueberschneidung ist
        # klein (7 von 6304), es geht also um Sauberkeit, nicht um Tempo.
        "ausschluss": ("oxide",),
    },
    "oxide": {
        "pattern": OXID_PATTERN,
        "beschreibung": "Oxide mit Summenformel (Q50690)",
    },
    "carbide": {
        "pattern": CARBID_PATTERN,
        "beschreibung": "Carbide (Q241906)",
    },
    "polymer": {
        "pattern": KUNSTSTOFF_PATTERN,
        "beschreibung": "Polymere / Kunststoffe (Q11474)",
    },
    "magnetwerkstoffe": {
        "pattern": MAGNET_PATTERN,
        "beschreibung": "Magnetwerkstoffe (Q949573, ohne Isotope)",
    },
}


def fetch_group_items(pattern: str, limit: Optional[int] = None) -> list:
    """Items einer Werkstoffgruppe, mit Formel und Artikeltiteln.

    Wie ergiebig das ist, haengt stark an der Gruppe (gemessen 2026-08-16):

        Gruppe        Items   mit Formel   mit de-Artikel
        Legierungen     568        10           178
        Mineralarten   6301      5694          1806
        Oxide           154       154           108

    Bei den Legierungen ist die Summenformel die Ausnahme - Stahl hat keine
    -, weshalb COD und Materials Project dort kaum etwas beitragen koennen.
    Bei Mineralen und Oxiden ist sie die Regel.
    """
    query = f"""
    SELECT ?i ?iLabel ?formel ?deTitle ?enTitle WHERE {{
      {pattern}
      OPTIONAL {{ ?i wdt:P274 ?formel . }}
      OPTIONAL {{ ?ade schema:about ?i ; schema:isPartOf <https://de.wikipedia.org/> ;
                       schema:name ?deTitle . }}
      OPTIONAL {{ ?aen schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> ;
                       schema:name ?enTitle . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"query": query, "format": "json"})
    gefunden = {}
    for b in resp.json()["results"]["bindings"]:
        qid = b["i"]["value"].rsplit("/", 1)[-1]
        eintrag = gefunden.setdefault(qid, {
            "qid": qid,
            "label": b.get("iLabel", {}).get("value", qid),
            "formula": "",
            "title_de": "",
            "title_en": "",
        })
        for feld, schluessel in (("formel", "formula"), ("deTitle", "title_de"),
                                 ("enTitle", "title_en")):
            if feld in b and not eintrag[schluessel]:
                eintrag[schluessel] = b[feld]["value"]
    # Stabile Reihenfolge: erst die mit Artikel (dort ist etwas zu holen),
    # dann nach QID - so ist ein abgebrochener Lauf reproduzierbar.
    alle = sorted(gefunden.values(),
                  key=lambda e: (not e["title_de"], int(e["qid"][1:])))
    return alle[:limit] if limit else alle


def gruppen_qids(gruppe: str) -> set:
    """Nur die QIDs einer Gruppe - fuer den Abgleich zwischen Gruppen.

    Billiger als fetch_group_items: keine Labels, keine Artikeltitel.
    """
    info = WERKSTOFFGRUPPEN[gruppe]
    if not info.get("pattern"):
        return {e["qid"] for e in info["items"]()[0]}
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT DISTINCT ?i WHERE {{ {info["pattern"]} }}
    """})
    return {b["i"]["value"].rsplit("/", 1)[-1]
            for b in resp.json()["results"]["bindings"]}


def items_der_gruppe(gruppe: str, limit: Optional[int] = None,
                     ausschluss: bool = True) -> list:
    """Itemliste einer Gruppe - aus SPARQL oder aus einer Wikipedia-Liste.

    Deklariert die Gruppe einen "ausschluss", werden Items, die auch in jener
    Gruppe stehen, hier weggelassen: sie laufen im eigenen Aufruf mit, und
    zweimal dasselbe vorzuschlagen hilft niemandem. Das geschieht VOR --limit,
    damit die Zahl dort die tatsaechlich bearbeiteten Items meint.
    """
    info = WERKSTOFFGRUPPEN[gruppe]
    if info.get("items"):
        items, ohne_item = info["items"]()
        if ohne_item:
            # Das ist der eigentliche Ertrag der Prueflisten-Gruppe: Namen,
            # fuer die es in Wikidata noch gar kein Item gibt. Anlegen kann
            # dieses Werkzeug sie nicht - es arbeitet nur an bestehenden
            # Items -, aber sie gehoeren ins Protokoll.
            print(f"  {len(ohne_item)} Eintraege der Liste haben KEIN "
                  f"Wikidata-Item: {', '.join(ohne_item)}", file=sys.stderr)
    else:
        items = fetch_group_items(info["pattern"])

    for andere in (info.get("ausschluss", ()) if ausschluss else ()):
        try:
            fremd = gruppen_qids(andere)
        except (RuntimeError, ValueError, requests.RequestException) as fehler:
            print(f"  Gruppe '{andere}' nicht abgefragt, es wird nichts "
                  f"ausgeschlossen - {fehler}", file=sys.stderr)
            continue
        vorher = len(items)
        items = [e for e in items if e["qid"] not in fremd]
        if vorher != len(items):
            print(f"  {vorher - len(items)} Items uebersprungen, weil sie in "
                  f"Gruppe '{andere}' stehen - dort laufen sie mit "
                  f"(--mit-ueberschneidungen nimmt sie hier dazu).",
                  file=sys.stderr)

    items = items[:limit] if limit else items
    mit_formel = sum(1 for e in items if e["formula"])
    mit_artikel = sum(1 for e in items if e["title_de"] or e["title_en"])
    print(f"{len(items)} Items in Gruppe '{gruppe}' - {info['beschreibung']} "
          f"({mit_formel} mit Summenformel, {mit_artikel} mit Wikipedia-Artikel).",
          file=sys.stderr)
    return items


def pruefe_legierungsklasse(gruppe: str, items: list) -> list:
    """Meldet Items, die nicht als Legierung klassifiziert sind.

    Nur fuer die Prueflisten-Gruppe sinnvoll: dort steht durch die Herkunft
    fest, dass es sich um Legierungen HANDELN SOLL. In den SPARQL-Gruppen ist
    die Klassifikation per Definition schon erfuellt.

    Vorgeschlagen wird NICHTS - die Einordnung eines Werkstoffs in die
    Klassenhierarchie ist eine fachliche Entscheidung, und
    [[Wikidata:WikiProject Materials/Materials]] verlangt dafuer eine
    differenzierte Einhaengung (Ferrous alloy, Alloy steel, ...), die sich
    aus dem Basismetall allein nicht ableiten laesst. Gemeldet wird nur.
    """
    if not WERKSTOFFGRUPPEN[gruppe].get("items") or not items:
        return []

    werte = " ".join(f"wd:{e['qid']}" for e in items)
    resp = netz.get_with_retry(WIKIDATA_SPARQL, {"format": "json", "query": f"""
    SELECT DISTINCT ?i WHERE {{
      VALUES ?i {{ {werte} }}
      {{ ?i wdt:P31/wdt:P279* wd:{LEGIERUNG_QID} }} UNION
      {{ ?i wdt:P279* wd:{LEGIERUNG_QID} }}
    }}
    """})
    klassifiziert = {b["i"]["value"].rsplit("/", 1)[-1]
                     for b in resp.json()["results"]["bindings"]}
    fehlend = [e for e in items if e["qid"] not in klassifiziert]
    if fehlend:
        print(f"  {len(fehlend)} Items sind NICHT als Legierung (Q{LEGIERUNG_QID[1:]}) "
              f"klassifiziert - bitte fachlich pruefen, hier wird nichts "
              f"vorgeschlagen:", file=sys.stderr)
        for e in fehlend:
            basis = f" [Basis: {e['basis']}]" if e.get("basis") else ""
            print(f"    {e['qid']:<12}{e['label'][:34]:<36}{basis}",
                  file=sys.stderr)
    return []
