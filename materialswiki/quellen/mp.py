"""Materials Project: gerechnete Kennwerte, mit DOI belegt.

Alle Werte sind DFT-Rechnungen bei 0 K am idealen Einkristall - deshalb
traegt jede Aussage P459 "berechnet (DFT)", und deshalb steht COD davor.
Warum kein mp-api-Paket benutzt wird: README, "Warum nicht mp-api?".
"""

import collections
import sys
import time
from typing import Optional

import requests

import konfig

from .. import netz, wikidata
from ..ausgabe import Reference, make_row, round_significant
from ..konfiguration import (  # noqa: F401
    HEADERS,
    MP_API, MP_API_KEY, MP_DATASET_DOI, MP_DATASET_WERK, MP_DOI,
    MP_USER_AGENT, MP_MAX_LIMIT,
)
from ..formeln import parse_formula
from ..properties import (
    AGGREGAT_FEST, AGGREGAT_PID, DETERMINATION_PID, DFT_LABEL, DFT_QID,
    DFT_TEMPERATUR, LITERATUR_BELEG, MP_FIELD_MAP, MP_META_FIELDS,
    NUR_FESTKOERPER, PLAUSIBEL, PROPERTY_MAP, TEMPERATUR_PID, ist_plausibel,
)

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

    EIN Aufruf genuegt: das Material-Dokument enthaelt Formel, Symmetrie und
    alle Kennwerte zugleich. Zurueck kommt eine Liste von dicts mit formula,
    material_id, den Metafeldern und den Rohwerten.

    Die drei Qualitaetsfilter entscheiden ueber die Brauchbarkeit:

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
        resp = netz.request_with_retry(
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


def proposals_for_material(material: dict, wd_match: dict,
                           skip_pids: Optional[set] = None) -> list:
    """Erzeugt die Vorschlagszeilen fuer EIN MP-Material gegen EIN
    bestehendes Wikidata-Item. Gemeinsam genutzt von Formel- und
    Periodensystem-Modus.

    `skip_pids` sind Properties, die eine bessere Quelle schon geliefert hat
    - in der Praxis die COD-Stufe fuer Raumgruppe und Kristallsystem. MP ist
    dort nur noch Rueckfall.

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
    mp_reference = Reference(doi=MP_DOI, note="; ".join(belege))

    # Gerechnete Aussagen tragen P459 - siehe "Bestimmungsmethode".
    mp_qualifiers = [(DETERMINATION_PID, DFT_QID, DFT_LABEL)]

    skip_pids = skip_pids or set()
    # MP rechnet nur Festkoerper. Ist der Stoff bei 20 C ein Gas, beschreiben
    # die elastischen Moduln die Tieftemperaturphase - siehe NUR_FESTKOERPER.
    gasfoermig = wikidata.ist_bei_raumtemperatur_gas(wd_match["qid"])
    proposals = []
    for mp_field, (internal_key, faktor) in MP_FIELD_MAP.items():
        prop_info = PROPERTY_MAP.get(internal_key)
        if prop_info is None or prop_info["pid"] in skip_pids:
            continue
        if gasfoermig and internal_key in NUR_FESTKOERPER:
            continue
        value = mp_value(_dig(material, mp_field), faktor)
        if value is None:
            continue
        if internal_key == "crystal_system":
            # Spezifischer als "kubisch", wo die Raumgruppe es hergibt.
            value = verfeinere_zentrierung(
                value, _dig(material, "symmetry.symbol"))

        # Literaturbeleg statt Rechnung, wo die Rechnung die schlechtere
        # Quelle waere - siehe LITERATUR_BELEG.
        lit = LITERATUR_BELEG.get(internal_key)
        if lit:
            reference = Reference(
                isbn=lit["isbn"],
                note=f"{lit['werk']}; Wert aus der Symmetrieanalyse von "
                     f"Materials Project {mp_id} - Modifikation gegen das "
                     f"Werk pruefen",
            )
            qualifiers = []  # kein "berechnet (DFT)" auf einem Literaturwert
        elif internal_key in MP_DATASET_DOI:
            # Datensatz mit eigener Zitierpflicht - siehe MP_DATASET_DOI.
            zusatz = MP_DATASET_DOI[internal_key]
            reference = Reference(
                doi=MP_DOI, dataset_doi=zusatz,
                note="; ".join(belege + [MP_DATASET_WERK[zusatz]]),
            )
            qualifiers = list(mp_qualifiers)
        else:
            reference = mp_reference
            qualifiers = list(mp_qualifiers)

        if internal_key == "density":
            # P2054 verlangt Temperatur und Aggregatzustand. Hier NICHT die
            # 20-°C-Vorgabe: eine DFT-Rechnung liefert das Volumen des
            # relaxierten Grundzustands, also 0 K. Genau daher ruehrt auch
            # die systematische Abweichung von den Handbuchwerten - bei
            # Raumtemperatur ist die Zelle thermisch geweitet.
            # MP fuehrt ausschliesslich kristalline Festkoerper, "fest" ist
            # hier also keine Annahme.
            qualifiers += [DFT_TEMPERATUR, (AGGREGAT_PID, AGGREGAT_FEST, "fest")]

        if internal_key == "poisson_ratio":
            # Die Poissonzahl haengt an der Temperatur - bei Stahl steigt sie
            # zwischen Raumtemperatur und 500 °C messbar an -, und der
            # Elastizitaetsdatensatz (de Jong et al. 2015) ist wie alles bei
            # MP bei 0 K gerechnet. Ohne Qualifikator stuende in Wikidata eine
            # temperaturlose Zahl, die stillschweigend als Raumtemperaturwert
            # gelesen wuerde - gerade hier weicht die Rechnung aber am
            # staerksten ab (17-41 %, siehe oben).
            # P5593 kennt keinen Qualifikator-Constraint; am Bestand tragen 4
            # der 226 Aussagen bereits P2076 (gemessen 2026-08-19).
            qualifiers.append(DFT_TEMPERATUR)

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
            # Physikalisch Unmoegliches nie vorschlagen - siehe PLAUSIBEL.
            if not ist_plausibel(internal_key, value):
                grenzen = PLAUSIBEL[internal_key]
                proposals.append(
                    make_row(
                        f"MANUELLE_KLAERUNG_NOETIG (unplausibler Wert "
                        f"{value:g}, erwartet {grenzen[0]:g}..{grenzen[1]:g} "
                        f"- Rechnung in {mp_id} vermutlich fehlgeschlagen)",
                        "MaterialsProject", wd_match, prop_info, value, "",
                        reference, formula=material.get("formula", ""),
                        entry_id=mp_id, qualifiers=qualifiers,
                    )
                )
                continue

        already_present = wikidata.item_has_statement(wd_match["qid"], pid)

        proposals.append(
            make_row(
                "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
                "MaterialsProject", wd_match, prop_info, value, value_label,
                reference, formula=material.get("formula", ""),
                entry_id=mp_id, qualifiers=qualifiers,
            )
        )
    return proposals


def verfeinere_zentrierung(system, hm_symbol) -> str:
    """'cubic' -> 'fcc'/'bcc' anhand des Hermann-Mauguin-Symbols.

    MPs Feld crystal_system sagt nur "Cubic" und verschenkt damit die
    Unterscheidung zwischen Kupfer und Wolfram. Der ERSTE Buchstabe des
    Raumgruppensymbols nennt aber genau die Bravais-Zentrierung:

        P  primitiv            Fe (Im-3m) -> bcc
        F  flaechenzentriert   Cu (Fm-3m) -> fcc
        I  raumzentriert       W  (Im-3m) -> bcc

    Nur fuer kubische Systeme angewandt; bei allem anderen bleibt es beim
    Kristallsystem. Ein unbekannter Anfangsbuchstabe aendert nichts.
    """
    if system != "cubic" or not hm_symbol:
        return system
    return {"F": "fcc", "I": "bcc"}.get(str(hm_symbol).strip()[:1], system)


def _dig(d: dict, dotted_path: str):
    """Liest verschachtelte dict-Werte anhand eines 'a.b.c'-Pfads."""
    cur = d
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur
