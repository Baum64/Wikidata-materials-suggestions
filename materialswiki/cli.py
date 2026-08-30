"""
Materials Project -> Wikidata: Vorschlagsgenerator (nur bestehende Items)
=========================================================================

Erstellt KEINE neuen Wikidata-Items und schreibt nichts automatisch nach
Wikidata. Es entstehen eine CSV-Vorschlagsliste zur manuellen Pruefung und
ein QuickStatements-Entwurf, in dem nur Zeilen mit Status "VORSCHLAG"
ausfuehrbar sind.

Quellenkaskade, jede Stufe nur fuer das, was die vorherige nicht lieferte:

    (Formel)  ->  COD  ->  Materials Project  ->  NIST WebBook
              ->  de.wikipedia  ->  en.wikipedia

Die Formel-Stufe steht in Klammern: sie ist abgeschaltet, siehe unten.

Eine weitere Aussage entsteht aus dem Item selbst: die Punktgruppe (P589)
aus einer Raumgruppe (P690) am Item.

Die Formel-Stufe ist seit 2026-08-27 AUS: sie ist die einzige, die P527
"besteht aus" und P2670 "enthaelt Elemente von" vorschlaegt (samt der
Umstellung "Stoff P527 Element" -> P2670, der einzigen Stufe mit
Loeschzeilen), und diese beiden Properties sollen nicht mehr vorgeschlagen
werden. Der Code bleibt stehen; --formel schaltet ihn fuer einen einzelnen
Lauf wieder ein.

Die chemische Metaklasse (P31) fuer Legierungen war bis 2026-08-23 eine
Stufe dieses Werkzeugs. Sie folgt aus der Klassenzugehoerigkeit, nicht aus
einer Quelle, und steht jetzt in "Material class structure/Vorschläge
generieren.py" (Pruefung 'metaklasse').

Abschaltbar mit --no-punktgruppe, --no-cod, --no-nist, --no-wikipedia;
--formel schaltet die abgeschaltete Formel-Stufe wieder zu.

    python -m materialswiki --elements Ti O --max 50
    python -m materialswiki --group minerale --batch-size 500 --weiter

BEGRUENDUNGEN STEHEN IM README, NICHT HIER.
--------------------------------------------
materialswiki/README.md erklaert, warum die Kaskade so geordnet ist, warum
Werte gekennzeichnet, gefiltert oder bewusst weggelassen werden, und mit
welchen Messungen das jeweils belegt ist. Kommentare im Code verweisen
darauf, statt es zu wiederholen - sonst driften beide auseinander.

Vor dem Einsatz
---------------
- MP_API_KEY und CONTACT_EMAIL gehoeren in die gitignorierte .env im
  Repo-Wurzelverzeichnis (Vorlage: .env.beispiel), nicht in den Quelltext.
  Ohne Schluessel antwortet die MP-API mit HTTP 401.
- MP_FIELD_MAP: Feldnamen und Einheiten stammen aus dem OpenAPI-Schema
  (https://api.materialsproject.org/openapi.json, ausgewertet 2026-08-15).
  Aendert sich das Schema, hier nachziehen.
- PROPERTY_MAP: nur Properties eintragen, die es auf wikidata.org gibt und
  deren Datentyp passt. Ein Eintrag allein erzeugt noch keine Vorschlaege -
  dafuer braucht der Schluessel auch einen Pfad in MP_FIELD_MAP oder eine
  andere Quelle.
"""

import argparse
import collections
import csv
import datetime as dt
import html as htmlmodul
import json
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
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
import konfig  # noqa: E402

# Alle Vorschlagsdateien (CSV, QuickStatements) gehoeren nach proposals/ -
# CLAUDE.md, "Arbeitsweise" Punkt 2. Unabhaengig vom Arbeitsverzeichnis.
PROPOSALS_DIR = os.path.join(_REPO, "proposals")

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Kennungen, Endpunkte und Schluessel stehen in konfiguration.py - sie werden
# von jedem Modul gebraucht und sind keine Logik.
from .konfiguration import (  # noqa: E402
    CONTACT, CONTACT_EMAIL, HEADERS, MP_API, MP_API_KEY, MP_DATASET_DOI,
    MP_DATASET_WERK, MP_DOI, MP_MAX_LIMIT, MP_USER_AGENT, REQUEST_DELAY_SEC,
    USER_AGENT, WIKIDATA_API, WIKIDATA_SPARQL,
)


# ---------------------------------------------------------------------------
# Properties, Einheiten, Schranken
# ---------------------------------------------------------------------------
#
# Die Tabellen stehen in properties.py - sie sind lang, aendern sich selten
# und haengen an nichts.
from .properties import (  # noqa: E402,F401
    AGGREGAT_FEST, AGGREGAT_FLUESSIG, AGGREGAT_GAS, AGGREGAT_PID,
    CELSIUS_QID, DETERMINATION_PID, DFT_LABEL, DFT_QID, DFT_TEMPERATUR,
    KELVIN_QID, LITERATUR_BELEG, MP_FIELD_MAP, MP_META_FIELDS,
    OHNE_BELEG_DATENTYPEN, PLAUSIBEL, PROPERTY_MAP, STANDARD_TEMPERATUR_C,
    TEMPERATUR_PID, ist_plausibel,
)
from .properties import (  # noqa: E402,F401
    CHEMBOX_FIELDS, NUR_FESTKOERPER, RAUMTEMPERATUR_K, STUFEN_PIDS,
    TEMPERATUR_NACH_KELVIN, WIKIPEDIA_DE_CHEM_FIELDS, WIKIPEDIA_DE_FIELDS,
    WIKIPEDIA_NUMERIC_FIELDS,
)

# ---------------------------------------------------------------------------
# Die uebrigen Schichten
# ---------------------------------------------------------------------------
#
# Aufgerufen wird ueber das MODUL (netz.get_with_retry, wikidata.…) - so
# sperrt ein einziger monkeypatch in den Tests jeden Weg ins Netz, und man
# sieht an der Aufrufstelle, woher der Wert kommt.
from . import netz, wikidata  # noqa: E402
from .formeln import (  # noqa: E402,F401
    PAULING, elemente_aus_formel, formula_candidates, parse_formula,
)
from .wikidata import _ECHTES_ELEMENTSYMBOL  # noqa: E402,F401
from .ausgabe import (  # noqa: E402,F401
    CSV_FIELDS, Reference, WIKIPEDIA_EN_QID, clear_quickstatements_draft,
    make_row, quickstatements_value, round_significant, write_csv,
    write_csv_streaming, write_quickstatements_draft,
)
from . import infobox  # noqa: E402
from .infobox import (  # noqa: E402,F401
    WIKIPEDIA_API, WIKIPEDIA_DE_API, WIKIPEDIA_DE_QID, aggregatzustand_bei,
    dichte_qualifikatoren, extract_ref_ids, parse_de_cas,
    parse_de_messtemperatur, parse_de_number, parse_de_temperature,
    parse_infobox_fields, parse_thermal_expansion, parse_wiki_number,
    strip_wiki_markup, waermeausdehnung_proposals_for_item,
    wikipedia_de_chem_values, wikipedia_de_proposals_for_item,
    wikipedia_de_values, wikipedia_en_chem_proposals_for_item,
    wikipedia_en_chem_values, wikipedia_fallback_proposals,
    wikipedia_proposals_for_item, wikipedia_values,
)
# Die drei externen Quellen liegen je in einer Datei unter quellen/.
# Unter eigenem Namen, weil "cod" und "nist" hier auch Schalter sind - eine
# Namenskollision mit dem Modul haette den Lauf mitten im COD-Aufruf zerlegt.
from .quellen import cod as cod_quelle, mp as mp_quelle  # noqa: E402
from .quellen import nist as nist_quelle  # noqa: E402
from .quellen.cod import (  # noqa: E402,F401
    COD_API, COD_ENTRY_URL, cod_best_entry, cod_dominante_raumgruppe,
    cod_hill_formula, cod_proposals_for_item, fetch_cod_entries,
)
from .quellen.mp import (  # noqa: E402,F401
    MissingApiKey, fetch_mp_materials, mp_value, proposals_for_material,
    verfeinere_zentrierung,
)
from .quellen.nist import (  # noqa: E402,F401
    NIST_QUELLEN, melde_nist_quellen, nist_fetch, nist_proposals_for_item,
    nist_tabellenzeilen, nist_wert,
)

# ---------------------------------------------------------------------------
# Werkstoffgruppen und Ableitungen
# ---------------------------------------------------------------------------
#
# Welche Items ein Lauf anfasst, steht in gruppen.py; was sich ohne externe
# Quelle aus einem Item ableiten laesst, in ableitungen.py.
from . import ableitungen, gruppen  # noqa: E402
from .gruppen import (  # noqa: E402,F401
    HALBMETALLE, KUNSTSTOFF_PATTERN, KUNSTSTOFF_QID, LEGIERUNG_OHNE_ELEMENTE,
    LEGIERUNG_PATTERN, LEGIERUNG_QID, MAGNET_PATTERN, MAGNETWERKSTOFF_QID,
    MINERAL_PATTERN, NICHTMETALLE,
    NAMED_ALLOYS_SEITE, OXID_PATTERN, WERKSTOFFGRUPPEN, fetch_group_items,
    fetch_named_alloys, gruppen_qids, items_der_gruppe,
    ist_metall_oder_halbmetall, named_alloys_als_items,
    pruefe_legierungsklasse,
)
from .ableitungen import (  # noqa: E402,F401
    METALL_QID, legierungs_qids, fetch_metaklassen,
    fetch_p527_elemente, formel_proposals_for_item,
    metaklassen, metaklassen_vorladen,
    p527_elemente, p527_vorladen, punktgruppe_proposals_for_item,
    umstellung_proposals_for_item,
)
# ---------------------------------------------------------------------------
# Bewusst NICHT umgesetzt: P31
# ---------------------------------------------------------------------------
#
# Dieses Werkzeug schlaegt gar kein P31 mehr vor. Die Gemisch-Metaklasse
# (Q119892838) fuer Legierungen ist nach "Material class structure/Vorschläge
# generieren.py" gewandert - sie folgt aus dem Klassengraphen, den jenes
# Skript ohnehin haelt. Und P31 = "type of chemical entity" (Q113145171) fuer
# reine Stoffe bleibt offen: die Definition widerspricht sich zwischen
# Projektseite und Guideline. Wer das aufgreift, faengt bei dieser Klaerung
# an, nicht beim Code - Zahlen und Belege im README, "Bewusst nicht
# umgesetzt".


# ---------------------------------------------------------------------------
# Hauptlogik: Vorschlaege zusammenstellen
# ---------------------------------------------------------------------------

def build_group_proposals(gruppe: str, limit: Optional[int] = None,
                          wikipedia: bool = True, cod: bool = True,
                          nur_experimentell: bool = True,
                          nur_stabil: bool = True, max_entries: int = 1,
                          formel: bool = False,
                          punktgruppe_an: bool = True, nist: bool = True,
                          auch_vorhandene: bool = False,
                          ausschluss: bool = True):
    """Vorschlaege fuer eine Werkstoffgruppe (Generator).

    Dieselbe Quellenkaskade wie sonst; welche Stufe traegt, haengt an der
    Gruppe. Bei Mineralen und Oxiden greifen COD und Materials Project ueber
    die Summenformel; bei Legierungen tragen beide kaum etwas bei, weil dort
    nur 10 von 568 Items eine Formel haben - siehe fetch_group_items. Dafuer
    greift dort die umgekehrte Ableitung: Formel AUS den Bestandteilen.
    """
    items = items_der_gruppe(gruppe, limit, ausschluss=ausschluss)
    yield from pruefe_legierungsklasse(gruppe, items)
    yield from build_proposals_for_items(
        items, wikipedia, cod, nur_experimentell, nur_stabil, max_entries,
        formel=formel,
        punktgruppe_an=punktgruppe_an, nist=nist,
        auch_vorhandene=auch_vorhandene)


def build_proposals_for_items(items: list, wikipedia: bool = True,
                              cod: bool = True,
                              nur_experimentell: bool = True,
                              nur_stabil: bool = True, max_entries: int = 1,
                              nummer_ab: int = 1, gesamt: Optional[int] = None,
                              formel: bool = False,
                              punktgruppe_an: bool = True,
                              nist: bool = True,
                              auch_vorhandene: bool = False):
    """Vorschlaege fuer eine fertige Itemliste (Generator).

    Von build_group_proposals abgetrennt, damit der Chargenbetrieb dieselbe
    Logik nutzt: bei 6301 Mineralen laeuft ein Durchgang stundenlang, und
    ohne Zwischenstaende gaebe es bis zum Schluss keine einspielbaren
    QuickStatements. `nummer_ab` und `gesamt` sorgen dafuer, dass der
    Fortschritt ueber Chargen hinweg fortlaufend gezaehlt wird.
    """
    gesamt = gesamt if gesamt is not None else len(items)
    # Die Klassenlage aller Items auf einmal holen: eine Abfrage je 200
    # Items statt je Item. Scheitert das, laeuft der Rest trotzdem - die Stufe
    # fragt dann eben einzeln nach. Gebraucht wird sie fuer die Umstellung:
    # die stellt nur an Stoffen um, und ein Item ohne Summenformel gilt nur
    # als Stoff, wenn es eine Legierung ist.
    if formel:
        try:
            metaklassen_vorladen([e["qid"] for e in items])
        except (RuntimeError, ValueError, requests.RequestException) as fehler:
            print(f"  Klassenlage nicht vorgeladen - {fehler}",
                  file=sys.stderr)
    # Und die bestehenden P527-Elementaussagen, die umgestellt werden.
    if formel:
        try:
            p527_vorladen([e["qid"] for e in items])
        except (RuntimeError, ValueError, requests.RequestException) as fehler:
            print(f"  P527-Aussagen nicht vorgeladen - {fehler}",
                  file=sys.stderr)
    # Der Aussagenbestand aller Items auf einmal: eine Anfrage je 50 statt je
    # Item. Daraus speist sich sowohl "traegt das Item die Property schon?"
    # als auch der Siedepunkt.
    try:
        wikidata.claims_vorladen([e["qid"] for e in items])
    except (RuntimeError, ValueError, requests.RequestException) as fehler:
        print(f"  Aussagenbestand nicht vorgeladen - {fehler}", file=sys.stderr)
    # Und die CAS-Nummern, mit denen die NIST-Stufe sucht.
    if nist:
        try:
            wikidata.cas_vorladen([e["qid"] for e in items])
        except (RuntimeError, ValueError, requests.RequestException) as fehler:
            print(f"  CAS-Nummern nicht vorgeladen - {fehler}", file=sys.stderr)
    # Dasselbe fuer die Raumgruppen am Item, aus denen die Punktgruppe folgt.
    if punktgruppe_an:
        try:
            wikidata.item_raumgruppen_vorladen([e["qid"] for e in items])
        except (RuntimeError, ValueError, requests.RequestException) as fehler:
            print(f"  Raumgruppen nicht vorgeladen - {fehler}",
                  file=sys.stderr)

    for i, eintrag in enumerate(items, nummer_ab):
        wd_match = {"qid": eintrag["qid"], "label": eintrag["label"],
                    "ambiguous": False, "title_de": eintrag["title_de"],
                    "title_en": eintrag["title_en"]}
        pids_belegt = set()
        zaehler = collections.Counter()
        n_cod = n_mp = n_formel = n_p589 = 0

        # Vor der Ableitung die Umstellung: was am Item schon als P527 ->
        # Element steht, wird auf P2670 umgehaengt statt daneben noch einmal
        # behauptet.
        if formel:
            try:
                for zeile in umstellung_proposals_for_item(
                        wd_match, eintrag["formula"]):
                    n_formel += 1
                    yield zeile
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: Umstellung uebersprungen - "
                      f"{fehler}", file=sys.stderr)

        # Dann die Ableitung aus der Formel: sie kostet keine Anfrage nach
        # aussen und liefert eine Property, die keine der externen Quellen
        # hergibt - COD und MP kennen kein P2670.
        if formel and eintrag["formula"]:
            try:
                for zeile in formel_proposals_for_item(
                        wd_match, eintrag["formula"]):
                    pids_belegt.add(zeile["_pid"])
                    n_formel += 1
                    yield zeile
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: Formel uebersprungen - {fehler}",
                      file=sys.stderr)

        # Punktgruppe aus der Raumgruppe, die am Item schon steht. Vor der
        # COD-Stufe, damit die dort nicht dasselbe noch einmal vorschlaegt -
        # und weil ein bereits eingetragener Strukturbefund mehr wiegt als
        # ein frisch aus COD gezogener.
        if punktgruppe_an:
            try:
                for zeile in punktgruppe_proposals_for_item(wd_match):
                    pids_belegt.add(zeile["_pid"])
                    n_p589 += 1
                    yield zeile
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: Punktgruppe uebersprungen - "
                      f"{fehler}", file=sys.stderr)

        # Quellen, die nichts mehr beitragen koennen, werden gar nicht erst
        # befragt - siehe wikidata.stufe_kann_nichts_beitragen. Mit --auch-vorhandene
        # laeuft wieder jede Stufe, dann steht in Abschnitt 2 des Entwurfs
        # auch wirklich alles Gepruefte.
        def ueberspringen(stufe, qid=eintrag["qid"]):
            if auch_vorhandene:
                return False
            still = wikidata.stufe_kann_nichts_beitragen(qid, stufe)
            if still:
                wikidata._UEBERSPRUNGEN[stufe] += 1
            return still

        if cod and eintrag["formula"] and not ueberspringen("cod"):
            try:
                treffer = cod_quelle.fetch_cod_entries(formula=eintrag["formula"])
                if treffer:
                    # pids_belegt enthaelt hier, was die beiden Ableitungen
                    # aus dem Item selbst schon geliefert haben. Bei der
                    # Punktgruppe koennen sich beide Wege widersprechen -
                    # Graphit traegt Raumgruppe 194, die COD-Suche nach "C"
                    # findet aber ueberwiegend Diamant. Dann gilt, was am
                    # Item steht; die abweichende COD-Raumgruppe bleibt als
                    # eigene Zeile sichtbar.
                    for zeile in cod_quelle.cod_proposals_for_item(wd_match, treffer,
                                                        skip_pids=pids_belegt):
                        pids_belegt.add(zeile["_pid"])
                        n_cod += 1
                        yield zeile
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: COD uebersprungen - {fehler}",
                      file=sys.stderr)

        zusammensetzung = parse_formula(eintrag["formula"])
        if zusammensetzung and ueberspringen("mp"):
            zusammensetzung = None
        if zusammensetzung:
            # MP filtert ueber die enthaltenen Elemente, nicht ueber die
            # Formel. Zurueck kommen also auch andere Phasen desselben
            # Systems - uebernommen wird nur, was in der Zusammensetzung
            # wirklich uebereinstimmt.
            try:
                for material in mp_quelle.fetch_mp_materials(
                        sorted(zusammensetzung), max_entries,
                        nur_experimentell=nur_experimentell,
                        nur_stabil=nur_stabil):
                    if parse_formula(material.get("formula", "")) != zusammensetzung:
                        continue
                    for zeile in mp_quelle.proposals_for_material(material, wd_match,
                                                        skip_pids=pids_belegt):
                        pids_belegt.add(zeile["_pid"])
                        n_mp += 1
                        yield zeile
            except MissingApiKey:
                raise
            except (RuntimeError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: MP uebersprungen - {fehler}",
                      file=sys.stderr)

        # NIST WebBook: zwei Groessen, die keine andere Stufe liefert. Nur
        # wo eine CAS-Nummer am Item steht - danach sucht das WebBook.
        n_nist = 0
        if nist and not ueberspringen("nist"):
            try:
                for zeile in nist_quelle.nist_proposals_for_item(
                        wd_match, wikidata.cas_nummer(eintrag["qid"]),
                        eintrag["formula"], skip_pids=pids_belegt):
                    pids_belegt.add(zeile["_pid"])
                    n_nist += 1
                    yield zeile
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: NIST uebersprungen - {fehler}",
                      file=sys.stderr)

        if (wikipedia and (eintrag["title_de"] or eintrag["title_en"])
                and not ueberspringen("wikipedia")):
            try:
                zeilen, zaehler = infobox.wikipedia_fallback_proposals(
                    wd_match, pids_belegt,
                    de_title=eintrag["title_de"], en_title=eintrag["title_en"],
                )
                yield from zeilen
            except (RuntimeError, requests.RequestException) as fehler:
                print(f"  {eintrag['qid']}: Wikipedia uebersprungen - {fehler}",
                      file=sys.stderr)

        print(f"  [{i}/{gesamt}] {eintrag['qid']} "
              f"{eintrag['label'][:28]}: Formel {n_formel}, "
              f"P589 {n_p589}, COD {n_cod}, MP {n_mp}, NIST {n_nist}"
              + (f", de.wp {zaehler['de.wp']}, en.wp {zaehler['en.wp']}"
                 if wikipedia else ""),
              file=sys.stderr)


