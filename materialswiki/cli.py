"""
Materials Project -> Wikidata: Vorschlagsgenerator (nur bestehende Items)
=========================================================================

Zweck
-----
Dieses Skript erstellt KEINE neuen Wikidata-Items und schreibt auch nichts
automatisch in Wikidata. Es:

  1. holt Materialdaten aus dem Materials Project (next-gen API),
  2. gleicht die Materialformel gegen bestehende Wikidata-Items ab
     (Property P274 "chemical formula") - nicht als Stringvergleich, sondern
     über die Zusammensetzung, siehe Abschnitt "Formel-Normalisierung",
  3. prüft, ob das jeweilige Statement dort schon existiert,
  4. schreibt alle Kandidaten als CSV-"Vorschlagsliste" zur manuellen Prüfung,
     plus einen QuickStatements-Entwurf. Dort steht nur der Status
     "VORSCHLAG" als ausführbare Zeile; "BEREITS_VORHANDEN" und
     "MANUELLE_KLAERUNG_NOETIG" stehen in eigenen, durchgehend
     auskommentierten Abschnitten - sichtbar, aber nicht einspielbar.

Warum Materials Project und nicht mehr NOMAD
---------------------------------------------
NOMAD lieferte wenige und in der Einzelprüfung nicht belastbare Werte. Der
Grund ist strukturell: NOMAD sammelt EINZELNE Rechnungen, ohne Aussage
darüber, ob das gerechnete Material real existiert oder überhaupt stabil ist.
Das Materials Project pflegt dagegen kuratierte Materialdokumente und macht
genau diese Einordnung über die API abfragbar:

    theoretical=false     nur Materialien mit experimentellem Nachweis
                          (in aller Regel ICSD-hinterlegt)
    is_stable=true        auf der konvexen Hülle, also thermodynamisch stabil
    deprecated=false      keine zurückgezogenen Dokumente

Alle drei Filter sind hier standardmäßig aktiv (abschaltbar, siehe --help).
Damit fällt genau das weg, was die NOMAD-Ausbeute unbrauchbar machte:
hypothetische Strukturen, instabile Phasen und Rechenartefakte.

Dazu kommt: Ein Material-Dokument enthält alle Größen auf einmal. NOMAD
brauchte je Eintrag einen zweiten Archiv-Abruf, hier genügt eine Anfrage.

Quellenkaskade (in beiden Modi dieselbe, jede Stufe nur für das, was die
vorherige nicht geliefert hat):

    Materials Project (DOI)  ->  de.wikipedia (Import)  ->  en.wikipedia

Die Wikipedia-Stufen sind standardmäßig AN und lassen sich mit
--no-wikipedia abschalten. Welche Infobox gelesen wird, entscheidet sich am
Artikel: {{Infobox Chemisches Element}} bzw. {{Infobox Chemikalie}} im
Deutschen, Template:Infobox <element> bzw. {{Chembox}} im Englischen.

WICHTIG - vor dem Einsatz
--------------------------
- MP_API_KEY: die Materials-Project-API verlangt einen Schlüssel, ohne ihn
  antwortet jeder Endpunkt mit HTTP 401. Kostenlos unter
  https://next-gen.materialsproject.org/api - dann als Umgebungsvariable
  setzen:  export MP_API_KEY="..."
  Bewusst NICHT im Quelltext hinterlegen; ein Schlüssel im Repo wäre ein
  Leck, sobald das Repo geteilt wird.
- USER_AGENT: gemäß Wikidata-Richtlinie mit echtem Namen/Kontakt ausfüllen
  (https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
- MP_FIELD_MAP: Feldnamen und Einheiten stammen aus dem öffentlichen
  OpenAPI-Schema (https://api.materialsproject.org/openapi.json, ausgewertet
  am 2026-08-15). Ändert sich das Schema, hier nachziehen.
- PROPERTY_MAP: nur Properties eintragen, deren P-Nummer auf
  https://www.wikidata.org/wiki/Property:Pxxxx tatsächlich existiert und zum
  Datentyp passt.

  Achtung: Ein Eintrag in PROPERTY_MAP allein erzeugt noch keine Vorschläge.
  Vorschläge entstehen nur für Schlüssel, die auch in MP_FIELD_MAP einen
  Pfad haben - alles Übrige muss aus der Wikipedia kommen.

Ablauf in der Praxis
---------------------
  export MP_API_KEY="..."
  python -m materialswiki --elements Ti O --max 50
  -> erzeugt vorschlaege_<Zeitstempel>.csv zur manuellen Durchsicht
  -> NICHTS wird automatisch nach Wikidata geschrieben

Der Zeitstempel steckt im Dateinamen, damit kein Lauf den vorherigen
überschreibt. Wer feste Namen will, setzt --out/--qs-out; dann wird der alte
QuickStatements-Entwurf vor dem Lauf geleert.
"""

import argparse
import collections
import csv
import datetime as dt
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests

# konfig.py liegt im Repo-Wurzelverzeichnis, eine Ebene ueber diesem Paket.
# Der Pfad wird ergaenzt, damit der Import auch beim direkten Aufruf
# (python materialswiki/cli.py) und aus fremden Arbeitsverzeichnissen greift.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import konfig  # noqa: E402

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Kontaktadresse und Schluessel kommen aus .env im Repo-Wurzelverzeichnis
# (Vorlage: .env.beispiel). Diese Datei ist gitignoriert - so steht kein
# Zugangsdatum im Quelltext und damit auch keines auf GitHub.
CONTACT_EMAIL = konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")
CONTACT = f"mailto:{CONTACT_EMAIL}"

# Zwei Kennungen, weil die beiden Gegenstellen Gegensaetzliches verlangen:
#
#   Wikimedia  verlangt laut User-Agent-Richtlinie eine sprechende Kennung
#              mit Kontakt; "Bot" im Namen ist dort ueblich und erwuenscht.
#   Materials  blockt genau das. Am Bestand geprueft (2026-08-15): mit
#   Project    "MaterialsWikidataSuggestBot/0.1" antwortet die API HTTP 403
#              "Forbidden", obwohl der Schluessel gueltig ist - und zwar
#              BEVOR sie den Schluessel prueft. Ausschlaggebend ist allein
#              das Wort "Bot": "SomethingBot/1.0" -> 403, dieselbe Kennung
#              ohne "Bot" -> 200. Kontaktangaben stoeren nicht,
#              "materialswiki/0.1 (mailto:...)" geht durch.
#
# Ein gemeinsamer User-Agent kann beide Anforderungen nicht erfuellen.
USER_AGENT = f"MaterialsWikidataSuggestBot/0.1 ({CONTACT})"
MP_USER_AGENT = f"materialswiki/0.1 ({CONTACT})"

HEADERS = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}

MP_API = "https://api.materialsproject.org"
# Die API verlangt einen Schluessel; ohne ihn antwortet jeder Endpunkt mit
# HTTP 401. Aus .env bzw. der Umgebung statt aus dem Quelltext - ein
# Schluessel im Repo waere ein Leck, sobald das Repo geteilt wird.
MP_API_KEY = konfig.wert("MP_API_KEY")

# Einzelne MP-Materialien haben keine eigene DOI. Belegt wird deshalb mit der
# Referenzpublikation der Datenbank; welches Material gemeint ist, steht als
# mp-ID in der Notiz und in der Belegspalte der CSV.
MP_DOI = "10.1063/1.4812323"  # Jain et al. 2013, APL Materials 1, 011002

# Groesste Seite, die die API ausliefert (Feld meta.max_limit in jeder
# Antwort, geprueft am 2026-08-15). Groessere Mengen kommen ueber _skip.
MP_MAX_LIMIT = 1000

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

REQUEST_DELAY_SEC = 1.0  # höflich sein, Rate Limits respektieren

# MP-Feldpfad -> (interner Schluessel, Faktor auf die Wikidata-Einheit).
# Feldnamen und Einheiten aus dem oeffentlichen OpenAPI-Schema
# (https://api.materialsproject.org/openapi.json, SummaryDoc, 69 Felder,
# ausgewertet am 2026-08-15). Die Faktoren sind der eigentliche Knackpunkt:
# MP liefert die Dichte in g/cm^3 und die Moduln in GPa, Wikidata erwartet
# kg/m^3 und Pascal.
MP_FIELD_MAP = {
    "density": ("density", 1000.0),                    # g/cm^3  -> kg/m^3
    "symmetry.crystal_system": ("crystal_system", None),  # itemwertig
    "bulk_modulus.vrh": ("bulk_modulus", 1e9),         # GPa     -> Pa
    "shear_modulus.vrh": ("shear_modulus", 1e9),       # GPa     -> Pa
    "homogeneous_poisson": ("poisson_ratio", 1.0),     # dimensionslos
    #
    # ABGLEICH gegen benchmark/properties_snapshot.json (58 Properties aus den
    # Abschnitten Physics/Mechanical/Thermal/Chemical/Electric and Magnetic der
    # Seite [[Wikidata:WikiProject Materials/Properties]]):
    # Materials Project deckt FUENF davon ab - eine mehr als NOMAD, das die
    # Poissonzahl nicht als Skalar fuehrte. Die Moduln kommen hier ausserdem
    # direkt als Voigt-Reuss-Hill-Mittel (Feld "vrh"), waehrend NOMAD eine
    # Liste von Mittelungsverfahren lieferte, aus der erst ausgewaehlt werden
    # musste.
    #
    # Bewusst NICHT uebernommen, obwohl MP es fuehrt:
    #
    #   band_gap (eV)  Wikidata hat KEINE Property dafuer. Es gibt zwei
    #     passende Items, beide als Praedikat unbrauchbar - an der mittleren
    #     Stelle einer Aussage steht zwingend eine P-Nummer:
    #       Q806352     "Bandluecke"          - Konzept (Energiebereich)
    #       Q103982939  "Bandlueckenenergie"  - physikalische Groesse
    #     Geprueft am 2026-08-13: keines der beiden hat P1687, keine Property
    #     traegt P1629 darauf, ein Sweep ueber alle quantity-Properties auf
    #     band/gap/semiconduct liefert nur P2911 "time gap" und P9279
    #     "Egapro", und auch Silizium (Q670) und Galliumarsenid (Q147395)
    #     fuehren keine solche Aussage. Der saubere Weg waere ein
    #     Property-Proposal mit P1629 -> Q103982939.
    #
    #   e_total, n, e_ij_max, weighted_work_function, total_magnetization:
    #     rechnerische Groessen ohne etablierte Wikidata-Property bzw. ohne
    #     eindeutigen Bezug zum Stoff statt zur gerechneten Zelle.
    #
    # Waerme- und elektrische Leitfaehigkeit (P2068 / P2055) stehen in
    # PROPERTY_MAP, haben hier aber keinen Pfad: MP fuehrt beide nicht. Sie
    # koennen nur aus der Wikipedia-Infobox kommen.
}

