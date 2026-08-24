"""Die Wikipedia-Infoboxen: lesen, deuten, belegen.

Drei Vorlagen, drei Eigenheiten - {{Infobox Chemisches Element}},
{{Infobox Chemikalie}} und {{Chembox}}. Der Grossteil dieser Datei ist
Kleinarbeit an Zahl- und Markup-Schreibweisen; welche Fallstricke dahinter
stecken, steht im README ("Die drei Wikipedia-Stufen und ihre Fallstricke").

Belegt wird bevorzugt mit dem Einzelnachweis des Feldes (DOI oder ISBN),
sonst als Wikimedia-Import mit Permalink auf die Artikelversion.
"""

import collections
import re
import sys
from decimal import Decimal
from typing import Optional

import requests

from . import netz, wikidata
from .ausgabe import Reference, WIKIPEDIA_EN_QID, make_row, round_significant
from .properties import (
    AGGREGAT_FEST, AGGREGAT_FLUESSIG, AGGREGAT_GAS, AGGREGAT_PID,
    CELSIUS_QID, CHEMBOX_FIELDS, NUR_FESTKOERPER, PLAUSIBEL, PROPERTY_MAP,
    STANDARD_TEMPERATUR_C, TEMPERATUR_PID, WIKIPEDIA_DE_CHEM_FIELDS,
    WIKIPEDIA_DE_FIELDS, WIKIPEDIA_NUMERIC_FIELDS, ist_plausibel,
)

# ---------------------------------------------------------------------------
# Belege aus den Wikipedia-Einzelnachweisen ziehen
# ---------------------------------------------------------------------------
#
# Traegt ein Infobox-Wert einen eigenen <ref> mit DOI oder ISBN, wird der
# statt des Wikimedia-Imports gesetzt. Die zu behandelnden Schreibweisen -
# darunter die reine Wiederverwendung <ref name="..." />, deren Inhalt
# anderswo im Artikel steht - listet das README auf:
# "Die drei Wikipedia-Stufen und ihre Fallstricke".

_REF_TAG = re.compile(r"<ref([^>]*?)(?:/>|>(.*?)</ref>)", re.S | re.I)
_REF_NAME_ATTR = re.compile(r'name\s*=\s*"([^"]+)"|name\s*=\s*([^\s/>]+)', re.I)

_DOI_MUSTER = [
    re.compile(r"\[\[\s*doi:\s*(10\.\d{4,9}/[^\]\s|]+)", re.I),
    re.compile(r"\{\{\s*DOI\s*\|\s*(10\.\d{4,9}/[^}\s|]+)", re.I),
    re.compile(r"\|\s*DOI\s*=\s*(10\.\d{4,9}/[^|}\n]+)", re.I),
    re.compile(r"\bdoi:\s*(10\.\d{4,9}/[^\s,;\]}]+)", re.I),
]
_ISBN_MUSTER = [
    re.compile(r"\|\s*ISBN\s*=\s*([\d\-Xx]{10,17})", re.I),
    re.compile(r"\bISBN(?:-1[03])?[:\s=]\s*([\d\-Xx]{10,17})", re.I),
]


def _ref_name(attrs: str) -> Optional[str]:
    m = _REF_NAME_ATTR.search(attrs or "")
    return (m.group(1) or m.group(2)) if m else None


def ref_texts_for_field(raw: str, article_wikitext: str) -> list:
    """Volltexte aller Einzelnachweise eines Infobox-Feldes.

    Selbstschliessende <ref name="X" /> werden ueber ihren Namen im Artikel
    aufgeloest.
    """
    texts = []
    for m in _REF_TAG.finditer(raw or ""):
        attrs, inhalt = m.group(1), m.group(2)
        if inhalt:
            texts.append(inhalt)
            continue
        name = _ref_name(attrs)
        if not name:
            continue
        treffer = re.search(
            r'<ref[^>]*name\s*=\s*"?' + re.escape(name) + r'"?[^>/]*>(.*?)</ref>',
            article_wikitext or "", re.S | re.I,
        )
        if treffer:
            texts.append(treffer.group(1))
    return texts


def extract_ref_ids(raw: str, article_wikitext: str) -> dict:
    """{'doi': ..., 'isbn': ...} aus den Belegen eines Feldes.

    Nur EINDEUTIGE Treffer: nennen die Belege eines Feldes mehrere
    verschiedene DOIs bzw. ISBNs, laesst sich der Wert keiner davon sicher
    zuordnen - dann lieber der Import als ein falscher Literaturbeleg.
    """
    dois, isbns = [], []
    for text in ref_texts_for_field(raw, article_wikitext):
        for muster in _DOI_MUSTER:
            for treffer in muster.findall(text):
                dois.append(treffer.rstrip(" .,;)]}"))
        for muster in _ISBN_MUSTER:
            for treffer in muster.findall(text):
                ziffern = re.sub(r"[^\dXx]", "", treffer)
                if len(ziffern) in (10, 13):
                    isbns.append(treffer.strip(" -"))

    ids = {}
    if len(set(dois)) == 1:
        ids["doi"] = dois[0]
    if len(set(isbns)) == 1:
        ids["isbn"] = isbns[0]
    return ids