def build_proposals(elements: Optional[list], max_entries: int,
                    wikipedia: bool = True, nur_experimentell: bool = True,
                    nur_stabil: bool = True, cod: bool = True):
    """Liefert Vorschlagszeilen ueber die Summenformel.

    Dieselbe Quellenkaskade wie im Periodensystem-Modus, jede Stufe nur fuer
    das, was die vorherige nicht geliefert hat:
        COD  ->  Materials Project (DOI)  ->  de.wikipedia  ->  en.wikipedia
    Bei Verbindungen greifen dabei {{Infobox Chemikalie}} bzw. {{Chembox}}
    statt der Elementinfoboxen.

    Generator: die Zeilen werden sofort weitergereicht, damit ein langer Lauf
    auch bei Abbruch bereits Geschriebenes behaelt.
    """
    materials = mp_quelle.fetch_mp_materials(
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
            aufgeloest[formel] = wikidata.find_wikidata_item_by_formula(formel)
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
        n_cod = 0
        if cod:
            # COD zuerst - siehe build_periodic_table_proposals.
            formel = next((m.get("formula") for m in gruppe if m.get("formula")), "")
            try:
                treffer = cod_quelle.fetch_cod_entries(formula=formel)
                if treffer:
                    for proposal in cod_quelle.cod_proposals_for_item(wd_match, treffer):
                        pids_belegt.add(proposal["_pid"])
                        n_cod += 1
                        yield proposal
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {formel}: COD-Stufe uebersprungen - {fehler}",
                      file=sys.stderr)

        n_mp = 0
        for material in gruppe:
            for proposal in mp_quelle.proposals_for_material(material, wd_match,
                                                   skip_pids=pids_belegt):
                pids_belegt.add(proposal["_pid"])
                n_mp += 1
                yield proposal

        zaehler = collections.Counter()
        if wikipedia:
            zeilen, zaehler = infobox.wikipedia_fallback_proposals(
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


def build_periodic_table_proposals(
    max_per_element: int = 1, only: Optional[list] = None,
    wikipedia: bool = True, nur_experimentell: bool = True,
    nur_stabil: bool = True, cod: bool = True, nur_metalle: bool = True,
    nist: bool = True, auch_vorhandene: bool = False,
):
    """Vorschlaege fuer die metallischen Elemente (Generator).

    Standardmaessig nur Metalle und Halbmetalle - Nichtmetalle tragen zu
    einem Werkstoffprojekt nichts bei. Mit nur_metalle=False laeuft wieder
    das ganze Periodensystem.

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
        COD  ->  Materials Project (DOI)  ->  de.wikipedia  ->  en.wikipedia
    COD steht vorn, weil es fuer Raumgruppe und Kristallsystem die bessere
    Quelle ist: CC0 statt CC BY, gemessene Struktur statt DFT-Rechnung, und
    die DOI der Originalarbeit statt der Sammel-DOI einer Datenbank (siehe
    den COD-Abschnitt). MP liefert diese beiden Groessen nur noch, wo COD
    nichts hat. Die deutsche Infobox steht vor der englischen, weil sie mehr
    Groessen fuehrt (u. a. spezifische Waermekapazitaet, elektrische
    Leitfaehigkeit, Schallgeschwindigkeit, CAS-Nummer).
    """
    symbols = wikidata.fetch_element_qids()
    print(f"{len(symbols)} chemische Elemente in Wikidata gefunden.", file=sys.stderr)

    todo = sorted(only) if only else sorted(symbols)
    if nur_metalle:
        # Nichtmetalle tragen zu einem Werkstoffprojekt nichts bei, und ihre
        # Kennwerte waeren ohnehin ueberwiegend gesperrt (siehe
        # NUR_FESTKOERPER - die Haelfte von ihnen ist bei 20 C ein Gas).
        vorher = len(todo)
        todo = [s for s in todo if ist_metall_oder_halbmetall(s)]
        weg = vorher - len(todo)
        halb = sorted(s for s in todo if s in HALBMETALLE)
        print(f"Auswahl: {len(todo)} Metalle und Halbmetalle "
              f"(davon {len(halb)} Halbmetalle: {', '.join(halb)}); "
              f"{weg} Nichtmetalle uebersprungen.", file=sys.stderr)
    # Aussagenbestand aller Elemente auf einmal - 118 Elemente sind drei
    # Anfragen statt 118 (siehe wikidata.claims_vorladen).
    try:
        wikidata.claims_vorladen([symbols[s]["qid"] for s in todo if s in symbols])
    except (RuntimeError, ValueError, requests.RequestException) as fehler:
        print(f"  Aussagenbestand nicht vorgeladen - {fehler}", file=sys.stderr)

    gescheitert = []
    for i, sym in enumerate(todo, 1):
        if sym not in symbols:
            # Zwei verschiedene Gruende - der Unterschied ist wichtig, sonst
            # sucht man den Tippfehler in "Ubb", den es gar nicht gibt.
            grund = (
                "systematischer Platzhalter fuer ein unentdecktes Element"
                if not _ECHTES_ELEMENTSYMBOL.fullmatch(sym)
                else "kein Wikidata-Item mit diesem Symbol"
            )
            print(f"  {sym}: uebersprungen - {grund}", file=sys.stderr)
            continue
        info = symbols[sym]
        wd_match = {"qid": info["qid"], "label": info["label"], "ambiguous": False}

        # Ein einzelnes Element darf den Lauf nicht abreissen. Ueber 118
        # Elemente mal drei Quellen dauert ein Durchlauf Stunden; ein
        # Fehler bei Element 112 warf bisher alles Weitere weg, obwohl die
        # uebrigen 6 voellig in Ordnung gewesen waeren. Genau so ist es
        # passiert (HTTP 400 auf einen Platzhalter, siehe
        # wikidata.fetch_element_qids). Fehlender Schluessel bleibt toedlich - der
        # trifft jedes Element, da waere Weitermachen sinnlos.
        try:
            materials = mp_quelle.fetch_mp_materials(
                None, max_per_element, pure_element=sym,
                nur_experimentell=nur_experimentell, nur_stabil=nur_stabil,
            )
        except MissingApiKey:
            raise
        except (RuntimeError, requests.RequestException) as fehler:
            gescheitert.append(sym)
            print(f"  [{i}/{len(todo)}] {sym}: uebersprungen - {fehler}",
                  file=sys.stderr)
            continue

        def ueberspringen(stufe, qid=info["qid"]):
            if auch_vorhandene:
                return False
            still = wikidata.stufe_kann_nichts_beitragen(qid, stufe)
            if still:
                wikidata._UEBERSPRUNGEN[stufe] += 1
            return still

        pids_belegt = set()
        n_cod = 0
        if cod and not ueberspringen("cod"):
            # COD zuerst - siehe Docstring. Faellt die Stufe aus, laeuft der
            # Rest unveraendert weiter; MP springt dann wieder ein.
            try:
                treffer = cod_quelle.fetch_cod_entries(element_symbol=sym)
                if treffer:
                    for proposal in cod_quelle.cod_proposals_for_item(wd_match, treffer):
                        pids_belegt.add(proposal["_pid"])
                        n_cod += 1
                        yield proposal
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {sym}: COD-Stufe uebersprungen - {fehler}",
                      file=sys.stderr)

        n_mp = 0
        for material in (materials if not ueberspringen("mp") else []):
            for proposal in mp_quelle.proposals_for_material(material, wd_match,
                                                   skip_pids=pids_belegt):
                pids_belegt.add(proposal["_pid"])
                n_mp += 1
                yield proposal

        # NIST WebBook: 116 der 118 Elemente tragen eine CAS-Nummer, das ist
        # hier die ergiebigste Gruppe ueberhaupt.
        n_nist = 0
        if nist and not ueberspringen("nist"):
            try:
                for proposal in nist_quelle.nist_proposals_for_item(
                        wd_match, wikidata.cas_nummer(info["qid"]), sym,
                        skip_pids=pids_belegt):
                    pids_belegt.add(proposal["_pid"])
                    n_nist += 1
                    yield proposal
            except (RuntimeError, ValueError, requests.RequestException) as fehler:
                print(f"  {sym}: NIST uebersprungen - {fehler}",
                      file=sys.stderr)

        zaehler = collections.Counter()
        if wikipedia and not ueberspringen("wikipedia"):
            try:
                zeilen, zaehler = infobox.wikipedia_fallback_proposals(
                    wd_match, pids_belegt,
                    de_title=info["title_de"], en_element=info["name_en"],
                )
            except (RuntimeError, requests.RequestException) as fehler:
                # Die MP-Zeilen dieses Elements sind schon geliefert; nur
                # die Wikipedia-Ergaenzung faellt aus.
                zeilen = []
                print(f"  {sym}: Wikipedia-Stufe uebersprungen - {fehler}",
                      file=sys.stderr)
            yield from zeilen

        print(
            f"  [{i}/{len(todo)}] {sym} ({info['qid']} {info['label']}): "
            + (f"COD {n_cod}, " if cod else "")
            + f"MP {n_mp}"
            + (f", NIST {n_nist}" if nist else "")
            + (f", de.wp {zaehler['de.wp']}, en.wp {zaehler['en.wp']}"
               if wikipedia else ""),
            file=sys.stderr,
        )

    if gescheitert:
        # Am Ende noch einmal gesammelt - im Protokoll eines stundenlangen
        # Laufs geht eine einzelne Zeile von vor zwei Stunden unter.
        print(
            f"\n{len(gescheitert)} Element(e) uebersprungen: "
            f"{', '.join(gescheitert)}\n"
            f"Gezielt nachholen mit: --periodic-table --elements "
            f"{' '.join(gescheitert)}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _chargen_pfad(basis: str, nummer: int, endung: str) -> str:
    """vorschlaege.csv -> vorschlaege_charge03.csv"""
    stamm, alt = os.path.splitext(basis)
    return f"{stamm}_charge{nummer:02d}{endung or alt}"


def fortschritt_lesen(pfad: str) -> dict:
    if not os.path.exists(pfad):
        return {}
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def chargenlauf(args, out: str, qs_out: str) -> int:
    """Eine Gruppe in Chargen abarbeiten, nach jeder Charge schreiben.

    Warum ueberhaupt: 6301 Minerale mal mehrere Abfragen je Item sind
    Stunden. In einem Durchgang gaebe es bis zum Ende keine einspielbaren
    QuickStatements, und ein Abbruch kurz vor Schluss waere besonders
    aergerlich. Chargenweise ist nach jeweils --batch-size Items ein
    vollstaendiger, einspielbarer Satz fertig.

    Die Itemliste wird EINMAL geholt und in derselben stabilen Reihenfolge
    zerlegt (siehe fetch_group_items). Nur so meint "Charge 3" beim
    Fortsetzen dieselben Items wie im ersten Lauf.
    """
    fortschritt_datei = os.path.splitext(qs_out)[0] + ".fortschritt.json"

    offset = args.offset
    if args.weiter:
        stand = fortschritt_lesen(fortschritt_datei)
        if stand.get("gruppe") != args.group:
            print(f"FEHLER: {fortschritt_datei} gehoert zur Gruppe "
                  f"'{stand.get('gruppe', '?')}', nicht zu '{args.group}'.",
                  file=sys.stderr)
            return 2
        offset = stand.get("erledigt", 0)
        print(f"Setze fort bei Item {offset + 1}.", file=sys.stderr)

    items = items_der_gruppe(args.group, args.limit,
                             ausschluss=not args.mit_ueberschneidungen)
    gesamt = len(items)
    offen = items[offset:]
    if not offen:
        print(f"Nichts zu tun: alle {gesamt} Items der Gruppe "
              f"'{args.group}' sind bereits abgearbeitet.", file=sys.stderr)
        return 0

    anzahl_chargen = (len(offen) + args.batch_size - 1) // args.batch_size
    print(f"Noch offen: {len(offen)} von {gesamt}, in {anzahl_chargen} "
          f"Charge(n) zu je {args.batch_size}.", file=sys.stderr)
    for zeile in pruefe_legierungsklasse(args.group, offen):
        pass

    erste_nummer = offset // args.batch_size + 1
    gesamt_neu = gesamt_vorhanden = gesamt_klaerung = 0

    for versatz in range(0, len(offen), args.batch_size):
        charge = offen[versatz:versatz + args.batch_size]
        nummer = erste_nummer + versatz // args.batch_size
        erstes = offset + versatz + 1
        csv_pfad = _chargen_pfad(out, nummer, ".csv")
        qs_pfad = _chargen_pfad(qs_out, nummer, ".txt")

        print(f"\n--- Charge {nummer}: Items {erstes} bis "
              f"{erstes + len(charge) - 1} von {gesamt} ---", file=sys.stderr)
        clear_quickstatements_draft(qs_pfad)
        zeilen_gen = build_proposals_for_items(
            charge, args.wikipedia, args.cod,
            args.experimentell, args.stabil, args.max,
            nummer_ab=erstes, gesamt=gesamt, formel=args.formel,
            punktgruppe_an=args.punktgruppe, nist=args.nist,
            auch_vorhandene=args.auch_vorhandene,
        )
        try:
            zeilen = write_csv_streaming(zeilen_gen, csv_pfad)
        except MissingApiKey as fehler:
            print(f"\nFEHLER: {fehler}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            # Der Fortschritt steht auf der letzten VOLLSTAENDIGEN Charge -
            # die angefangene wird beim naechsten Lauf wiederholt. Lieber
            # doppelt gepruefte Items als uebersprungene.
            print(f"\nAbgebrochen in Charge {nummer}. Vollstaendige Chargen "
                  f"davor sind geschrieben; mit --weiter geht es bei Item "
                  f"{offset + versatz + 1} weiter.", file=sys.stderr)
            return 1

        write_quickstatements_draft(zeilen, qs_pfad)
        neu = sum(1 for z in zeilen if z.get("status") == "VORSCHLAG")
        vorhanden = sum(1 for z in zeilen if z.get("status") == "BEREITS_VORHANDEN")
        klaerung = sum(1 for z in zeilen if "KLAERUNG" in z.get("status", ""))
        gesamt_neu += neu
        gesamt_vorhanden += vorhanden
        gesamt_klaerung += klaerung

        erledigt = offset + versatz + len(charge)
        with open(fortschritt_datei, "w", encoding="utf-8") as f:
            json.dump({"gruppe": args.group, "erledigt": erledigt,
                       "gesamt": gesamt, "batch_size": args.batch_size,
                       "letzte_charge": nummer,
                       "zeitpunkt": dt.datetime.now().isoformat(timespec="seconds")},
                      f, indent=1)
        print(f"Charge {nummer} fertig: {neu} neu, {vorhanden} vorhanden, "
              f"{klaerung} zur Klaerung. Stand: {erledigt}/{gesamt}.",
              file=sys.stderr)

    wikidata.melde_uebersprungene_stufen()
    nist_quelle.melde_nist_quellen()
    print(f"\nAlle Chargen fertig. Insgesamt {gesamt_neu} neue Vorschlaege, "
          f"{gesamt_vorhanden} bereits vorhanden, {gesamt_klaerung} zur "
          f"Klaerung.\nFortschritt: {fortschritt_datei}", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elements", nargs="*", default=None, help="z. B. --elements Ti O")
    parser.add_argument("--max", type=int, default=50,
                        help="max. Anzahl MP-Materialien")
    parser.add_argument(
        "--periodic-table",
        action="store_true",
        help="Vorschlaege fuer die Elemente erzeugen (Abgleich ueber das "
        "Elementsymbol P246 statt ueber die Summenformel); "
        "standardmaessig nur Metalle und Halbmetalle, siehe --nur-metalle",
    )
    parser.add_argument(
        "--group", choices=sorted(WERKSTOFFGRUPPEN), default=None,
        help="Vorschlaege fuer eine ganze Werkstoffgruppe erzeugen. "
        "'minerale' ist mit Abstand die ergiebigste (6301 Arten, 5694 mit "
        "Summenformel, KEINE EINZIGE mit COD-ID); 'oxide' umfasst die 154 "
        "Oxide mit Summenformel; bei 'legierungen' laufen COD und MP mangels "
        "Formel weitgehend leer (nur 10 von 568 tragen eine), dafuer "
        "greift dort die Ableitung Formel AUS den Bestandteilen",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="mit --group: nur die ersten N Items bearbeiten. Bei 6301 "
        "Mineralen dauert ein voller Lauf Stunden",
    )
    parser.add_argument(
        "--batch-size", type=int, default=None, metavar="N",
        help="mit --group: in Chargen zu je N Items arbeiten. Nach JEDER "
        "Charge werden CSV und QuickStatements geschrieben - man kann also "
        "einspielen, waehrend der Rest noch laeuft, und ein Abbruch kostet "
        "hoechstens die angefangene Charge. Der Stand landet in einer "
        "Fortschrittsdatei, --weiter macht dort weiter",
    )
    parser.add_argument(
        "--offset", type=int, default=0, metavar="N",
        help="mit --group: die ersten N Items ueberspringen",
    )
    parser.add_argument(
        "--weiter", action="store_true",
        help="die naechste Charge aus der Fortschrittsdatei fortsetzen "
        "(setzt --offset auf den gespeicherten Stand)",
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
        "aber die Verlaesslichkeit sinkt entsprechend",
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
    parser.add_argument(
        "--cod",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Raumgruppe (P690), Kristallsystem (P556) und COD-ID (P9824) "
        "aus der Crystallography Open Database holen, BEVOR das Materials "
        "Project drankommt: CC0 statt CC BY, gemessene Struktur statt "
        "DFT-Rechnung, DOI der Originalarbeit statt Sammel-DOI. Default: an. "
        "Mit --no-cod liefert wieder MP diese Groessen",
    )
    parser.add_argument(
        "--formel",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Default: AUS. Zusammensetzung aus der Summenformel des Items "
        "ableiten: je "
        "funktionaler Gruppe eine Aussage 'besteht aus' (P527) - so gross, "
        "wie die Formel sie hergibt, bei Gips also Sulfat und Wasser statt "
        "S, O, H -, und je Element, das dann noch uebrig ist, eine Aussage "
        "'enthaelt Elemente von' (P2670). Anzahl jeweils als Qualifikator "
        "(P1114). Stellt ausserdem bestehende Aussagen 'Stoff P527 Element' "
        "auf P2670 um. Braucht keine externe Quelle und geht deshalb ohne "
        "S-Beleg raus. Elemente aus Mischreihen wie (Fe,Mg) werden NICHT "
        "vorgeschlagen, sondern zur Klaerung ausgewiesen. Abgeschaltet, weil "
        "P527 und P2670 nicht mehr vorgeschlagen werden sollen - dies ist die "
        "einzige Stufe, die beide erzeugt",
    )
    parser.add_argument(
        "--punktgruppe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Punktgruppe (P589) aus der Raumgruppe (P690) nachschlagen, die "
        "am Item schon steht - jede der 230 Raumgruppen gehoert zu genau "
        "einer der 32 Punktgruppen, und Wikidata fuehrt die Zuordnung an den "
        "Raumgruppen-Items. Traegt ein Item mehrere Raumgruppen, wird nichts "
        "vorgeschlagen. Default: an",
    )
    parser.add_argument(
        "--mit-ueberschneidungen",
        action="store_true",
        help="Items auch dann bearbeiten, wenn sie in einer anderen "
        "Werkstoffgruppe stehen, die einen eigenen Aufruf hat. "
        "Standardmaessig laesst 'minerale' die Items der Gruppe 'oxide' aus - "
        "sie laufen dort mit, und zweimal dasselbe vorzuschlagen hilft "
        "niemandem",
    )
    parser.add_argument(
        "--auch-vorhandene",
        action="store_true",
        help="auch Quellen befragen, deren Properties das Item schon "
        "vollstaendig traegt. Standardmaessig werden sie uebersprungen - das "
        "spart den teuersten Teil der Laufzeit, dafuer steht in Abschnitt 2 "
        "des Entwurfs dann nur noch, was beim Suchen nebenbei anfiel",
    )
    parser.add_argument(
        "--nist",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Standardbildungsenthalpie (P3078) und molare Standardentropie "
        "(P3071) aus dem NIST Chemistry WebBook holen, je Aggregatzustand "
        "(P515 als Qualifikator). Gesucht wird ueber die CAS-Nummer am Item; "
        "belegt wird NIE mit dem WebBook, sondern mit der Originalarbeit, der "
        "es den Wert zuschreibt (JANAF bzw. CODATA) - die NIST-Daten sind "
        "urheberrechtlich geschuetzt. Kostet je Item mit CAS zwei Abrufe mit "
        "5 s Wartezeit (robots.txt). Default: an",
    )
    parser.add_argument(
        "--nur-metalle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="im Periodensystem-Modus nur Metalle und Halbmetalle "
        "durchgehen (Default: an, das sind 98 der 118 Elemente). "
        "--no-nur-metalle nimmt auch die Nichtmetalle dazu - deren "
        "Festkoerper-Kennwerte werden allerdings ohnehin groesstenteils "
        "gesperrt, weil die Haelfte von ihnen bei 20 C ein Gas ist",
    )
    parser.add_argument("--out", default=None,
                        help="CSV-Ausgabe (Default: "
                             "proposals/vorschlaege_<Zeitstempel>.csv)")
    parser.add_argument("--qs-out", default=None,
                        help="QuickStatements-Entwurf (Default: "
                             "proposals/quickstatements_entwurf_<Zeitstempel>.txt)")
    args = parser.parse_args()

    # Zeitstempel im Dateinamen, fuer beide Dateien derselbe: so ueberschreibt
    # kein Lauf den vorherigen, und CSV und Entwurf sind als Paar erkennbar.
    # Ohne --out/--qs-out nach proposals/ (CLAUDE.md, "Arbeitsweise" Punkt 2).
    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    os.makedirs(PROPOSALS_DIR, exist_ok=True)
    out = args.out or os.path.join(PROPOSALS_DIR, f"vorschlaege_{stempel}.csv")
    qs_out = args.qs_out or os.path.join(
        PROPOSALS_DIR, f"quickstatements_entwurf_{stempel}.txt")

    if args.group and args.batch_size:
        return chargenlauf(args, out, qs_out)

    if args.group:
        proposals = build_group_proposals(
            args.group, args.limit, args.wikipedia, args.cod,
            args.experimentell, args.stabil, args.max, formel=args.formel,
            punktgruppe_an=args.punktgruppe, nist=args.nist,
            auch_vorhandene=args.auch_vorhandene,
            ausschluss=not args.mit_ueberschneidungen,
        )
    elif args.periodic_table:
        proposals = build_periodic_table_proposals(
            args.per_element, args.elements, args.wikipedia,
            args.experimentell, args.stabil, args.cod, args.nur_metalle,
            nist=args.nist, auch_vorhandene=args.auch_vorhandene,
        )
    else:
        proposals = build_proposals(
            args.elements, args.max, args.wikipedia,
            args.experimentell, args.stabil, args.cod,
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
    wikidata.melde_uebersprungene_stufen()
    nist_quelle.melde_nist_quellen()

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