# Groessen, die MP zwar liefert, die aber nur der Qualitaetsbewertung dienen
# und nie zu einer Aussage werden. Sie landen als Kontext in der CSV.
MP_META_FIELDS = ("material_id", "formula_pretty", "theoretical", "is_stable",
                  "energy_above_hull", "database_IDs")

# ---------------------------------------------------------------------------
# Bestimmungsmethode: gerechnete Werte als solche kennzeichnen
# ---------------------------------------------------------------------------
#
# MP-Werte sind DFT-Rechnungen bei 0 K am idealen Einkristall, keine
# Messungen. Am Bestand geprueft (2026-08-15, Cu/Fe/Ti): Kristallsystem
# exakt, Dichte 0,4-3,6 % daneben, aber Schubmodul bis +41 % (Titan 62 statt
# 44 GPa) und Poissonzahl bis 22 % (Eisen 0,353 statt 0,29 - magnetisch, fuer
# DFT ein bekannt schwieriger Fall).
#
# Eine solche Zahl ohne Kennzeichnung ans Wikidata-Item eines Werkstoffs zu
# haengen, waere irrefuehrend: Leser erwarten dort den gemessenen Wert.
# Deshalb traegt jede gerechnete Aussage den Qualifikator
#
#     P459 "Bestimmungsmethode oder -standard"  ->  Q1048589
#
# Verifiziert am 2026-08-15:
#   - P459 ist itemwertig (WikibaseItem)
#   - der Property-Scope-Constraint von P459 nennt ausdruecklich
#     "als Qualifikator" (Q54828449) - die Verwendung ist also vorgesehen
#   - Q1048589 = "density functional theory", laut Beschreibung
#     "computational quantum mechanical modelling method to investigate the
#     electronic structure", P31/P279: algorithm, computational chemistry,
#     computational physics. Das ist die Elektronenstruktur-DFT, die MP
#     rechnet - NICHT Q1209474, ein labelloser Stub gleichen Namens
#     (klassische DFT der statistischen Mechanik).
#
# Werte aus den Wikipedia-Infoboxen bekommen bewusst KEINEN Qualifikator:
# das sind Literaturwerte, und mit welcher Methode sie bestimmt wurden,
# steht dort nicht - eine Methode zu behaupten waere geraten.
DETERMINATION_PID = "P459"
DFT_QID = "Q1048589"
DFT_LABEL = "Dichtefunktionaltheorie"

# MP schreibt das Kristallsystem gross ("Tetragonal"), die value_map unten
# klein. Verglichen wird deshalb in Kleinschreibung; das Vokabular ist
# ansonsten identisch (dieselben sieben Systeme).

# Interner Schlüssel -> (Wikidata-Property, Datentyp, Einheit-QID, Beschreibung)
# NUR mit auf wikidata.org verifizierten Properties befüllen!
#
# "datatype" muss zum Wikidata-Datentyp der Property passen:
#   "quantity" -> Zahlwert + unit_qid
#   "item"     -> QID-Wert; "value_map" uebersetzt den NOMAD-String in ein QID.
#                 Werte ausserhalb der value_map werden NICHT geraten, sondern
#                 zur manuellen Klaerung markiert.
PROPERTY_MAP = {
    "density": {
        "pid": "P2054",
        "datatype": "quantity",
        "unit_qid": "Q844211",  # Kilogramm pro Kubikmeter, kg/m^3
        "label": "Dichte",
    },
    "melting_point": {
        "pid": "P2101",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin
        "label": "Schmelzpunkt",
    },
    "boiling_point": {
        "pid": "P2102",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin
        "label": "Siedepunkt",
    },
    # P556 ist item-wertig. Die sieben QIDs sind nicht geraten, sondern die
    # tatsaechlich in Wikidata verwendeten P556-Werte (per SPARQL nach
    # Haeufigkeit abgefragt, 2026-08-13). NOMADs crystal_system-Vokabular
    # (results.material.symmetry.crystal_system) hat genau dieselben sieben
    # Auspraegungen - die Abbildung ist damit 1:1 und vollstaendig.
    "crystal_system": {
        "pid": "P556",
        "datatype": "item",
        "unit_qid": "",
        "label": "Kristallsystem",
        "value_map": {
            "cubic": ("Q473227", "kubisches Kristallsystem"),
            "hexagonal": ("Q663314", "hexagonales Kristallsystem"),
            "monoclinic": ("Q624543", "monoklines Kristallsystem"),
            "orthorhombic": ("Q648961", "orthorhombisches Kristallsystem"),
            "tetragonal": ("Q503601", "tetragonales Kristallsystem"),
            "triclinic": ("Q376927", "triklines Kristallsystem"),
            "trigonal": ("Q588274", "trigonales Kristallsystem"),
        },
    },
    # Elastische Moduln. MP fuehrt sie als Objekt mit voigt/reuss/vrh;
    # genommen wird das Voigt-Reuss-Hill-Mittel (Pfad "...vrh" in
    # MP_FIELD_MAP), das uebliche Mittel fuer polykristalline Werkstoffe.
    # MP rechnet in GPa, Wikidata will Pascal - Faktor steht in MP_FIELD_MAP.
    "bulk_modulus": {
        "pid": "P5668",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal
        "label": "Kompressionsmodul",
    },
    "shear_modulus": {
        "pid": "P5673",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal
        "label": "Schubmodul",
    },
    "thermal_conductivity": {
        "pid": "P2068",
        "datatype": "quantity",
        "unit_qid": "Q1463969",  # Watt pro Meter-Kelvin, W/(m*K)
        "label": "Waermeleitfaehigkeit",
    },
    "electrical_conductivity": {
        "pid": "P2055",
        "datatype": "quantity",
        "unit_qid": "Q80842107",  # Siemens pro Meter, S/m
        "label": "Elektrische Leitfaehigkeit",
    },
    # Aus der Wikipedia-Infobox kommt der spezifische Widerstand direkt;
    # er wird als solcher uebernommen und NICHT zur Leitfaehigkeit
    # umgerechnet - so steht in der Aussage, was die Quelle wirklich sagt.
    "electrical_resistivity": {
        "pid": "P5679",
        "datatype": "quantity",
        "unit_qid": "Q1441459",  # Ohm-Meter, Ohm*m
        "label": "Spezifischer Widerstand",
    },
    # Spezifische Waermekapazitaet - kein NOMAD-Pfad (dort nur eine Kurve),
    # aber die deutsche Wikipedia fuehrt sie als Skalar in J/(kg*K).
    "specific_heat_capacity": {
        "pid": "P2056",
        "datatype": "quantity",
        "unit_qid": "Q3085309",  # Joule pro Kilogramm-Kelvin, J/(kg*K)
        "label": "Spezifische Waermekapazitaet",
    },
    "speed_of_sound": {
        "pid": "P2075",
        "datatype": "quantity",
        "unit_qid": "Q182429",  # Meter pro Sekunde, m/s
        "label": "Schallgeschwindigkeit",
    },
    "poisson_ratio": {
        "pid": "P5593",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos
        "label": "Poissonzahl",
    },
    # CAS-Nummer: Datentyp external-id, also eine Zeichenkette ohne Einheit.
    # Q102507 ("CAS-Nummer") traegt P1687 -> P231; das ist die Property.
    "cas_number": {
        "pid": "P231",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "CAS-Nummer",
    },
}


# ---------------------------------------------------------------------------
# Referenz-Modell: DOI bevorzugt, sonst Referenz-URL + Abrufdatum
# ---------------------------------------------------------------------------

WIKIPEDIA_EN_QID = "Q328"  # englischsprachige Wikipedia