# ---------------------------------------------------------------------------
# Fallback-Quelle 1: Deutsche Wikipedia, {{Infobox Chemisches Element}}
# ---------------------------------------------------------------------------
#
# Die ergiebigste Quelle ueberhaupt: sie fuehrt als einzige P2056, P2055,
# P2075, P5593 und P231. Der Artikeltitel kommt aus dem Wikidata-Sitelink,
# NICHT aus dem Elementnamen geraten (Titan -> "Titan (Element)").
#
# Werte mit "<br" oder ":" nennen mehrere Modifikationen und werden VERWORFEN,
# sonst landete willkuerlich Graphit oder Diamant als "der" Wert des Elements.
# Die vollstaendige Liste der Zahl- und Markup-Eigenheiten, an denen sich die
# Parser unten abarbeiten, steht im README:
# "Die drei Wikipedia-Stufen und ihre Fallstricke".

WIKIPEDIA_DE_QID = "Q48183"  # deutschsprachige Wikipedia
WIKIPEDIA_DE_API = "https://de.wikipedia.org/w/api.php"


WIKIPEDIA_DE_CRYSTAL_KEYWORDS = [
    # Zentrierung zuerst: "kubisch flaechenzentriert" ist aussagekraeftiger
    # als "kubisch", und die allgemeine Regel wuerde sonst greifen. Die
    # Bindestrichvarianten kommen im Bestand beide vor.
    ("kubisch flächenzentriert", "fcc"),
    ("kubisch-flächenzentriert", "fcc"),
    ("kubisch raumzentriert", "bcc"),
    ("kubisch-raumzentriert", "bcc"),
    ("orthorhombisch", "orthorhombic"),
    ("rhombisch", "orthorhombic"),
    ("tetragonal", "tetragonal"),
    ("monoklin", "monoclinic"),
    ("triklin", "triclinic"),
    ("rhomboedrisch", "trigonal"),
    ("rhomboëdrisch", "trigonal"),
    ("trigonal", "trigonal"),
    ("hexagonal", "hexagonal"),
    ("kubisch", "cubic"),
]

# "58,1 · 10<sup>6</sup>" -> vor dem Tag-Strippen einfangen, sonst bleibt
# nur "58,1 6" uebrig und die Zehnerpotenz ginge verloren.
_DE_ZEHNERPOTENZ = re.compile(
    r"([\d.,]+)\s*[·⋅*x]\s*10\s*<sup>\s*([−–-]?\s*\d+)\s*</sup>", re.I
)
_DE_CASRN = re.compile(r"\{\{\s*CASRN\s*\|\s*([\d-]+)\s*\}\}", re.I)
_DE_HEDGE = re.compile(r"^(etwa|ca\.?|ungefähr|circa|rund|≈|~)\s*", re.I)
_DE_NUMBER = re.compile(r"^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")
# Einheiten, die hinter der Zahl stehen duerfen und abgetrennt werden.
# "g·cm-3" und "°C" kommen aus der Verbindungsinfobox (siehe unten), die
# Elementinfobox schreibt "g/cm³" bzw. gar keine Einheit.
_DE_UNIT = re.compile(
    r"\s*(g\s*/\s*cm\s*\^?\s*3|g/cm³|g\s*[·⋅*]\s*cm\s*\^?\s*-?\s*3"
    r"|kg\s*/\s*m\s*\^?\s*3|°\s*C|K|W|S/m|m/s|GPa|Pa)\s*$"
)


def parse_de_number(raw: str) -> Optional[float]:
    """Zahl aus einem deutschen Infobox-Feld, sonst None.

    Konservativ: mehrdeutige Felder (mehrere Modifikationen), Bereiche und
    alles mit Resttext werden verworfen statt interpretiert.
    """
    s = raw or ""
    if not s.strip():
        return None
    # Auskommentiertes zuerst weg (Kohlenstoff), dann Mehrdeutigkeit pruefen
    s = _WIKI_COMMENT.sub(" ", s)
    if "<br" in s.lower() or ":" in _WIKI_REF.sub(" ", s):
        return None  # mehrere Modifikationen / beschrifteter Wert

    # Zehnerpotenz normalisieren, bevor die Tags fallen
    s = _DE_ZEHNERPOTENZ.sub(
        lambda m: f"{m.group(1)}e{m.group(2).replace(' ', '').replace('−', '-').replace('–', '-')}",
        s,
    )
    s = strip_wiki_markup(s)
    s = re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r"\1", s)  # [[Kelvin|K]] -> K
    s = _DE_HEDGE.sub("", s.strip())
    if "±" in s:
        s = s.split("±")[0]  # "1812 ± 1 K" -> Hauptwert
    if "{{" in s or "…" in s or "–" in s:
        return None  # Restvorlage oder Bereich
    # Einheit und angehaengte Messbedingung "(20 °C)" abtragen, in
    # beliebiger Reihenfolge - beides kann am Ende stehen.
    s = s.strip()
    for _ in range(3):
        vorher = s
        s = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()
        s = _DE_UNIT.sub("", s).strip()
        if s == vorher:
            break

    if "," in s:  # deutsches Dezimalkomma, Punkt ist Tausendertrenner
        s = s.replace(".", "").replace(",", ".")
    if not _DE_NUMBER.match(s):
        return None
    return float(s)


def parse_de_cas(raw: str) -> Optional[str]:
    """CAS-Nummer aus {{CASRN|7440-50-8}}.

    Nur bei GENAU einer Nummer - manche Elemente listen je Modifikation
    eine eigene (Kohlenstoff: Graphit und Diamant), dann ist unklar, welche
    dem Element-Item zusteht. Ein blosses angehaengtes <br /> ist dagegen
    unschaedlich.
    """
    treffer = _DE_CASRN.findall(raw or "")
    return treffer[0] if len(treffer) == 1 else None



_DE_TEMP_K = re.compile(r"([+-]?[\d.,]+)\s*K(?![A-Za-z])")
_DE_TEMP_C = re.compile(r"([+-]?[\d.,]+)\s*°\s*C")
# Zersetzung/Sublimation ist kein Schmelzpunkt, "> 300" keine Zahl.
_DE_TEMP_UNSICHER = re.compile(r"zersetz|sublim|explod|[<>≤≥]", re.I)


def _de_zahl(roh: str) -> Optional[float]:
    """Deutsche Zahlschreibweise -> float ('1.234,5' -> 1234.5)."""
    s = (roh or "").strip()
    if "," in s:  # Dezimalkomma, Punkt ist Tausendertrenner
        s = s.replace(".", "").replace(",", ".")
    return float(s) if _DE_NUMBER.match(s) else None


def parse_de_temperature(raw: str) -> Optional[float]:
    """Temperatur aus der Verbindungsinfobox, umgerechnet in KELVIN.

    Die Einheit MUSS im Feld stehen: "1843" allein laesst offen, ob Grad
    Celsius oder Kelvin gemeint ist, und der Unterschied waere ein um 273,15
    danebenliegender Wert in Wikidata. Steht beides da ("1855 °C (2128 K)"),
    gewinnt Kelvin - dieser Wert geht ohne Umrechnung durch.

    Verworfen wird wie ueberall alles Mehrdeutige: mehrere Modifikationen,
    Bereiche, Zersetzungs- statt Schmelztemperaturen, Ungleichungen.
    """
    s = _WIKI_COMMENT.sub(" ", raw or "")
    if "<br" in s.lower() or ":" in _WIKI_REF.sub(" ", s):
        return None  # mehrere Modifikationen / beschrifteter Wert
    s = strip_wiki_markup(s)
    s = re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r"\1", s)  # [[Grad Celsius|°C]]
    s = _DE_HEDGE.sub("", s.strip())
    if "{{" in s or "…" in s or "–" in s or _DE_TEMP_UNSICHER.search(s):
        return None
    if "±" in s:
        s = s.split("±")[0]

    treffer = _DE_TEMP_K.search(s)
    if treffer:
        return _de_zahl(treffer.group(1))
    treffer = _DE_TEMP_C.search(s)
    if treffer:
        wert = _de_zahl(treffer.group(1))
        return None if wert is None else wert + 273.15
    return None


def wikipedia_de_chem_values(fields: dict, article_wikitext: str = "") -> dict:
    """{Schluessel: (wert, notiz, beleg_ids)} aus {{Infobox Chemikalie}}."""
    out = {}

    def merken(key, value, feld, note):
        out[key] = (value, note, extract_ref_ids(fields.get(feld, ""),
                                                 article_wikitext))

    for feld, (key, faktor) in WIKIPEDIA_DE_CHEM_FIELDS.items():
        value = parse_de_number(fields.get(feld, ""))
        if value is None:
            continue
        if key == "density" and not (0.01 <= value <= 30):
            continue  # g/cm^3 plausibel? sonst steht dort etwas anderes
        merken(key, value * faktor, feld, f"Infobox-Feld '{feld}'")

    for feld, key in (("Schmelzpunkt", "melting_point"),
                      ("Siedepunkt", "boiling_point")):
        kelvin = parse_de_temperature(fields.get(feld, ""))
        if kelvin is not None:
            merken(key, kelvin, feld, f"Infobox-Feld '{feld}' (in Kelvin)")

    cas = parse_de_cas(fields.get("CAS", ""))
    if cas:
        merken("cas_number", cas, "CAS", "Infobox-Feld 'CAS'")
    return out


def fetch_page_infobox(api: str, page: str, site: str):
    """(Felder, Permalink, Wikitext) einer beliebigen Wiki-Seite.

    Gemeinsame Basis fuer alle drei Faelle: deutscher Artikel (Element wie
    Verbindung), englische Elementvorlage und englischer Verbindungsartikel.

    Der volle Wikitext wird mitgegeben, weil benannte Einzelnachweise
    (<ref name="X" />) nur ueber den restlichen Artikel aufloesbar sind.
    Der Permalink zeigt auf die konkrete Version (oldid) - ein Beleg auf
    "die Seite" waere wertlos, sobald sie sich aendert.
    """
    resp = netz.request_with_retry("GET", api, params={
        "action": "parse", "page": page, "prop": "wikitext|revid",
        "format": "json", "formatversion": "2",
    })
    if resp.status_code != 200:
        return None, None, ""
    data = resp.json()
    if "error" in data:
        return None, None, ""
    parse = data["parse"]
    permalink = (
        f"{site}/w/index.php?title={page.replace(' ', '_')}"
        f"&oldid={parse.get('revid')}"
    )
    return parse_infobox_fields(parse["wikitext"]), permalink, parse["wikitext"]