class Reference:
    """Belegt einen Wert. Drei Arten, in absteigender Belastbarkeit:

      DOI      -> S356                                 (stabil, zitierfaehig)
      Import   -> S143 <Projekt-QID> + S4656 <URL>     (Wikimedia-Import)
      URL      -> S854 + S813 (abgerufen am)           (Notnagel)

    P143 "importiert aus Wikimedia-Projekt" zusammen mit P4656
    "Wikimedia-Import-URL" ist die vorgesehene Form fuer aus einer Wikipedia
    uebernommene Werte. Als Import-URL wird ein Permalink auf die konkrete
    Version (oldid) gesetzt - sonst zeigt der Beleg auf eine Seite, die sich
    nach dem Import beliebig geaendert haben kann.
    """

    def __init__(self, doi=None, isbn=None, url=None, imported_from=None,
                 import_url=None, retrieved=None, note=""):
        if not any((doi, isbn, url, import_url)):
            raise ValueError("Reference braucht doi, isbn, url oder import_url")
        self.doi = doi
        self.isbn = isbn
        self.url = url
        self.imported_from = imported_from
        self.import_url = import_url
        self.retrieved = retrieved or dt.date.today().isoformat()
        self.note = note

    @property
    def isbn_pid(self) -> str:
        """P212 fuer ISBN-13, P957 fuer ISBN-10 - anhand der Ziffernzahl."""
        ziffern = re.sub(r"[^\dXx]", "", self.isbn or "")
        return "P212" if len(ziffern) == 13 else "P957"

    @property
    def mode(self) -> str:
        if self.doi:
            return "DOI"
        if self.isbn:
            return "ISBN-13" if self.isbn_pid == "P212" else "ISBN-10"
        if self.import_url:
            return "Wikimedia-Import"
        return "URL+Datum"

    def as_csv_fields(self) -> dict:
        return {
            "ref_mode": self.mode,
            "ref_doi": self.doi or "",
            "ref_isbn": self.isbn or "",
            "ref_url": (
                self.url
                or self.import_url
                or (f"https://doi.org/{self.doi}" if self.doi else "")
            ),
            # Abrufdatum nur wo noetig - DOI und ISBN sind stabil.
            "ref_retrieved": "" if (self.doi or self.isbn) else self.retrieved,
            "ref_note": self.note,
        }

    def as_quickstatements(self) -> str:
        if self.doi:
            return f'\tS356\t"{self.doi}"'
        if self.isbn:
            return f'\t{self.isbn_pid.replace("P", "S")}\t"{self.isbn}"'
        if self.import_url:
            return (
                f"\tS143\t{self.imported_from}"
                f'\tS4656\t"{self.import_url}"'
                f"\tS813\t+{self.retrieved}T00:00:00Z/11"
            )
        return f'\tS854\t"{self.url}"\tS813\t+{self.retrieved}T00:00:00Z/11'


# ---------------------------------------------------------------------------
# Schritt 1: Materialien aus dem Materials Project holen
# ---------------------------------------------------------------------------

class MissingApiKey(RuntimeError):
    """Kein MP_API_KEY gesetzt - ohne Schluessel antwortet die API mit 401."""


def mp_headers() -> dict:
    if not MP_API_KEY:
        raise MissingApiKey(
            konfig.fehlt_hinweis("MP_API_KEY")
            + "\nSchluessel kostenlos unter "
            "https://next-gen.materialsproject.org/api"
        )
    # User-Agent bewusst ueberschreiben - siehe Kommentar bei MP_USER_AGENT.
    return {**HEADERS, "User-Agent": MP_USER_AGENT, "X-API-KEY": MP_API_KEY}


def fetch_mp_materials(
    elements: Optional[list],
    max_entries: int = 50,
    pure_element: Optional[str] = None,
    nur_experimentell: bool = True,
    nur_stabil: bool = True,
) -> list:
    """Fragt den summary-Endpunkt des Materials Project ab.

    Anders als bei NOMAD genuegt EIN Aufruf: das Material-Dokument enthaelt
    Formel, Symmetrie und alle Kennwerte zugleich. Zurueck kommt eine Liste
    von dicts mit formula, material_id, den Metafeldern und den Rohwerten.

    Die drei Qualitaetsfilter sind der eigentliche Gewinn gegenueber NOMAD:

      nur_experimentell  theoretical=false - das Material ist experimentell
                         nachgewiesen (in aller Regel ICSD-hinterlegt) und
                         nicht bloss durchgerechnet.
      nur_stabil         is_stable=true - liegt auf der konvexen Huelle, ist
                         also thermodynamisch stabil und keine Phase, die es
                         so gar nicht gibt.
      (immer)            deprecated=false - keine zurueckgezogenen Dokumente.

    pure_element schraenkt auf den REINEN Stoff ein (nelements == 1) - der
    Modus fuer das Periodensystem, wo ein Material genau einem Element
    zugeordnet werden muss.
    """
    # Nur die Top-Level-Namen anfordern; Unterfelder wie "symmetry.crystal_system"
    # kennt _fields nicht, die kommen im Objekt "symmetry" mit.
    felder = {pfad.split(".")[0] for pfad in MP_FIELD_MAP}
    felder.update(MP_META_FIELDS)

    params = {
        "_fields": ",".join(sorted(felder)),
        "deprecated": "false",
    }
    if nur_experimentell:
        params["theoretical"] = "false"
    if nur_stabil:
        params["is_stable"] = "true"
    if pure_element:
        params["elements"] = pure_element
        params["nelements"] = 1
    elif elements:
        params["elements"] = ",".join(elements)

    # Seitenweise holen. Die API deckelt _limit bei 1000 (Feld meta.max_limit),
    # liefert aber ohne Murren weniger, wenn man mehr verlangt - wer einfach
    # min(max_entries, 100) sendet, bekommt bei --max 500 stillschweigend 100
    # Dokumente und merkt es nicht. Deshalb echte Paginierung ueber _skip.
    materials = []
    while len(materials) < max_entries:
        params["_limit"] = min(max_entries - len(materials), MP_MAX_LIMIT)
        params["_skip"] = len(materials)
        resp = request_with_retry(
            "GET", f"{MP_API}/materials/summary/",
            headers=mp_headers(), params=params,
        )
        # Zwei verschiedene Codes, dieselbe Ursache - am Bestand geprueft
        # (2026-08-15): ohne Schluessel antwortet MP mit 401 "No API key found
        # in request", mit einem falschen Schluessel dagegen mit 403
        # "Forbidden". Wer nur 401 abfaengt, bekommt beim Tippfehler im
        # Schluessel einen nichtssagenden RuntimeError.
        if resp.status_code in (401, 403):
            raise MissingApiKey(
                f"Materials Project weist die Anfrage zurueck (HTTP "
                f"{resp.status_code}). MP_API_KEY pruefen - Schluessel unter "
                f"https://next-gen.materialsproject.org/api"
            )
        if not resp.ok:
            # MP begruendet Query-Fehler (422) im Body - sonst geht die
            # eigentliche Ursache im generischen HTTPError verloren.
            raise RuntimeError(
                f"MP-Query fehlgeschlagen ({resp.status_code}): "
                f"{resp.text[:500]}"
            )

        seite = resp.json().get("data", [])
        if not seite:
            break  # keine weiteren Treffer
        for doc in seite:
            formel = doc.get("formula_pretty")
            if not formel:
                continue
            doc["formula"] = formel
            materials.append(doc)
        if len(seite) < params["_limit"]:
            break  # letzte Seite war nicht voll -> Ende der Treffermenge

    return materials[:max_entries]


_LAST_REQUEST = 0.0



def request_with_retry(method: str, url: str, attempts: int = 4, **kwargs):
    """Einziger HTTP-Einstiegspunkt: drosselt und wiederholt bei 429/5xx.

    Die Drosselung steckt hier statt in den Aufrufern - so wird genau dann
    gewartet, wenn wirklich eine Anfrage rausgeht (Cache-Treffer bremsen
    nichts mehr), und keine Stelle kann das Rate-Limit versehentlich umgehen.

    Ohne Retry reisst ein einzelner 502 den kompletten Lauf ab; sowohl der
    Wikidata-Query-Service als auch NOMAD liefern die unter Last sporadisch.
    """
    global _LAST_REQUEST
    delay = 2.0
    for attempt in range(1, attempts + 1):
        wait = REQUEST_DELAY_SEC - (time.monotonic() - _LAST_REQUEST)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST = time.monotonic()
        try:
            # headers ueberschreibbar - die MP-API braucht zusaetzlich
            # X-API-KEY, alle anderen Aufrufer bleiben bei HEADERS.
            resp = requests.request(
                method, url, timeout=60,
                **{"headers": HEADERS, **kwargs}
            )
        except requests.RequestException:
            if attempt == attempts:
                raise
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
            if attempt == attempts:
                resp.raise_for_status()
            print(
                f"  HTTP {resp.status_code} von {url} - Versuch "
                f"{attempt}/{attempts}, warte {delay:.0f}s",
                file=sys.stderr,
            )
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"Unerreichbar: {url}")


def get_with_retry(url: str, params: dict, attempts: int = 4):
    resp = request_with_retry("GET", url, attempts, params=params)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Belege aus den Wikipedia-Einzelnachweisen ziehen
# ---------------------------------------------------------------------------
#
# Viele Infobox-Werte tragen einen eigenen <ref>-Beleg. Steht darin eine DOI
# oder ISBN, ist das ein echter Literaturbeleg und damit deutlich besser als
# "importiert aus Wikipedia" - dann wird er statt des Imports gesetzt.
#
# Reale Formen (alle im Kupfer-Artikel):
#   <ref name="Zhang">... [[doi:10.1021/je1011086]].</ref>
#   <ref name="Speight">... ISBN 978-1-259-58610-1, S. 41.</ref>
#   <ref>{{Literatur |Autor=... |ISBN=978-3-642-45427-1 |Seiten=380}}</ref>
#   {{DOI|10.1002/14356007.a07_471}}
#   <ref name="Harry H. Binder" />        <- reine WIEDERVERWENDUNG
# Die letzte Form ist wichtig: der Inhalt steht dann an anderer Stelle im
# Artikel und muss ueber den Namen aufgeloest werden, sonst geht bei der
# spezifischen Waermekapazitaet der Beleg verloren.

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
# Die deutsche Elementinfobox steht im ARTIKEL (nicht in einer eigenen
# Vorlagenseite wie im Englischen) und ist fuer diesen Zweck die ergiebigste
# Quelle ueberhaupt - sie fuehrt als einzige:
#   SpezifischeWaermekapazitaet  -> P2056, in J/(kg*K) als Skalar
#                                   (NOMAD hat dort nur eine C_v-Kurve)
#   ElektrischeLeitfaehigkeit    -> P2055, in S/m
#   Schallgeschwindigkeit        -> P2075, Poissonzahl -> P5593
#   CAS                          -> P231
#
# Der Artikeltitel wird ueber den Wikidata-Sitelink aufgeloest, NICHT aus dem
# Elementnamen geraten: Titan liegt unter "Titan (Element)", weil "Titan" der
# Mond bzw. die Mythologie ist.
#
# Deutsche Zahl- und Markup-Eigenheiten, alle real im Bestand:
#   Dichte = 8,96&nbsp;g/cm³ (20 [[Grad Celsius|°C]])<ref .../>  Dezimalkomma
#   ElektrischeLeitfaehigkeit = 58,1 · 10<sup>6</sup>            Zehnerpotenz
#   Schmelzpunkt_K = 1812 ± 1 [[Kelvin|K]]                       Toleranz
#   ElektrischeLeitfaehigkeit = etwa 7,14 · 10<sup>6</sup>       Unschaerfewort
#   Kristallstruktur = α-Eisen: kubisch raumzentriert<br />γ-...  MEHRDEUTIG
#   Dichte = Graphit: 2,26 g/cm<sup>3</sup><br />Diamant: 3,51    MEHRDEUTIG
#   Waermeleitfaehigkeit = <!--G: 119–165 W/(m·K)-->             auskommentiert
# Werte mit "<br" oder ":" bezeichnen mehrere Modifikationen und werden
# VERWORFEN - sonst landete willkuerlich Graphit oder Diamant als "der" Wert
# des Elements in Wikidata.