def fetch_de_wikipedia_infobox(title: str):
    """(Felder, Permalink, Wikitext) der Infobox im deutschen Artikel."""
    return fetch_page_infobox(WIKIPEDIA_DE_API, title, "https://de.wikipedia.org")


def wikipedia_de_values(fields: dict, article_wikitext: str = "") -> dict:
    """{Schluessel: (wert, notiz, beleg_ids)} aus der deutschen Infobox."""
    out = {}

    def merken(key, value, feld, note):
        out[key] = (value, note, extract_ref_ids(fields.get(feld, ""),
                                                 article_wikitext))

    for feld, (key, faktor) in WIKIPEDIA_DE_FIELDS.items():
        value = parse_de_number(fields.get(feld, ""))
        if value is None:
            continue
        if key == "density" and not (0.01 <= value <= 30):
            continue  # g/cm^3 plausibel? sonst steht dort etwas anderes
        merken(key, value * faktor, feld, f"Infobox-Feld '{feld}'")

    cas = parse_de_cas(fields.get("CAS", ""))
    if cas:
        merken("cas_number", cas, "CAS", "Infobox-Feld 'CAS'")

    roh = fields.get("Kristallstruktur", "")
    if roh and "<br" not in roh.lower() and ":" not in _WIKI_REF.sub(" ", roh):
        # Wikilinks aufloesen, BEVOR nach Stichworten gesucht wird: Aluminium
        # schreibt "[[Kubisches Kristallsystem|kubisch]] flächenzentriert",
        # und die Klammern zerreissen die Phrase, nach der wir suchen.
        xtal = re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r"\1",
                      strip_wiki_markup(roh)).lower()
        for keyword, system in WIKIPEDIA_DE_CRYSTAL_KEYWORDS:
            if keyword in xtal:
                merken("crystal_system", system, "Kristallstruktur",
                       f"Infobox 'Kristallstruktur' = '{xtal}'")
                break
    return out


def wikipedia_de_proposals_for_item(wd_match: dict, de_title: str,
                                    skip_keys: set) -> list:
    """Vorschlaege aus der deutschen Wikipedia, als Import referenziert.

    Deckt beide Infoboxen ab: {{Infobox Chemisches Element}} bei Elementen,
    {{Infobox Chemikalie}} bei Verbindungen. Ein Artikel traegt nie beide -
    ein Abruf, beide Feldsaetze darauf angewendet. Die Elementinfobox hat
    Vorrang, weil sie mehr Groessen fuehrt und ihre Temperaturen bereits in
    Kelvin stehen.
    """
    if not de_title:
        return []
    fields, permalink, wikitext = fetch_de_wikipedia_infobox(de_title)
    if not fields:
        return []
    werte = wikipedia_de_values(fields, wikitext)
    for key, wert in wikipedia_de_chem_values(fields, wikitext).items():
        werte.setdefault(key, wert)
    return _infobox_proposals(
        wd_match, werte, skip_keys,
        "Wikipedia (de)", WIKIPEDIA_DE_QID, permalink,
        messtemperatur=parse_de_messtemperatur(fields.get("Dichte", "")),
    )


# Messtemperatur der Dichte, z. B. "8,96 g/cm³ (20 °C)". Sie steht in
# Klammern hinter dem Wert - die Elementinfoboxen sind darin uneinheitlich:
# Kupfer/Silber/Aluminium/Blei nennen 20 °C, Titan und Zink 25 °C, Eisen und
# Quecksilber gar nichts. Blind 20 °C anzunehmen waere also fuer einen Teil
# des Bestands schlicht falsch.
_DE_MESSTEMPERATUR = re.compile(r"\(\s*([+-]?[\d.,]+)\s*°\s*C\s*\)")


def parse_de_messtemperatur(raw: str) -> Optional[float]:
    """Messtemperatur aus einem Infobox-Feld in Grad Celsius, sonst None."""
    s = strip_wiki_markup(raw or "")
    s = re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r"\1", s)  # [[Grad Celsius|°C]]
    treffer = _DE_MESSTEMPERATUR.search(s)
    return _de_zahl(treffer.group(1)) if treffer else None


def aggregatzustand_bei(temperatur_c: float, werte: dict) -> Optional[str]:
    """QID des Aggregatzustands bei dieser Temperatur, sonst None.

    Abgeleitet aus Schmelz- und Siedepunkt DESSELBEN Artikels, beide in
    Kelvin. Fehlt einer der beiden, wird nichts behauptet - lieber kein
    Qualifikator als ein falscher.

    Noetig, weil "fest" gerade nicht immer stimmt: Quecksilber schmilzt bei
    234 K, seine Dichteangabe bei 20 °C meint also die FLUESSIGKEIT.
    """
    kelvin = temperatur_c + 273.15
    schmelz = werte.get("melting_point")
    if schmelz is None:
        return None
    if kelvin < schmelz[0]:
        return AGGREGAT_FEST
    siede = werte.get("boiling_point")
    if siede is None:
        return None  # oberhalb des Schmelzpunkts, aber fluessig oder gasfoermig?
    return AGGREGAT_FLUESSIG if kelvin < siede[0] else AGGREGAT_GAS


def dichte_qualifikatoren(temperatur_c: float, zustand_qid: Optional[str]) -> list:
    """Qualifikatoren fuer eine Dichteaussage: Temperatur, Aggregatzustand.

    Der Temperaturwert steht in QuickStatements-Schreibweise, also mit
    Einheit - "20U25267" ist 20 Grad Celsius (Q25267).
    """
    zahl = format(Decimal(str(temperatur_c)).normalize(), "f")
    qual = [(TEMPERATUR_PID, f"{zahl}U{CELSIUS_QID[1:]}",
             f"{zahl} °C")]
    if zustand_qid:
        klartext = {AGGREGAT_FEST: "fest", AGGREGAT_FLUESSIG: "fluessig",
                    AGGREGAT_GAS: "gasfoermig"}[zustand_qid]
        qual.append((AGGREGAT_PID, zustand_qid, klartext))
    return qual


def _infobox_proposals(wd_match, werte, skip_keys, quelle, projekt_qid,
                       permalink, messtemperatur=None) -> list:
    """Gemeinsame Zeilenerzeugung fuer beide Wikipedia-Sprachen.

    Der Beleg wird in dieser Reihenfolge gewaehlt: DOI aus dem
    Einzelnachweis, sonst ISBN daraus, sonst der Wikimedia-Import. Ein
    echter Literaturbeleg ist in Wikidata deutlich mehr wert als
    "importiert aus Wikipedia"; der Permalink bleibt in der Notiz erhalten,
    damit nachvollziehbar ist, woher der Wert stammt.
    """
    # Auch die Infoboxen fuehren Moduln, die aus der Festkoerperphase
    # stammen - siehe NUR_FESTKOERPER.
    gasfoermig = wikidata.ist_bei_raumtemperatur_gas(wd_match["qid"])
    proposals = []
    for key, (value, note, ids) in werte.items():
        if key in skip_keys:
            continue
        prop_info = PROPERTY_MAP.get(key)
        if prop_info is None:
            continue
        if gasfoermig and key in NUR_FESTKOERPER:
            continue
        if ids.get("doi"):
            reference = Reference(
                doi=ids["doi"], note=f"{note}, Beleg aus {quelle}: {permalink}"
            )
        elif ids.get("isbn"):
            reference = Reference(
                isbn=ids["isbn"], note=f"{note}, Beleg aus {quelle}: {permalink}"
            )
        else:
            reference = Reference(
                imported_from=projekt_qid, import_url=permalink, note=note
            )
        value_label = ""
        qualifiers = []
        if key == "density":
            # P2054 verlangt Temperatur und Aggregatzustand als Qualifikator.
            # Die Temperatur steht meist im Feld selbst; sonst 20 °C.
            temperatur = (messtemperatur if messtemperatur is not None
                          else STANDARD_TEMPERATUR_C)
            qualifiers = dichte_qualifikatoren(
                temperatur, aggregatzustand_bei(temperatur, werte))
        if prop_info.get("datatype") == "item":
            mapped = prop_info.get("value_map", {}).get(str(value))
            if mapped is None:
                proposals.append(make_row(
                    f"MANUELLE_KLAERUNG_NOETIG (Wert '{value}' nicht in "
                    f"value_map fuer {prop_info['pid']})",
                    quelle, wd_match, prop_info, value, "", reference,
                ))
                continue
            value, value_label = mapped
        elif prop_info.get("datatype") == "quantity":
            value = round_significant(value)
            # Was ausserhalb der Schranken liegt, wird nicht still verworfen,
            # sondern ausgewiesen - siehe PLAUSIBEL. Bei der Mohshaerte ist
            # das der Regelfall fuer die weichen Alkalimetalle (Caesium 0,2):
            # ein echter Wert, den P1088 wegen seines Bereichs-Constraints
            # trotzdem nicht annimmt. Das gehoert vor Augen, nicht in den
            # Papierkorb.
            if not ist_plausibel(key, value):
                untere, obere = PLAUSIBEL[key]
                proposals.append(make_row(
                    f"MANUELLE_KLAERUNG_NOETIG (unplausibler Wert {value:g}, "
                    f"erwartet {untere:g}..{obere:g} fuer {prop_info['pid']})",
                    quelle, wd_match, prop_info, value, "", reference,
                ))
                continue

        already_present = wikidata.item_has_statement(wd_match["qid"], prop_info["pid"])
        proposals.append(make_row(
            "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
            quelle, wd_match, prop_info, value, value_label, reference,
            qualifiers=qualifiers,
        ))
    return proposals


# ---------------------------------------------------------------------------
# Fallback-Quelle 2: Englische Wikipedia-Elementinfobox (Import-Referenz)
# ---------------------------------------------------------------------------
#
# Je Element eine Vorlage "Infobox <name>" (z. B. [[Template:Infobox copper]]).
# "melting point K" / "boiling point K" stehen bereits in Kelvin.
#
# Markup wird entfernt und anschliessend nur ein SAUBERER Zahlwert akzeptiert;
# alles mit Buchstaben, Bereich oder Restvorlage wird verworfen. Die realen
# Faelle, die das noetig machen: README, "Die drei Wikipedia-Stufen".

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