WIKIPEDIA_DE_QID = "Q48183"  # deutschsprachige Wikipedia
WIKIPEDIA_DE_API = "https://de.wikipedia.org/w/api.php"

# Infobox-Feld -> (interner Schluessel, Faktor auf die Wikidata-Einheit)
WIKIPEDIA_DE_FIELDS = {
    "Schmelzpunkt_K": ("melting_point", 1.0),            # K
    "Siedepunkt_K": ("boiling_point", 1.0),              # K
    "Dichte": ("density", 1000.0),                       # g/cm^3 -> kg/m^3
    "Wärmeleitfähigkeit": ("thermal_conductivity", 1.0),  # W/(m*K)
    "ElektrischeLeitfähigkeit": ("electrical_conductivity", 1.0),  # S/m
    "SpezifischeWärmekapazität": ("specific_heat_capacity", 1.0),  # J/(kg*K)
    "Schallgeschwindigkeit": ("speed_of_sound", 1.0),    # m/s
    "Poissonzahl": ("poisson_ratio", 1.0),               # dimensionslos
}

WIKIPEDIA_DE_CRYSTAL_KEYWORDS = [
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


# Verbindungen stehen in der deutschen Wikipedia nicht in der Elementinfobox,
# sondern in {{Infobox Chemikalie}}. Deren Felder heissen anders und - der
# entscheidende Unterschied - die Temperaturen stehen in GRAD CELSIUS:
#   | Schmelzpunkt = 1855 [[Grad Celsius|°C]]<ref .../>
#   | Siedepunkt   = 2900 °C
#   | Dichte       = 4,23 g·cm<sup>−3</sup>
#   | CAS          = {{CASRN|13463-67-7}}
# Ein Artikel traegt immer nur eine der beiden Infoboxen, deshalb koennen
# beide Feldsaetze gefahrlos nacheinander auf denselben Wikitext angewendet
# werden.
WIKIPEDIA_DE_CHEM_FIELDS = {
    "Dichte": ("density", 1000.0),   # g/cm^3 -> kg/m^3
}

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
    resp = request_with_retry("GET", api, params={
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
        xtal = strip_wiki_markup(roh).lower()
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
    )


def _infobox_proposals(wd_match, werte, skip_keys, quelle, projekt_qid,
                       permalink) -> list:
    """Gemeinsame Zeilenerzeugung fuer beide Wikipedia-Sprachen.

    Der Beleg wird in dieser Reihenfolge gewaehlt: DOI aus dem
    Einzelnachweis, sonst ISBN daraus, sonst der Wikimedia-Import. Ein
    echter Literaturbeleg ist in Wikidata deutlich mehr wert als
    "importiert aus Wikipedia"; der Permalink bleibt in der Notiz erhalten,
    damit nachvollziehbar ist, woher der Wert stammt.
    """
    proposals = []
    for key, (value, note, ids) in werte.items():
        if key in skip_keys:
            continue
        prop_info = PROPERTY_MAP.get(key)
        if prop_info is None:
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

        already_present = item_has_statement(wd_match["qid"], prop_info["pid"])
        proposals.append(make_row(
            "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
            quelle, wd_match, prop_info, value, value_label, reference,
        ))
    return proposals


# ---------------------------------------------------------------------------
# Fallback-Quelle 2: Englische Wikipedia-Elementinfobox (Import-Referenz)
# ---------------------------------------------------------------------------
#
# Die englische Wikipedia pflegt je Element eine Vorlage "Infobox <name>"
# (z. B. [[Template:Infobox copper]]) mit sauber benannten Feldern:
#   - "melting point K" / "boiling point K" stehen bereits in KELVIN,
#     also genau in der Wikidata-Einheit
#   - "thermal conductivity" und "electrical resistivity at 20" liefern
#     Groessen, die NOMAD ueberhaupt nicht fuehrt
# Trotzdem ist Vorsicht noetig; reale Faelle aus dem Bestand:
#   density=8.935&nbsp;g/cm<sup>3</sup>&thinsp;<ref name="Arblaster 2018" />
#   thermal conductivity=graphite: 119-165      (Kohlenstoff: Prosa + Bereich)
#   electrical resistivity at 20=2.3{{e|3}}     (Silizium: Vorlage im Wert)
# Deshalb wird Markup entfernt und anschliessend nur ein SAUBERER Zahlwert
# akzeptiert; alles mit Buchstaben, Bereich oder Restvorlage wird verworfen.

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# Infobox-Feld -> (interner Schluessel, Umrechnung in die Wikidata-Einheit)
WIKIPEDIA_NUMERIC_FIELDS = {
    "melting point K": ("melting_point", 1.0),        # schon Kelvin
    "boiling point K": ("boiling_point", 1.0),        # schon Kelvin
    "thermal conductivity": ("thermal_conductivity", 1.0),  # W/(m*K)
}

# "crystal structure" nennt das Bravais-Gitter bzw. den Strukturtyp, nicht
# das Kristallsystem. Schreibweisen schwanken ("face-centered cubic" vs.
# "face centered cubic"), deshalb wird normalisiert und nach Schluesselwort
# gesucht. Reihenfolge ist wichtig: spezifisch vor allgemein.
WIKIPEDIA_CRYSTAL_KEYWORDS = [
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

    # Dichte steht konventionell in g/cm^3 -> kg/m^3
    dichte = parse_wiki_number(fields.get("density", ""))
    if dichte is not None and 0.01 <= dichte <= 30:
        merken("density", dichte * 1000.0, "density",
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


def wikipedia_proposals_for_item(wd_match: dict, name_en: str,
                                 skip_keys: set) -> list:
    """Vorschlaege aus der englischen Elementinfobox, als Import referenziert."""
    fields, permalink, wikitext = fetch_wikipedia_infobox(name_en)
    if not fields:
        return []
    return _infobox_proposals(
        wd_match, wikipedia_values(fields, wikitext), skip_keys,
        "Wikipedia (en)", WIKIPEDIA_EN_QID, permalink,
    )


# ---------------------------------------------------------------------------
# Fallback-Quelle 3: {{Chembox}} der englischen Wikipedia (Verbindungen)
# ---------------------------------------------------------------------------
#
# Fuer Verbindungen gibt es keine Vorlagenseite wie bei den Elementen; die
# Chembox steht im Artikel selbst. Angenehm dabei: die Einheit steckt im
# FELDNAMEN (MeltingPtC vs. MeltingPtK), es muss also nichts geraten werden.
#   | Density    = 4.23 g/cm3
#   | MeltingPtC = 1843
#   | BoilingPtC = 2972
#   | CASNo      = 13463-67-7
# Reihenfolge im Mapping: Kelvin-Felder vor Celsius-Feldern, damit der Wert
# ohne Umrechnung gewinnt, wenn die Box beide fuehrt.

# Feld -> (interner Schluessel, Faktor, Offset auf die Wikidata-Einheit)
CHEMBOX_FIELDS = {
    "MeltingPtK": ("melting_point", 1.0, 0.0),
    "MeltingPtC": ("melting_point", 1.0, 273.15),
    "BoilingPtK": ("boiling_point", 1.0, 0.0),
    "BoilingPtC": ("boiling_point", 1.0, 273.15),
    "Density": ("density", 1000.0, 0.0),          # g/cm^3 -> kg/m^3
}

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


# ---------------------------------------------------------------------------
# Schritt 2a: Elemente des Periodensystems -> bestehende Wikidata-Items
# ---------------------------------------------------------------------------

def fetch_element_qids() -> dict:
    """{Elementsymbol: {qid, label, name_en}} fuer alle chemischen Elemente.

    name_en adressiert die englische Vorlage "Template:Infobox <name>",
    title_de den deutschen Artikel (per Sitelink, nicht geraten).

    Ueber das Symbol (P246) statt ueber die Summenformel - fuer Reinstoffe
    ist das eindeutig und umgeht die Formel-Normalisierung (NOMAD schreibt
    "O2Ti", Wikidata P274 "TiO₂") vollstaendig.
    Geprueft am 2026-08-14: 174 Items mit P31=Q11344 und P246, KEIN Symbol
    doppelt vergeben - die Abbildung ist damit kollisionsfrei.
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
    resp = get_with_retry(WIKIDATA_SPARQL, {"query": query, "format": "json"})
    out = {}
    for b in resp.json()["results"]["bindings"]:
        qid = b["e"]["value"].rsplit("/", 1)[-1]
        out[b["sym"]["value"]] = {
            "qid": qid,
            "label": b.get("eLabel", {}).get("value", qid),
            "name_en": b["enLabel"]["value"],
            # Sitelink statt geratenem Titel: Titan liegt unter
            # "Titan (Element)".
            "title_de": b.get("deTitle", {}).get("value", ""),
        }
    return out


# ---------------------------------------------------------------------------
# Formel-Normalisierung
# ---------------------------------------------------------------------------
#
# NOMAD und Wikidata schreiben dieselbe Verbindung unterschiedlich auf, in
# ZWEI voneinander unabhaengigen Punkten:
#
#   Zeichensatz   NOMAD "TiO2" (ASCII-Ziffern) <-> Wikidata "TiO₂" (U+2082).
#                 Am Bestand geprueft (2026-08-15): unter den haeufigsten
#                 P274-Werten steht ausnahmslos die tiefgestellte Form, und
#                 eine VALUES-Abfrage auf TiO2/Al2O3/Fe2O3 liefert NULL
#                 Treffer, auf TiO₂/Al₂O₃/Fe₂O₃ dagegen 13.
#   Reihenfolge   NOMAD liefert alphabetisch ("O2Ti") - auch im Feld
#                 chemical_formula_hill, denn Hill ordnet ohne Kohlenstoff
#                 alphabetisch. Wikidata schreibt Verbindungen dagegen
#                 konventionell mit dem elektropositiveren Partner vorn
#                 ("TiO₂", "Al₂O₃", "NaCl", "SiC").
#
# Ein direkter Stringvergleich muss daran scheitern. Deshalb wird die Formel
# zuerst in ihre Zusammensetzung {Element: Anzahl} zerlegt und daraus werden
# die plausiblen Schreibweisen ERZEUGT, gegen die dann abgefragt wird.

_TIEFGESTELLT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_NORMALZIFFERN = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

# Elektronegativitaet nach Pauling - sie entscheidet, wer in der
# konventionellen Schreibweise vorn steht. Edelgase und einige Actinoide
# haben keinen etablierten Wert; sie fallen auf _EN_UNBEKANNT zurueck und
# werden dadurch nur ueber die alphabetische Variante gefunden.
_EN_UNBEKANNT = 2.2
PAULING = {
    "H": 2.20, "Li": 0.98, "Be": 1.57, "B": 2.04, "C": 2.55, "N": 3.04,
    "O": 3.44, "F": 3.98, "Na": 0.93, "Mg": 1.31, "Al": 1.61, "Si": 1.90,
    "P": 2.19, "S": 2.58, "Cl": 3.16, "K": 0.82, "Ca": 1.00, "Sc": 1.36,
    "Ti": 1.54, "V": 1.63, "Cr": 1.66, "Mn": 1.55, "Fe": 1.83, "Co": 1.88,
    "Ni": 1.91, "Cu": 1.90, "Zn": 1.65, "Ga": 1.81, "Ge": 2.01, "As": 2.18,
    "Se": 2.55, "Br": 2.96, "Kr": 3.00, "Rb": 0.82, "Sr": 0.95, "Y": 1.22,
    "Zr": 1.33, "Nb": 1.60, "Mo": 2.16, "Tc": 1.90, "Ru": 2.20, "Rh": 2.28,
    "Pd": 2.20, "Ag": 1.93, "Cd": 1.69, "In": 1.78, "Sn": 1.96, "Sb": 2.05,
    "Te": 2.10, "I": 2.66, "Xe": 2.60, "Cs": 0.79, "Ba": 0.89, "La": 1.10,
    "Ce": 1.12, "Pr": 1.13, "Nd": 1.14, "Pm": 1.13, "Sm": 1.17, "Eu": 1.20,
    "Gd": 1.20, "Tb": 1.10, "Dy": 1.22, "Ho": 1.23, "Er": 1.24, "Tm": 1.25,
    "Yb": 1.10, "Lu": 1.27, "Hf": 1.30, "Ta": 1.50, "W": 2.36, "Re": 1.90,
    "Os": 2.20, "Ir": 2.20, "Pt": 2.28, "Au": 2.54, "Hg": 2.00, "Tl": 1.62,
    "Pb": 2.33, "Bi": 2.02, "Po": 2.00, "At": 2.20, "Fr": 0.70, "Ra": 0.90,
    "Ac": 1.10, "Th": 1.30, "Pa": 1.50, "U": 1.38, "Np": 1.36, "Pu": 1.28,
    "Am": 1.13, "Cm": 1.28, "Bk": 1.30, "Cf": 1.30, "Es": 1.30, "Fm": 1.30,
    "Md": 1.30, "No": 1.30, "Lr": 1.30,
}

# Ein Token ist entweder ein Elementsymbol mit optionaler Anzahl oder eine
# Klammer mit optionaler Anzahl. Alles andere macht die Formel unbrauchbar.
_FORMEL_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)|(\()|(\)(\d*))")


def parse_formula(formula: str) -> Optional[dict]:
    """Summenformel -> {Element: Anzahl}, oder None wenn nicht deutbar.

    Versteht beide Ziffernarten und geschachtelte Klammern ("Ca(OH)₂").
    Bewusst streng: Hydratpunkte ("CuSO4·5H2O"), Ladungen, Freitext und
    unbekannte Elementsymbole fuehren zu None statt zu einer geratenen
    Zusammensetzung - ein falsch gedeuteter Treffer waere schlimmer als
    gar keiner.
    """
    if not formula:
        return None
    s = formula.strip().translate(_NORMALZIFFERN)
    if not s or not re.fullmatch(r"[A-Za-z0-9()]+", s):
        return None

    stapel = [collections.Counter()]
    pos = 0
    while pos < len(s):
        m = _FORMEL_TOKEN.match(s, pos)
        if not m or m.end() == pos:
            return None
        pos = m.end()
        symbol, anzahl, klammer_auf, klammer_zu, klammer_anzahl = m.groups()
        if symbol:
            if symbol not in PAULING and symbol not in ("He", "Ne", "Ar", "Rn"):
                return None  # kein Elementsymbol -> Formel nicht deutbar
            stapel[-1][symbol] += int(anzahl) if anzahl else 1
        elif klammer_auf:
            stapel.append(collections.Counter())
        elif klammer_zu:
            if len(stapel) == 1:
                return None  # schliessende Klammer ohne oeffnende
            gruppe = stapel.pop()
            faktor = int(klammer_anzahl) if klammer_anzahl else 1
            for el, n in gruppe.items():
                stapel[-1][el] += n * faktor
    if len(stapel) != 1:
        return None  # nicht geschlossene Klammer
    return dict(stapel[0]) or None


def _formel_schreiben(zusammensetzung: dict, reihenfolge: list,
                      tiefgestellt: bool) -> str:
    teile = []
    for el in reihenfolge:
        n = zusammensetzung[el]
        ziffern = "" if n == 1 else str(n)
        teile.append(el + (ziffern.translate(_TIEFGESTELLT)
                           if tiefgestellt else ziffern))
    return "".join(teile)


def formula_candidates(zusammensetzung: dict) -> list:
    """Plausible Schreibweisen einer Zusammensetzung, beste zuerst.

    Jeweils tief- und normalgestellt, in dieser Reihenfolge:

      Hill (C, dann H, dann alphabetisch): "C₁₅H₂₂O₃" - fuer ORGANISCHE
        Verbindungen, also solche mit Kohlenstoff UND Wasserstoff. Nur dort
        ist Hill die Konvention; ein Carbid wie SiC waere als "CSi" nirgends
        auffindbar.
      konventionell, elektropositiver Partner zuerst: "TiO₂", "Al₂O₃",
        "NaCl", "SiC", "CO₂" - fuer alles Anorganische.
      alphabetisch: "O₂Ti" - so liefert NOMAD, und vereinzelt steht es auch
        in Wikidata.

    Erzeugt werden immer alle drei; die Reihenfolge bestimmt nur, welche
    Schreibweise zuerst probiert wird. Doppelte fallen raus - bei NaCl
    bleiben so zwei Kandidaten statt sechs.
    """
    elemente = sorted(zusammensetzung)

    hill = ["C"] + (["H"] if "H" in zusammensetzung else [])
    hill += [el for el in elemente if el not in ("C", "H")]
    konventionell = sorted(
        elemente, key=lambda el: (PAULING.get(el, _EN_UNBEKANNT), el))

    organisch = "C" in zusammensetzung and "H" in zusammensetzung
    ordnungen = ([hill, konventionell] if organisch
                 else [konventionell] + ([hill] if "C" in zusammensetzung
                                         else []))

    kandidaten = []
    for reihenfolge in ordnungen + [elemente]:
        for tiefgestellt in (True, False):
            s = _formel_schreiben(zusammensetzung, reihenfolge, tiefgestellt)
            if s not in kandidaten:
                kandidaten.append(s)
    return kandidaten


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
    resp = get_with_retry(WIKIDATA_SPARQL, {"query": sparql, "format": "json"})
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

_CLAIM_CACHE: dict = {}


def fetch_item_pids(qid: str) -> set:
    """Alle P-Nummern, zu denen das Item bereits eine Aussage hat.

    Einmal pro Item statt einmal pro Property abfragen - im
    Periodensystem-Lauf spart das rund drei Viertel der Requests.
    """
    if qid not in _CLAIM_CACHE:
        resp = get_with_retry(
            WIKIDATA_API,
            {"action": "wbgetclaims", "entity": qid, "format": "json"},
        )
        _CLAIM_CACHE[qid] = set(resp.json().get("claims", {}))
    return _CLAIM_CACHE[qid]


def item_has_statement(qid: str, pid: str) -> bool:
    return pid in fetch_item_pids(qid)


def mp_value(raw, faktor):
    """Rohwert aus dem MP-Dokument -> Wert in der Wikidata-Einheit.

    faktor None kennzeichnet itemwertige Groessen (Kristallsystem); die
    werden nicht gerechnet, sondern spaeter ueber die value_map abgebildet.
    MP schreibt sie gross ("Tetragonal"), die value_map klein.
    """
    if raw is None:
        return None
    if faktor is None:
        return str(raw).strip().lower()
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None  # kein Zahlwert -> nicht deuten
    return raw * faktor


# ---------------------------------------------------------------------------
# Hauptlogik: Vorschlaege zusammenstellen
# ---------------------------------------------------------------------------

def build_proposals(elements: Optional[list], max_entries: int,
                    wikipedia: bool = True, nur_experimentell: bool = True,
                    nur_stabil: bool = True):
    """Liefert Vorschlagszeilen ueber die Summenformel.

    Dieselbe Quellenkaskade wie im Periodensystem-Modus, jede Stufe nur fuer
    das, was die vorherige nicht geliefert hat:
        Materials Project (DOI)  ->  de.wikipedia  ->  en.wikipedia
    Bei Verbindungen greifen dabei {{Infobox Chemikalie}} bzw. {{Chembox}}
    statt der Elementinfoboxen.

    Generator: die Zeilen werden sofort weitergereicht, damit ein langer Lauf
    auch bei Abbruch bereits Geschriebenes behaelt.
    """
    materials = fetch_mp_materials(
        elements, max_entries,
        nur_experimentell=nur_experimentell, nur_stabil=nur_stabil,
    )
    print(f"{len(materials)} MP-Materialien gefunden"
          + (" (experimentell" if nur_experimentell else " (auch theoretisch")
          + (", stabil)." if nur_stabil else ", auch instabil)."),
          file=sys.stderr)

    # Erst alle Formeln aufloesen und die Materialien nach Wikidata-Item
    # gruppieren. Zwei Gruende: die Wikipedia-Stufe muss wissen, was MP fuer
    # DIESES Item ueber ALLE seine Materialien hinweg schon abgedeckt hat,
    # und mehrere Materialien zur selben Formel (Polymorphe!) fragen Wikidata
    # nur einmal ab.
    gruppen = {}
    aufgeloest = {}
    for material in materials:
        formel = material.get("formula")
        if not formel:
            continue
        if formel not in aufgeloest:
            aufgeloest[formel] = find_wikidata_item_by_formula(formel)
        wd_match = aufgeloest[formel]
        if wd_match is None:
            continue  # kein bestehendes Item -> gemaess Vorgabe ueberspringen
        if wd_match.get("ambiguous"):
            yield {
                "status": "MANUELLE_KLAERUNG_NOETIG (mehrdeutige Formel)",
                "qid": "",
                "label": "",
                "property": "",
                "value": "",
                "formula": formel,
                "kandidaten": "; ".join(wd_match["candidates"]),
                "entry_id": material.get("material_id", ""),
                # In die Belegspalte, nicht in ein eigenes Feld: sonst faellt
                # die DOI beim CSV-Schreiben unter den Tisch (CSV_FIELDS kennt
                # kein "doi") und die Zeile ist nicht mehr rueckverfolgbar.
                "ref_doi": MP_DOI,
            }
            continue
        gruppen.setdefault(wd_match["qid"], (wd_match, []))[1].append(material)

    for i, (qid, (wd_match, gruppe)) in enumerate(gruppen.items(), 1):
        pids_belegt = set()
        n_mp = 0
        for material in gruppe:
            for proposal in proposals_for_material(material, wd_match):
                pids_belegt.add(proposal["_pid"])
                n_mp += 1
                yield proposal

        zaehler = collections.Counter()
        if wikipedia:
            zeilen, zaehler = wikipedia_fallback_proposals(
                wd_match, pids_belegt,
                de_title=wd_match.get("title_de", ""),
                en_title=wd_match.get("title_en", ""),
            )
            yield from zeilen

        print(
            f"  [{i}/{len(gruppen)}] {qid} ({wd_match['label']}): "
            f"MP {n_mp}"
            + (f", de.wp {zaehler['de.wp']}, en.wp {zaehler['en.wp']}"
               if wikipedia else ""),
            file=sys.stderr,
        )


def proposals_for_material(material: dict, wd_match: dict) -> list:
    """Erzeugt die Vorschlagszeilen fuer EIN MP-Material gegen EIN
    bestehendes Wikidata-Item. Gemeinsam genutzt von Formel- und
    Periodensystem-Modus.

    Belegt wird mit der Referenzpublikation der Datenbank plus der mp-ID -
    einzelne MP-Materialien haben keine eigene DOI. Die Notiz nennt
    zusaetzlich, ob das Material experimentell nachgewiesen und stabil ist,
    damit beim Durchsehen nicht nachgeschlagen werden muss.
    """
    mp_id = material.get("material_id", "?")
    # "berechnet (DFT)" steht bewusst an erster Stelle. MP-Werte sind
    # DFT-Rechnungen bei 0 K am idealen Einkristall, keine Messungen. Fuer
    # Dichte und Kristallsystem faellt das kaum ins Gewicht (am Bestand
    # geprueft: Cu/Fe/Ti weichen um 0,4-3,6 % vom Handbuchwert ab), fuer die
    # elastischen Moduln und die Poissonzahl sehr wohl - dort sind es 17-41 %
    # (Ti-Schubmodul 62 statt 44 GPa). Wer die Zeile durchsieht, muss das
    # sehen, ohne es zu wissen.
    belege = [f"Materials Project {mp_id}", "berechnet (DFT)"]
    if material.get("theoretical") is False:
        belege.append("experimentell nachgewiesen")
    if material.get("is_stable"):
        belege.append("stabil (auf der konvexen Huelle)")
    icsd = [i for i in (material.get("database_IDs") or {}).get("icsd", [])]
    if icsd:
        belege.append(f"ICSD {', '.join(str(i) for i in icsd[:3])}")
    reference = Reference(doi=MP_DOI, note="; ".join(belege))

    # Jede MP-Aussage ist gerechnet - siehe Abschnitt "Bestimmungsmethode".
    qualifiers = [(DETERMINATION_PID, DFT_QID, DFT_LABEL)]

    proposals = []
    for mp_field, (internal_key, faktor) in MP_FIELD_MAP.items():
        prop_info = PROPERTY_MAP.get(internal_key)
        if prop_info is None:
            continue
        value = mp_value(_dig(material, mp_field), faktor)
        if value is None:
            continue

        pid = prop_info["pid"]
        value_label = ""

        if prop_info.get("datatype") == "item":
            # Item-wertige Property: MP-String -> QID. Unbekannte
            # Auspraegungen werden nicht geraten.
            mapped = prop_info.get("value_map", {}).get(str(value))
            if mapped is None:
                proposals.append(
                    make_row(
                        f"MANUELLE_KLAERUNG_NOETIG (Wert '{value}' "
                        f"nicht in value_map fuer {pid})",
                        "MaterialsProject", wd_match, prop_info, value, "",
                        reference, formula=material.get("formula", ""),
                        entry_id=mp_id, qualifiers=qualifiers,
                    )
                )
                continue
            value, value_label = mapped
        else:
            value = round_significant(value)

        already_present = item_has_statement(wd_match["qid"], pid)

        proposals.append(
            make_row(
                "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
                "MaterialsProject", wd_match, prop_info, value, value_label,
                reference, formula=material.get("formula", ""),
                entry_id=mp_id, qualifiers=qualifiers,
            )
        )
    return proposals


def round_significant(value: float, digits: int = 6) -> float:
    """Auf signifikante Stellen runden, nicht auf Nachkommastellen.

    Die Groessen hier reichen von 1e-8 (spezifischer Widerstand in Ohm*m)
    bis 2e4 (Dichte in kg/m^3). round(x, 6) wuerde den Widerstand zu 0.0
    machen.
    """
    return float(f"{value:.{digits}g}")


def make_row(status, source, wd_match, prop_info, value, value_label,
             reference, formula="", entry_id="", qualifiers=None):
    """Baut eine Vorschlagszeile - einheitlich fuer alle Quellen.

    qualifiers ist eine Liste (pid, wert_qid, klartext); sie landet sowohl
    lesbar in der CSV-Spalte "bestimmungsmethode" als auch maschinenlesbar
    im QuickStatements-Entwurf.
    """
    qualifiers = qualifiers or []
    row = {
        "status": status,
        "source": source,
        "qid": wd_match["qid"],
        "label": wd_match["label"],
        "property": f"{prop_info['pid']} ({prop_info['label']})",
        "value": value,
        "value_label": value_label,
        "datatype": prop_info.get("datatype", "quantity"),
        "unit_qid": prop_info["unit_qid"],
        "formula": formula,
        "bestimmungsmethode": "; ".join(
            f"{pid}={wert} ({text})" for pid, wert, text in qualifiers
        ),
        "entry_id": entry_id,
    }
    row.update(reference.as_csv_fields())
    row["_ref"] = reference
    row["_pid"] = prop_info["pid"]
    row["_qualifiers"] = qualifiers
    return row


def build_periodic_table_proposals(
    max_per_element: int = 1, only: Optional[list] = None,
    wikipedia: bool = True, nur_experimentell: bool = True,
    nur_stabil: bool = True,
):
    """Vorschlaege fuer ALLE Elemente des Periodensystems (Generator).

    Fuer jedes Element wird im Materials Project nach dem REINEN Stoff
    (nelements == 1) gesucht und gegen das bestehende Wikidata-Item des
    Elements abgeglichen. Das Item kommt ueber das Elementsymbol (P246),
    nicht ueber die Summenformel - deshalb greift hier die Formel-
    Normalisierung nicht als Hindernis.

    ACHTUNG bei der Durchsicht: Ein Element hat je nach Modifikation
    unterschiedliche Dichte und Kristallsystem (Graphit/Diamant, alpha-/
    beta-Titan). MP liefert den Wert der jeweiligen STRUKTUR, nicht "den"
    Wert des Elements. Die mp-ID steht in jeder Zeile - vor Uebernahme
    pruefen, welche Modifikation gemeint ist. Der Filter auf experimentell
    nachgewiesene und stabile Materialien macht das deutlich zuverlaessiger
    als zuvor, nimmt die Pruefung aber nicht ab.

    Quellen greifen in absteigender Belastbarkeit des Belegs, jede nur fuer
    das, was die vorherige nicht geliefert hat:
        Materials Project (DOI)  ->  de.wikipedia  ->  en.wikipedia
    Die deutsche Infobox steht vor der englischen, weil sie mehr Groessen
    fuehrt (u. a. spezifische Waermekapazitaet, elektrische Leitfaehigkeit,
    Schallgeschwindigkeit, CAS-Nummer).
    """
    symbols = fetch_element_qids()
    print(f"{len(symbols)} chemische Elemente in Wikidata gefunden.", file=sys.stderr)

    todo = sorted(only) if only else sorted(symbols)
    for i, sym in enumerate(todo, 1):
        if sym not in symbols:
            print(f"  {sym}: kein Wikidata-Item mit diesem Symbol", file=sys.stderr)
            continue
        info = symbols[sym]
        wd_match = {"qid": info["qid"], "label": info["label"], "ambiguous": False}

        materials = fetch_mp_materials(
            None, max_per_element, pure_element=sym,
            nur_experimentell=nur_experimentell, nur_stabil=nur_stabil,
        )
        pids_belegt = set()
        n_mp = 0
        for material in materials:
            for proposal in proposals_for_material(material, wd_match):
                pids_belegt.add(proposal["_pid"])
                n_mp += 1
                yield proposal

        zaehler = collections.Counter()
        if wikipedia:
            zeilen, zaehler = wikipedia_fallback_proposals(
                wd_match, pids_belegt,
                de_title=info["title_de"], en_element=info["name_en"],
            )
            yield from zeilen

        print(
            f"  [{i}/{len(todo)}] {sym} ({info['qid']} {info['label']}): "
            f"MP {n_mp}"
            + (f", de.wp {zaehler['de.wp']}, en.wp {zaehler['en.wp']}"
               if wikipedia else ""),
            file=sys.stderr,
        )


def _dig(d: dict, dotted_path: str):
    """Liest verschachtelte dict-Werte anhand eines 'a.b.c'-Pfads."""
    cur = d
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "status",
    "source",
    "qid",
    "label",
    "property",
    "value",
    "value_label",
    "datatype",
    "unit_qid",
    "formula",
    # Qualifikator der Aussage: bei gerechneten Werten P459 -> DFT.
    # Leer bei Literaturwerten aus der Wikipedia.
    "bestimmungsmethode",
    # Nur bei MANUELLE_KLAERUNG_NOETIG belegt: die in Frage kommenden Items,
    # damit die Zeile ohne eigene Recherche abarbeitbar ist.
    "kandidaten",
    "entry_id",
    # Referenz: DOI wenn vorhanden, sonst URL + Abrufdatum
    "ref_mode",
    "ref_doi",
    "ref_isbn",
    "ref_url",
    "ref_retrieved",
    "ref_note",
]


def write_csv_streaming(proposals, path: str = "vorschlaege.csv") -> list:
    """Schreibt jede Zeile SOFORT und gibt sie zusaetzlich gesammelt zurueck.

    Ein Periodensystem-Lauf dauert je nach Drosselung viele Minuten. Wuerde
    erst am Ende geschrieben, waere bei Abbruch (Ctrl-C, Netzfehler) alles
    verloren - genau das ist beim Lauf ueber 44 von 174 Elementen passiert.
    Deshalb Zeile fuer Zeile mit flush().
    """
    gesammelt = []
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        f.flush()
        for row in proposals:
            writer.writerow(row)
            f.flush()
            gesammelt.append(row)
    print(
        f"Vorschlagsliste geschrieben nach: {path} ({len(gesammelt)} Zeilen)",
        file=sys.stderr,
    )
    return gesammelt


def write_csv(proposals: list, path: str = "vorschlaege.csv") -> None:
    write_csv_streaming(proposals, path)


def quickstatements_value(row: dict) -> str:
    """Wert einer Aussage in QuickStatements-V1-Schreibweise.

    Mengenwerte MUESSEN ihre Einheit tragen: QuickStatements erwartet
    "<zahl>U<QID-Nummer>", also z. B. "1357.77U11579" fuer Kelvin (Q11579).
    Ohne das "U..." landet der Wert als einheitenlose Zahl in Wikidata -
    eine Dichte stuende dann als blosse 8935 da.

    Ausserdem wird die Exponentialschreibweise aufgeloest: Python schreibt
    den spezifischen Widerstand als "1.678e-08", QuickStatements liest das
    nicht als Zahl. Ueber Decimal wird daraus "0.00000001678".

    Item-wertige Aussagen (z. B. P556 Kristallsystem) stehen als blankes
    QID - dort waere eine Einheit sinnlos.
    """
    value = row["value"]
    if row.get("datatype") == "item":
        return str(value)
    if row.get("datatype") in ("external-id", "string"):
        # Zeichenketten (z. B. CAS-Nummer) gehoeren in Anfuehrungszeichen,
        # sonst liest QuickStatements sie als Zahl oder QID.
        return f'"{value}"'

    try:
        zahl = format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError):
        return str(value)

    unit_qid = (row.get("unit_qid") or "").strip()
    if not unit_qid.startswith("Q"):
        return zahl  # dimensionslose Groesse
    return f"{zahl}U{unit_qid[1:]}"


def clear_quickstatements_draft(path: str) -> None:
    """Setzt den Entwurf vor dem Lauf auf einen Platzhalter.

    Der Entwurf entsteht erst am Ende. Ohne dieses Leeren stuende nach einem
    Abbruch der vollstaendige Entwurf des VORIGEN Laufs neben der frisch und
    nur teilweise geschriebenen CSV - zwei Dateien, die nicht zusammengehoeren
    und deren Unterschied niemandem auffaellt.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Lauf noch nicht abgeschlossen - dieser Entwurf ist leer "
                "und unvollstaendig.\n")


_TRENNER = "# " + "=" * 70


def _abschnitt_kopf(titel: str, anzahl: int, erklaerung: list,
                    einheit: tuple = ("Zeile", "Zeilen")) -> list:
    """Auskommentierter Abschnittskopf mit Zaehler und Begruendung."""
    zeilen = [
        "",
        _TRENNER,
        f"# {titel} ({anzahl} {einheit[0] if anzahl == 1 else einheit[1]})",
    ]
    zeilen += [f"# {z}" for z in erklaerung]
    zeilen.append(_TRENNER)
    return zeilen


def _vorhandene_zeile(row: dict) -> str:
    """Eine BEREITS_VORHANDEN-Zeile, vollstaendig auskommentiert."""
    ref = row.get("_ref")
    herkunft = f" | Quelle: {row.get('source', '?')}"
    if ref is not None:
        herkunft += f" ({ref.mode})"
    return (f"# {row.get('qid', '')}\t{row.get('_pid', '')}\t"
            f"{row.get('value', '')}{herkunft}")


def _klaerungs_zeilen(row: dict) -> list:
    """Eine MANUELLE_KLAERUNG-Zeile, vollstaendig auskommentiert.

    Zwei Auspraegungen: eine mehrdeutige Formel (dann steht kein Item fest,
    dafuer die Kandidaten) und ein Wert ohne Abbildung in der value_map
    (dann steht das Item fest, aber der Wert laesst sich nicht setzen).
    """
    grund = row.get("status", "").replace("MANUELLE_KLAERUNG_NOETIG", "").strip()
    grund = grund.strip("()") or "unklar"
    if row.get("kandidaten"):
        zeilen = [f"# Formel {row.get('formula', '?')}: {grund}"]
        for kandidat in row["kandidaten"].split("; "):
            zeilen.append(f"#     {kandidat}")
        zeilen.append(f"#     NOMAD-Eintrag {row.get('entry_id', '?')}, "
                      f"DOI {row.get('ref_doi') or '?'}")
        return zeilen
    return [
        f"# {row.get('qid', '')} {row.get('label', '')}: {grund}",
        f"#     Property {row.get('property', '?')}, Rohwert "
        f"{row.get('value', '?')!r}, Quelle {row.get('source', '?')}",
    ]


def write_quickstatements_draft(proposals: list, path: str = "quickstatements_entwurf.txt") -> None:
    """Erzeugt einen QuickStatements-V1-Entwurf aus ALLEN Zeilen.

    Einspielbar ist nur, was status == 'VORSCHLAG' hat (bestehendes Item,
    Property noch nicht gesetzt, Beleg vorhanden). Die beiden anderen
    Status kommen mit in die Datei, aber in eigene, durchgehend
    auskommentierte Abschnitte:

      BEREITS_VORHANDEN         geprueft und bewusst nicht vorgeschlagen
      MANUELLE_KLAERUNG_NOETIG  Entscheidung noetig, die das Skript nicht
                                treffen darf

    Sie stehen dort zur Kenntnis, nicht zur Ausfuehrung: ausserhalb des
    ersten Abschnitts beginnt JEDE Zeile mit '#'. Die Datei laesst sich
    dadurch komplett nach QuickStatements kopieren, ohne dass aus einer
    dieser Zeilen versehentlich eine Aussage wird.

    Die Datei bleibt ein ENTWURF - vor dem Einspielen jede Zeile pruefen!
    """
    vorschlaege = [r for r in proposals if r.get("status") == "VORSCHLAG"]
    vorhanden = [r for r in proposals
                 if r.get("status") == "BEREITS_VORHANDEN"]
    klaerung = [r for r in proposals
                if "KLAERUNG" in (r.get("status") or "")]

    lines = [
        _TRENNER,
        "# ENTWURF - vor Verwendung jede Zeile manuell pruefen!",
        "#",
        "# Aufbau dieser Datei:",
        f"#   ABSCHNITT 1  EINSPIELBAR .......... {len(vorschlaege):4d}  "
        "(die einzigen ausfuehrbaren Zeilen)",
        f"#   ABSCHNITT 2  BEREITS VORHANDEN .... {len(vorhanden):4d}  "
        "(auskommentiert)",
        f"#   ABSCHNITT 3  MANUELLE KLAERUNG .... {len(klaerung):4d}  "
        "(auskommentiert)",
        "#",
        "# Ausserhalb von Abschnitt 1 beginnt jede Zeile mit '#'.",
        "#",
        "# Mengenwerte tragen ihre Einheit als '<zahl>U<QID-Nummer>',",
        "# z. B. 1357.77U11579 = 1357.77 Kelvin (Q11579).",
        "# Beleg, in dieser Rangfolge: S356 = DOI, S212/S957 = ISBN-13/-10",
        "# (beide aus dem Wikipedia-Einzelnachweis des Wertes), sonst",
        "# S143+S4656 = Wikimedia-Import mit Permalink auf die Artikelversion.",
        "#",
        f"# {DETERMINATION_PID} {DFT_QID} als QUALIFIKATOR heisst: der Wert ist",
        f"# gerechnet ({DFT_LABEL}), nicht gemessen. Diese Aussagen",
        "# stammen aus dem Materials Project und beschreiben den idealen",
        "# Einkristall bei 0 K. Kristallsystem und Dichte liegen dicht am",
        "# Handbuchwert, elastische Moduln und Poissonzahl koennen deutlich",
        "# abweichen (Titan-Schubmodul 62 statt 44 GPa) - diese Zeilen vor",
        "# der Uebernahme gegen Literatur pruefen.",
        "# Zeilen OHNE diesen Qualifikator sind Literaturwerte aus einer",
        "# Wikipedia-Infobox - dort Wert und Modifikation gegenpruefen.",
        _TRENNER,
    ]

    lines += _abschnitt_kopf(
        "ABSCHNITT 1: EINSPIELBAR", len(vorschlaege),
        ["Nur diese Zeilen sind QuickStatements-Syntax. Trotzdem gilt:",
         "erst nach zeilenweiser Pruefung einspielen."],
        einheit=("Aussage", "Aussagen"),
    )
    ohne_einheit = []
    for row in vorschlaege:
        ref = row["_ref"]
        # Item-wertige Aussagen stehen als blankes QID (z. B. Q473227),
        # Mengenwerte als Zahl + Einheit. Ein in Anfuehrungszeichen gesetztes
        # QID wuerde QuickStatements als Zeichenkette interpretieren.
        wert = quickstatements_value(row)
        # Nur melden, wenn eine Einheit HINTERLEGT ist, aber nicht in der
        # Zeile landet. Echt dimensionslose Groessen (Poissonzahl) haben
        # bewusst keine und sind kein Fehler.
        if row.get("unit_qid") and "U" not in wert:
            ohne_einheit.append(f"{row['qid']} {row['_pid']}")
        # Reihenfolge in QuickStatements V1: Aussage, dann Qualifikatoren
        # (P-Praefix), dann Belege (S-Praefix) - alles in EINER Zeile.
        qual = "".join(
            f"\t{pid}\t{wert_qid}"
            for pid, wert_qid, _ in row.get("_qualifiers") or []
        )
        lines.append(
            f"{row['qid']}\t{row['_pid']}\t{wert}{qual}"
            f"{ref.as_quickstatements()}"
        )
        klartext = f" ({row['value_label']})" if row.get("value_label") else ""
        lines.append(f"# Quelle: {row['source']} ({ref.mode}) - {ref.note}{klartext}")
    if not vorschlaege:
        lines.append("# (keine)")

    lines += _abschnitt_kopf(
        "ABSCHNITT 2: BEREITS VORHANDEN - NICHT EINSPIELEN", len(vorhanden),
        ["Das Item traegt diese Property schon. Hier nur, damit",
         "nachvollziehbar ist, was geprueft und verworfen wurde."],
    )
    lines += [_vorhandene_zeile(r) for r in vorhanden] or ["# (keine)"]

    lines += _abschnitt_kopf(
        "ABSCHNITT 3: MANUELLE KLAERUNG NOETIG - NICHT EINSPIELEN",
        len(klaerung),
        ["Hier ist eine fachliche Entscheidung noetig, die das Skript",
         "nicht treffen darf - etwa welches Polymorph gemeint ist.",
         "Nach der Entscheidung die Aussage von Hand ergaenzen."],
    )
    for row in klaerung:
        lines += _klaerungs_zeilen(row)
    if not klaerung:
        lines.append("# (keine)")

    if ohne_einheit:
        # Sichtbar machen statt still durchgehen lassen - eine Mengenaussage
        # ohne Einheit ist in Wikidata praktisch immer ein Fehler.
        print(
            f"WARNUNG: {len(ohne_einheit)} Mengenaussage(n) ohne Einheit: "
            f"{', '.join(ohne_einheit[:5])}"
            + (" ..." if len(ohne_einheit) > 5 else ""),
            file=sys.stderr,
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(
        f"QuickStatements-Entwurf geschrieben nach: {path} "
        f"({len(vorschlaege)} einspielbar, {len(vorhanden)} vorhanden, "
        f"{len(klaerung)} zur Klaerung)",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elements", nargs="*", default=None, help="z. B. --elements Ti O")
    parser.add_argument("--max", type=int, default=50,
                        help="max. Anzahl MP-Materialien")
    parser.add_argument(
        "--periodic-table",
        action="store_true",
        help="Vorschlaege fuer ALLE Elemente des Periodensystems erzeugen "
        "(Abgleich ueber das Elementsymbol P246 statt ueber die Summenformel)",
    )
    parser.add_argument(
        "--per-element",
        type=int,
        default=1,
        help="MP-Materialien je Element im Periodensystem-Modus (Default: 1)",
    )
    parser.add_argument(
        "--experimentell",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="nur Materialien mit experimentellem Nachweis (theoretical=false, "
        "in aller Regel ICSD-hinterlegt). Default: an. --no-experimentell "
        "laesst auch rein gerechnete Strukturen zu - dann steigt die Ausbeute, "
        "aber die Verlaesslichkeit sinkt genau so, wie sie es bei NOMAD tat",
    )
    parser.add_argument(
        "--stabil",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="nur thermodynamisch stabile Materialien (is_stable=true, auf der "
        "konvexen Huelle). Default: an, abschaltbar mit --no-stabil",
    )
    parser.add_argument(
        "--wikipedia",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fehlende Werte aus den Wikipedia-Infoboxen holen, erst deutsch "
        "({{Infobox Chemisches Element}} / {{Infobox Chemikalie}}), dann "
        "englisch (Template:Infobox <element> / {{Chembox}}); belegt als "
        "Wikimedia-Import (P143 + P4656 mit Permalink auf die Version). "
        "Default: an, abschaltbar mit --no-wikipedia",
    )
    parser.add_argument("--out", default=None,
                        help="CSV-Ausgabe (Default: "
                             "vorschlaege_<Zeitstempel>.csv im aktuellen "
                             "Verzeichnis)")
    parser.add_argument("--qs-out", default=None,
                        help="QuickStatements-Entwurf (Default: "
                             "quickstatements_entwurf_<Zeitstempel>.txt)")
    args = parser.parse_args()

    # Zeitstempel im Dateinamen, fuer beide Dateien derselbe: so ueberschreibt
    # kein Lauf den vorherigen, und CSV und Entwurf sind als Paar erkennbar.
    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    out = args.out or f"vorschlaege_{stempel}.csv"
    qs_out = args.qs_out or f"quickstatements_entwurf_{stempel}.txt"

    if args.periodic_table:
        proposals = build_periodic_table_proposals(
            args.per_element, args.elements, args.wikipedia,
            args.experimentell, args.stabil,
        )
    else:
        proposals = build_proposals(
            args.elements, args.max, args.wikipedia,
            args.experimentell, args.stabil,
        )

    # Bei selbst gesetzten Pfaden kann eine Datei aus einem frueheren Lauf
    # dastehen. Den Entwurf deshalb VOR dem Lauf leeren - sonst laege nach
    # einem Abbruch der vollstaendige Entwurf von gestern neben der frisch
    # und nur teilweise geschriebenen CSV von heute.
    clear_quickstatements_draft(qs_out)

    print(f"Schreibe laufend nach: {os.path.abspath(out)}", file=sys.stderr)
    try:
        proposals = write_csv_streaming(proposals, out)
    except MissingApiKey as fehler:
        # Kein Traceback - das ist kein Programmfehler, sondern eine fehlende
        # Voraussetzung, und die Abhilfe steht in der Meldung.
        print(f"\nFEHLER: {fehler}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # Die CSV ist durch das flush() bereits vollstaendig bis zur letzten
        # verarbeiteten Zeile; nur der QuickStatements-Entwurf entfaellt.
        print(
            f"\nAbgebrochen. Bereits geschriebene Zeilen stehen in "
            f"{os.path.abspath(out)}; {os.path.abspath(qs_out)} ist als "
            f"unvollstaendig markiert.",
            file=sys.stderr,
        )
        return 1

    write_quickstatements_draft(proposals, qs_out)

    neu = [p for p in proposals if p.get("status") == "VORSCHLAG"]
    n_vorhanden = sum(1 for p in proposals if p.get("status") == "BEREITS_VORHANDEN")
    n_klaerung = sum(1 for p in proposals if "KLAERUNG" in p.get("status", ""))
    nach_beleg = collections.Counter(p.get("ref_mode", "?") for p in neu)
    aufschluesselung = ", ".join(
        f"{n}x {modus}" for modus, n in sorted(nach_beleg.items())
    )
    print(
        f"\nZusammenfassung: {len(neu)} neue Vorschlaege"
        + (f" ({aufschluesselung})" if neu else "")
        + f", {n_vorhanden} bereits vorhanden, "
        f"{n_klaerung} zur manuellen Klaerung.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    main()