# "crystal structure" nennt das Bravais-Gitter bzw. den Strukturtyp, nicht
# das Kristallsystem. Schreibweisen schwanken ("face-centered cubic" vs.
# "face centered cubic"), deshalb wird normalisiert und nach Schluesselwort
# gesucht. Reihenfolge ist wichtig: spezifisch vor allgemein.
WIKIPEDIA_CRYSTAL_KEYWORDS = [
    # Zentrierung zuerst, aus demselben Grund wie in der deutschen Liste.
    # Ohne Bindestrich, weil die Auswertung "-" vorher durch " " ersetzt.
    ("face centered cubic", "fcc"),
    ("body centered cubic", "bcc"),
    ("orthorhombic", "orthorhombic"),
    ("tetragonal", "tetragonal"),
    ("monoclinic", "monoclinic"),
    ("triclinic", "triclinic"),
    ("rhombohedral", "trigonal"),  # rhomboedrisch gehoert zum trigonalen System
    ("trigonal", "trigonal"),
    ("hexagonal", "hexagonal"),
    ("cubic", "cubic"),
]

_WIKI_REF = re.compile(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_WIKI_TAG = re.compile(r"<[^>]+>")
_WIKI_COMMENT = re.compile(r"<!--.*?-->", re.S)
_WIKI_ENTITY = re.compile(r"&[a-z]+;|&#\d+;", re.I)
_WIKI_NUMBER = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
# SI-Praefixe des Feldes "electrical resistivity unit prefix"
_SI_PREFIX = {"n": 1e-9, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "": None,
              "k": 1e3, "M": 1e6, "G": 1e9}


def strip_wiki_markup(text: str) -> str:
    """Entfernt Refs, Tags, Kommentare und HTML-Entities aus einem Feldwert."""
    s = _WIKI_COMMENT.sub(" ", text or "")
    s = _WIKI_REF.sub(" ", s)
    s = _WIKI_TAG.sub(" ", s)
    s = _WIKI_ENTITY.sub(" ", s)
    s = s.replace("''", " ").replace("−", "-")  # Unicode-Minus
    return re.sub(r"\s+", " ", s).strip()


def parse_wiki_number(raw: str) -> Optional[float]:
    """Sauberer Zahlwert oder None.

    Bewusst streng: Restvorlagen ({{...}}), Bereiche und alles mit
    Buchstaben werden verworfen statt interpretiert.
    """
    s = strip_wiki_markup(raw)
    if not s or "{{" in s or "}}" in s:
        return None
    s = s.replace(",", "")
    # Bekannte Einheit hinter der Zahl abtrennen. Grosszuegig bei
    # Leerzeichen, weil "<sup>3</sup>" beim Strippen zu "g/cm 3" wird.
    s = re.sub(
        r"\s*(g\s*/\s*cm\s*\^?\s*3|kg\s*/\s*m\s*\^?\s*3)\s*$",
        "", s, flags=re.I,
    ).strip()
    if not _WIKI_NUMBER.match(s):
        return None
    return float(s)


def parse_infobox_fields(wikitext: str) -> dict:
    """{Feldname: Rohwert} aus dem Vorlagenaufruf."""
    fields = {}
    for m in re.finditer(r"^\|\s*([^=|\n]+?)\s*=(.*)$", wikitext, re.M):
        fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def fetch_wikipedia_infobox(element_name: str):
    """(Felder, Permalink, Wikitext) der Vorlage "Infobox <element>"."""
    return fetch_page_infobox(
        WIKIPEDIA_API, f"Template:Infobox {element_name.lower()}",
        "https://en.wikipedia.org",
    )


def wikipedia_values(fields: dict, article_wikitext: str = "") -> dict:
    """{Schluessel: (wert, notiz, beleg_ids)} aus den Infobox-Feldern."""
    out = {}

    def merken(key, value, feld, note):
        out[key] = (value, note, extract_ref_ids(fields.get(feld, ""),
                                                 article_wikitext))

    for feld, (key, faktor) in WIKIPEDIA_NUMERIC_FIELDS.items():
        value = parse_wiki_number(fields.get(feld, ""))
        if value is not None:
            merken(key, value * faktor, feld, f"Infobox-Feld '{feld}'")

    # Dichte steht konventionell in g/cm^3 - der Zieleinheit, siehe
    # PROPERTY_MAP. Nichts umzurechnen, nur zu pruefen.
    dichte = parse_wiki_number(fields.get("density", ""))
    if dichte is not None and 0.01 <= dichte <= 30:
        merken("density", dichte, "density",
               "Infobox-Feld 'density' (g/cm^3)")

    # Spezifischer Widerstand: Zahl + eigenes Praefix-Feld. Ohne bekanntes
    # Praefix wird nicht geraten (Silizium fuehrt dort nur eine Vorlage).
    rho = parse_wiki_number(fields.get("electrical resistivity at 20", ""))
    faktor = _SI_PREFIX.get(fields.get("electrical resistivity unit prefix", "").strip())
    if rho is not None and faktor:
        merken(
            "electrical_resistivity", rho * faktor,
            "electrical resistivity at 20",
            f"Infobox 'electrical resistivity at 20' mit Praefix "
            f"'{fields.get('electrical resistivity unit prefix')}'",
        )

    # Kristallstruktur -> Kristallsystem
    xtal = strip_wiki_markup(fields.get("crystal structure", "")).lower()
    xtal = xtal.replace("-", " ")
    if xtal:
        for keyword, system in WIKIPEDIA_CRYSTAL_KEYWORDS:
            if keyword in xtal:
                merken("crystal_system", system, "crystal structure",
                       f"Infobox 'crystal structure' = '{xtal}'")
                break
    return out


# ---------------------------------------------------------------------------
# Laengenausdehnungskoeffizient (P5672) aus der englischen Elementinfobox
# ---------------------------------------------------------------------------
#
# Die einzige Quelle im ganzen Werkzeug, die diese Groesse fuehrt - die
# deutsche Elementinfobox hat kein solches Feld, die Chembox auch nicht, und
# das Materials Project rechnet keine thermische Ausdehnung.
#
# Das Feld heisst "thermal expansion comment" und steht in der Form
#   {{val|16.64|e=−6}}/K (at&nbsp;20&nbsp;°C)<ref name="Arblaster 2018" />
# also 16,64 um/(m*K) mit ausdruecklicher Temperatur. Aeltere Vorlagen fuehren
# stattdessen "thermal expansion at 25" als blosse Zahl, die dort bereits in
# um/(m*K) steht.
#
# Wie weit das traegt, an allen 118 Elementvorlagen gemessen (2026-08-19):
# 38 isotrope Werte, 24 anisotrope, 11 unbrauchbare, 45 ohne Angabe. Warum die
# anisotropen NICHT vorgeschlagen werden: README.
_AUSDEHNUNG_VAL = re.compile(
    r"\{\{val\|([\d.]+)\|e=[−-]6(?:\|u=[^}]*)?\}\}\s*/?\s*K?\s*"
    r"\(at&nbsp;([\d.]+)&nbsp;°C\)"
)
# "The thermal expansion is anisotropic" - dann ist der genannte Wert das
# Mittel ueber die Achsen (alpha_V/3), nicht "der" Laengenkoeffizient.
_AUSDEHNUNG_ANISOTROP = re.compile(r"anisotrop", re.I)


def parse_thermal_expansion(fields: dict) -> Optional[tuple]:
    """(Wert in um/(m*K), Temperatur in °C, anisotrop) oder None.

    Verworfen wird alles, was die Temperatur nicht ausdruecklich nennt
    ("at r.t.") oder sich auf eine Modifikation bezieht ("diamond: 0.8",
    "beta form: 5-7") - beides kommt real vor und waere geraten.
    """
    kommentar = fields.get("thermal expansion comment", "")
    treffer = _AUSDEHNUNG_VAL.search(kommentar)
    if treffer:
        return (float(treffer.group(1)), float(treffer.group(2)),
                bool(_AUSDEHNUNG_ANISOTROP.search(kommentar)))
    if kommentar:
        return None  # Kommentar da, aber ohne verwertbare Zahl-Temperatur

    # Aeltere Vorlagen: Zahl in um/(m*K), Temperatur steckt im Feldnamen.
    roh = fields.get("thermal expansion at 25", "").strip()
    if re.fullmatch(r"[\d.]+", roh):
        return float(roh), 25.0, False
    return None


def waermeausdehnung_proposals_for_item(wd_match: dict, fields: dict,
                                        permalink: str, wikitext: str,
                                        skip_keys: set) -> list:
    """P5672-Vorschlag aus der englischen Elementinfobox.

    Eigene Stufe statt eines Eintrags in WIKIPEDIA_NUMERIC_FIELDS: die
    Groesse braucht eine Temperatur als Qualifikator, und die anisotropen
    Faelle brauchen einen Klaerungsvermerk. Beides passt nicht in die
    generische Feldabbildung.
    """
    prop_info = PROPERTY_MAP["linear_thermal_expansion"]
    if "linear_thermal_expansion" in skip_keys:
        return []
    if wikidata.ist_bei_raumtemperatur_gas(wd_match["qid"]):
        return []  # siehe NUR_FESTKOERPER - der Wert waere der des Feststoffs
    gemessen = parse_thermal_expansion(fields)
    if gemessen is None:
        return []
    wert, temperatur_c, anisotrop = gemessen
    if not ist_plausibel("linear_thermal_expansion", wert):
        return []

    feld = ("thermal expansion comment"
            if fields.get("thermal expansion comment") else
            "thermal expansion at 25")
    ids = extract_ref_ids(fields.get(feld, ""), wikitext)
    note = f"Infobox-Feld '{feld}' ({wert} um/(m*K) bei {temperatur_c:g} °C)"
    if ids.get("doi"):
        reference = Reference(doi=ids["doi"],
                              note=f"{note}, Beleg aus Wikipedia (en): {permalink}")
    elif ids.get("isbn"):
        reference = Reference(isbn=ids["isbn"],
                              note=f"{note}, Beleg aus Wikipedia (en): {permalink}")
    else:
        reference = Reference(imported_from=WIKIPEDIA_EN_QID,
                              import_url=permalink, note=note)

    zahl = format(Decimal(str(temperatur_c)).normalize(), "f")
    qualifiers = [(TEMPERATUR_PID, f"{zahl}U{CELSIUS_QID[1:]}", f"{zahl} °C")]

    if anisotrop:
        # Bei anisotropen Kristallen haengt der Koeffizient von der
        # Kristallachse ab; die Infobox nennt das Mittel alpha_V/3 und die
        # Achsenwerte in einer Fussnote. Ein einzelner Wert ohne Achsenangabe
        # waere in Wikidata eine Halbwahrheit - das entscheidet niemand
        # nebenbei.
        return [make_row(
            f"MANUELLE_KLAERUNG_NOETIG (anisotrope Ausdehnung: {wert} "
            f"um/(m*K) ist das Mittel alpha_V/3, die Achsenwerte stehen in "
            f"der Fussnote der Infobox)",
            "Wikipedia (en)", wd_match, prop_info, round_significant(wert), "",
            reference, entry_id="waermeausdehnung", qualifiers=qualifiers,
        )]

    vorhanden = wikidata.item_has_statement(wd_match["qid"], prop_info["pid"])
    return [make_row(
        "BEREITS_VORHANDEN" if vorhanden else "VORSCHLAG",
        "Wikipedia (en)", wd_match, prop_info, round_significant(wert), "",
        reference, entry_id="waermeausdehnung", qualifiers=qualifiers,
    )]


def wikipedia_proposals_for_item(wd_match: dict, name_en: str,
                                 skip_keys: set) -> list:
    """Vorschlaege aus der englischen Elementinfobox, als Import referenziert."""
    fields, permalink, wikitext = fetch_wikipedia_infobox(name_en)
    if not fields:
        return []
    zeilen = _infobox_proposals(
        wd_match, wikipedia_values(fields, wikitext), skip_keys,
        "Wikipedia (en)", WIKIPEDIA_EN_QID, permalink,
        messtemperatur=parse_de_messtemperatur(fields.get("density", "")),
    )
    return zeilen + waermeausdehnung_proposals_for_item(
        wd_match, fields, permalink, wikitext, skip_keys)


# ---------------------------------------------------------------------------
# Fallback-Quelle 3: {{Chembox}} der englischen Wikipedia (Verbindungen)
# ---------------------------------------------------------------------------
#
# Die Chembox steht im Artikel selbst. Die Einheit steckt im FELDNAMEN
# (MeltingPtC vs. MeltingPtK), es muss also nichts geraten werden. Reihenfolge
# im Mapping: Kelvin-Felder vor Celsius-Feldern, damit der Wert ohne
# Umrechnung gewinnt, wenn die Box beide fuehrt.


_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def wikipedia_en_chem_values(fields: dict, article_wikitext: str = "") -> dict:
    """{Schluessel: (wert, notiz, beleg_ids)} aus der {{Chembox}}."""
    out = {}

    def merken(key, value, feld, note):
        if key not in out:  # erstes passendes Feld gewinnt (K vor C)
            out[key] = (value, note, extract_ref_ids(fields.get(feld, ""),
                                                     article_wikitext))

    for feld, (key, faktor, offset) in CHEMBOX_FIELDS.items():
        value = parse_wiki_number(fields.get(feld, ""))
        if value is None:
            continue
        if key == "density" and not (0.01 <= value <= 30):
            continue  # g/cm^3 plausibel? sonst steht dort etwas anderes
        einheit = " (in Kelvin)" if offset else ""
        merken(key, value * faktor + offset, feld,
               f"Chembox-Feld '{feld}'{einheit}")

    cas = strip_wiki_markup(fields.get("CASNo", ""))
    if _CAS_RE.match(cas):
        merken("cas_number", cas, "CASNo", "Chembox-Feld 'CASNo'")
    return out


def wikipedia_en_chem_proposals_for_item(wd_match: dict, en_title: str,
                                         skip_keys: set) -> list:
    """Vorschlaege aus der englischen Chembox, als Import referenziert."""
    if not en_title:
        return []
    fields, permalink, wikitext = fetch_page_infobox(
        WIKIPEDIA_API, en_title, "https://en.wikipedia.org")
    if not fields:
        return []
    return _infobox_proposals(
        wd_match, wikipedia_en_chem_values(fields, wikitext), skip_keys,
        "Wikipedia (en)", WIKIPEDIA_EN_QID, permalink,
        messtemperatur=parse_de_messtemperatur(fields.get("Density", "")),
    )


def wikipedia_fallback_proposals(wd_match: dict, pids_belegt: set,
                                 de_title: str = "", en_element: str = "",
                                 en_title: str = ""):
    """Die Wikipedia-Stufen der Quellenkaskade - fuer BEIDE Modi dieselbe.

    Jede Stufe liefert nur, was die vorherigen nicht schon belegt haben;
    `pids_belegt` waechst dabei mit. Deutsch vor Englisch, weil die deutsche
    Infobox mehr Groessen fuehrt (u. a. spezifische Waermekapazitaet,
    elektrische Leitfaehigkeit, Schallgeschwindigkeit, CAS-Nummer).

    Zurueck kommen (Zeilen, Zaehler je Stufe).
    """
    zeilen, zaehler = [], collections.Counter()

    def offene_schluessel():
        # Schluessel statt PIDs vergleichen - uebersprungen wird nur, was
        # eine hoeherwertige Quelle wirklich geliefert hat.
        return {k for k, v in PROPERTY_MAP.items() if v["pid"] in pids_belegt}

    def stufe(name, rows):
        for proposal in rows:
            pids_belegt.add(proposal["_pid"])
            zeilen.append(proposal)
            zaehler[name] += 1

    if de_title:
        stufe("de.wp", wikipedia_de_proposals_for_item(
            wd_match, de_title, offene_schluessel()))
    if en_element:
        stufe("en.wp", wikipedia_proposals_for_item(
            wd_match, en_element, offene_schluessel()))
    if en_title:
        stufe("en.wp", wikipedia_en_chem_proposals_for_item(
            wd_match, en_title, offene_schluessel()))
    return zeilen, zaehler
