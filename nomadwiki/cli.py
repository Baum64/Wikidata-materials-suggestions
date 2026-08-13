"""
NOMAD -> Wikidata: Vorschlagsgenerator (nur bestehende Items, nur DOI-belegte Werte)
=====================================================================================

Zweck
-----
Dieses Skript erstellt KEINE neuen Wikidata-Items und schreibt auch nichts
automatisch in Wikidata. Es:

  1. sucht in der NOMAD-Datenbank nach Einträgen, die zu einem Datensatz mit
     einer echten DOI gehören (nur DOI = zitierfähige, stabile Referenz),
  2. gleicht die Materialformel gegen bestehende Wikidata-Items ab
     (Property P274 "chemical formula"),
  3. prüft, ob das jeweilige Statement dort schon existiert,
  4. schreibt alle offenen Kandidaten als CSV-"Vorschlagsliste" zur manuellen
     Prüfung, plus optional als QuickStatements-Entwurf (auskommentiert /
     deaktiviert, bis ein Mensch die Zeilen freigegeben hat).

WICHTIG - vor dem Einsatz anpassen
-----------------------------------
- USER_AGENT: gemäß Wikidata-Richtlinie mit echtem Namen/Kontakt ausfüllen
  (https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
- NOMAD_FIELD_MAP: Feldpfade im NOMAD-Schema können sich ändern. Vor Gebrauch
  im NOMAD API-Dashboard (https://nomad-lab.eu/prod/v1/api/v1/extensions/docs)
  verifizieren.
- PROPERTY_MAP: nur Properties eintragen, deren P-Nummer auf
  https://www.wikidata.org/wiki/Property:Pxxxx tatsächlich existiert und zum
  Datentyp passt. Aktuell nur mit sicher verifizierten Properties befüllt
  (Dichte P2054, Schmelzpunkt P2101, Siedepunkt P2102, Wärmeleitfähigkeit
  P2068, elektrische Leitfähigkeit P2055 - alle Datentyp "quantity").
  Mechanische Kenngrößen wie E-Modul haben aktuell KEINE etablierte
  Property - nicht ergänzen, bevor das nicht auf wikidata.org geprüft wurde.

  Achtung: Ein Eintrag in PROPERTY_MAP allein erzeugt noch keine Vorschläge.
  Vorschläge entstehen nur für Schlüssel, die auch in NOMAD_FIELD_MAP einen
  Pfad haben - siehe Kommentar dort zu den beiden Leitfähigkeiten.

Ablauf in der Praxis
---------------------
  python -m nomadwiki.cli --elements Ti O --max 50
  -> erzeugt vorschlaege.csv zur manuellen Durchsicht
  -> NICHTS wird automatisch nach Wikidata geschrieben
"""

import argparse
import csv
import sys
import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

USER_AGENT = "MaterialsWikidataSuggestBot/0.1 (mailto:DEINE-ADRESSE@example.org)"
HEADERS = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}

NOMAD_API = "https://nomad-lab.eu/prod/v1/api/v1"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

REQUEST_DELAY_SEC = 1.0  # höflich sein, Rate Limits respektieren

# NOMAD-Feldpfad -> interner Schlüssel (im API-Dashboard verifizieren!)
NOMAD_FIELD_MAP = {
    "results.material.chemical_formula_reduced": "formula",
    "results.material.chemical_formula_hill": "formula_hill",
    "results.properties.structures.structure_original.mass_density": "density",
    "results.material.symmetry.crystal_system": "crystal_system",
    # Beispiel weiterer Felder - vor Gebrauch prüfen/ergänzen:
    # "results.properties.thermodynamic.melting_point": "melting_point",
    #
    # Bandlücke: NOMAD hat die Größe
    # (results.properties.electronic.band_structure_electronic.band_gap[].value,
    # eine LISTE je Spinkanal, Werte in Joule), Wikidata hat aber KEINE
    # Property dafür.
    #
    # Q806352 ist das Konzept-Item "Bandlücke" - korrekt, aber als Prädikat
    # unbrauchbar: an der mittleren Stelle einer Aussage steht zwingend eine
    # P-Nummer, "<Material> Q806352 1.1" ist kein gültiges Statement.
    # Geprüft am 2026-08-13:
    #   - Q806352 hat kein P1687 ("Wikidata property")
    #   - keine Property trägt P1629 -> Q806352
    #   - Sweep über ALLE quantity-Properties auf band/gap/semiconduct liefert
    #     nur P2911 "time gap" und P9279 "Egapro" - nichts Passendes
    #   - Q806352 wird in nur 6 Statements verwendet, alle ontologisch
    #     (P1889/P366/P527/P2578); nirgends als Messwert an einem Material
    #   - auch Silizium (Q670) und Galliumarsenid (Q147395) führen keine
    #     solche Aussage
    # Der saubere Weg wäre ein Property-Proposal auf Wikidata; das neue
    # Property bekäme dann P1629 -> Q806352. Bis dahin wird hier nichts
    # eingetragen (siehe Regel im Modul-Docstring).
    # Mechanisch gültig wäre allenfalls P1552 (hat Merkmal) -> Q806352, also
    # "hat eine Bandlücke" OHNE Zahlenwert - für einen Datenaustausch wertlos
    # und bisher auf Wikidata für diesen Fall unbenutzt.
    #
    # Wärmekapazität: Wikidata hat P2056 (spezifische Wärmekapazität, J/(kg*K)).
    # NOMAD liefert unter
    # results.properties.vibrational.heat_capacity_constant_volume nur
    # heat_capacities + temperatures, und zwar als Archiv-Referenz auf eine
    # KURVE (C_v über Temperatur) für die Simulationszelle - kein Skalar und
    # nicht massenbezogen. Für einen Austausch fehlen zwei Festlegungen:
    # (a) bei welcher Temperatur abgegriffen wird, (b) Umrechnung C_v [J/K] der
    # Zelle -> c_p [J/(kg*K)] des Stoffs. Erst danach eintragen.
    #
    # Wärme- und elektrische Leitfähigkeit (P2068 / P2055) sind in PROPERTY_MAP
    # definiert, haben hier aber bewusst KEINEN Pfad: NOMAD führt beide
    # Größen derzeit nicht in seiner harmonisierten results-Sektion.
    # Geprüft am 2026-08-13 gegen das vollständige kontrollierte Vokabular
    # results.properties.available_properties (192 Terme, 66 Top-Level-Sektionen)
    # - kein Treffer auf conduct/thermal/transport/resistiv. Vorhanden sind nur
    # electronic (band_gap, dos), mechanical (bulk_modulus, shear_modulus),
    # vibrational (heat_capacity_constant_volume, energy_free_helmholtz),
    # structures, spectra, solar_cell, trajectory, geometry_optimization.
    # Sobald NOMAD die Größen aufnimmt, genügt hier je eine Zeile:
    # "results.properties.<pfad>.thermal_conductivity": "thermal_conductivity",
    # "results.properties.<pfad>.electrical_conductivity": "electrical_conductivity",
}

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
    # Spezifische Waermekapazitaet - verifiziert, aber noch ohne NOMAD-Pfad,
    # siehe Kommentar in NOMAD_FIELD_MAP.
    "specific_heat_capacity": {
        "pid": "P2056",
        "datatype": "quantity",
        "unit_qid": "Q3085309",  # Joule pro Kilogramm-Kelvin, J/(kg*K)
        "label": "Spezifische Waermekapazitaet",
    },
}


# ---------------------------------------------------------------------------
# Schritt 1: NOMAD-Einträge mit DOI holen
# ---------------------------------------------------------------------------

def fetch_nomad_entries_with_doi(elements: Optional[list], max_entries: int = 50) -> list:
    """Fragt NOMAD nach Einträgen, deren zugehöriger Datensatz eine DOI hat.

    Gibt eine Liste von dicts zurück, jeweils mit entry_id, formula, doi.
    """
    # NOMAD kennt keinen "exists"-Operator. Eine offene Range auf das
    # Keyword-Feld datasets.doi wirkt aber als Existenzfilter: jede echte DOI
    # beginnt mit "10." und liegt damit lexikografisch ueber "0".
    query: dict = {"datasets.doi:gt": "0"}
    if elements:
        query["results.material.elements:all"] = elements

    payload = {
        "query": query,
        "pagination": {"page_size": min(max_entries, 100)},
        "required": {
            "include": [
                "entry_id",
                "results.material.chemical_formula_reduced",
                "results.material.chemical_formula_hill",
                # Unterfelder einzeln anfordern - "datasets" allein liefert
                # nur leere Objekte zurueck.
                "datasets.doi",
                "datasets.dataset_id",
                "datasets.dataset_name",
            ]
        },
    }

    resp = requests.post(f"{NOMAD_API}/entries/query", json=payload, headers=HEADERS, timeout=30)
    if not resp.ok:
        # NOMAD begruendet Query-Fehler (422) im Body - sonst geht die
        # eigentliche Ursache im generischen HTTPError verloren.
        raise RuntimeError(
            f"NOMAD-Query fehlgeschlagen ({resp.status_code}): {resp.text[:500]}"
        )
    data = resp.json()

    results = []
    for entry in data.get("data", []):
        datasets = entry.get("datasets", []) or []
        doi = None
        for ds in datasets:
            if ds.get("doi"):
                doi = ds["doi"]
                break
        if not doi:
            continue  # kein DOI -> gemaess Vorgabe ueberspringen
        material = entry.get("results", {}).get("material", {})
        results.append(
            {
                "entry_id": entry.get("entry_id"),
                "formula": material.get("chemical_formula_reduced"),
                "formula_hill": material.get("chemical_formula_hill"),
                "doi": doi,
                "doi_url": doi
                if doi.startswith("http")
                else f"https://doi.org/{doi[4:] if doi.startswith('doi:') else doi}",
            }
        )

    return results


def fetch_entry_values(entry_id: str) -> dict:
    """Holt die eigentlichen physikalischen Werte fuer einen NOMAD-Eintrag.

    Feldpfade unbedingt vor Produktivbetrieb im API-Dashboard verifizieren.
    """
    # Achtung: Der Archiv-Endpunkt ignoriert die Punktnotation aus
    # required.include stillschweigend (er liefert dann nur m_ref_archives).
    # Nur die verschachtelte Form greift - alle Pfade in NOMAD_FIELD_MAP
    # liegen unter "results".
    payload = {"required": {"results": "*"}}
    resp = requests.post(
        f"{NOMAD_API}/entries/{entry_id}/archive/query",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    if resp.status_code != 200:
        return {}
    # Die Nutzdaten liegen unter data.archive; data selbst enthaelt nur
    # entry_id/upload_id/parser_name. Ohne dieses Auspacken laeuft jeder
    # _dig("results....") ins Leere.
    return resp.json().get("data", {}).get("archive", {})


def get_with_retry(url: str, params: dict, attempts: int = 4):
    """GET mit Backoff bei 429/5xx.

    Der Wikidata-Query-Service liefert unter Last sporadisch 502; ohne Retry
    reisst ein einzelner Ausrutscher den kompletten Lauf ab.
    """
    delay = 2.0
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
        except requests.RequestException:
            if attempt == attempts:
                raise
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
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


# ---------------------------------------------------------------------------
# Schritt 2: Bestehendes Wikidata-Item ueber Formel finden
# ---------------------------------------------------------------------------

def find_wikidata_item_by_formula(formula: str) -> Optional[dict]:
    """Sucht ein BESTEHENDES Wikidata-Item mit passender chemischer Formel
    (P274). Legt NIEMALS ein neues Item an.
    """
    if not formula:
        return None

    sparql = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item wdt:P274 "{formula}" .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    LIMIT 5
    """
    resp = get_with_retry(WIKIDATA_SPARQL, {"query": sparql, "format": "json"})
    bindings = resp.json().get("results", {}).get("bindings", [])
    if not bindings:
        return None
    if len(bindings) > 1:
        # Mehrdeutig (z. B. Polymorphe) -> zur manuellen Klaerung markieren
        return {"ambiguous": True, "candidates": bindings}
    b = bindings[0]
    qid = b["item"]["value"].rsplit("/", 1)[-1]
    label = b.get("itemLabel", {}).get("value", qid)
    return {"qid": qid, "label": label, "ambiguous": False}


# ---------------------------------------------------------------------------
# Schritt 3: Pruefen, ob das Statement schon existiert
# ---------------------------------------------------------------------------

def item_has_statement(qid: str, pid: str) -> bool:
    resp = get_with_retry(
        WIKIDATA_API,
        {
            "action": "wbgetclaims",
            "entity": qid,
            "property": pid,
            "format": "json",
        },
    )
    claims = resp.json().get("claims", {})
    return bool(claims.get(pid))


# ---------------------------------------------------------------------------
# Hauptlogik: Vorschlaege zusammenstellen
# ---------------------------------------------------------------------------

def build_proposals(elements: Optional[list], max_entries: int) -> list:
    proposals = []
    entries = fetch_nomad_entries_with_doi(elements, max_entries)
    print(f"{len(entries)} NOMAD-Eintraege mit DOI gefunden.", file=sys.stderr)

    for entry in entries:
        time.sleep(REQUEST_DELAY_SEC)

        wd_match = find_wikidata_item_by_formula(entry["formula"])
        if wd_match is None:
            continue  # kein bestehendes Item -> gemaess Vorgabe ueberspringen
        if wd_match.get("ambiguous"):
            proposals.append(
                {
                    "status": "MANUELLE_KLAERUNG_NOETIG (mehrdeutige Formel)",
                    "qid": "",
                    "label": "",
                    "property": "",
                    "value": "",
                    "formula": entry["formula"],
                    "entry_id": entry["entry_id"],
                    "doi": entry["doi"],
                }
            )
            continue

        time.sleep(REQUEST_DELAY_SEC)
        values = fetch_entry_values(entry["entry_id"])

        for nomad_field, internal_key in NOMAD_FIELD_MAP.items():
            if internal_key not in PROPERTY_MAP:
                continue
            value = _dig(values, nomad_field)
            if value is None:
                continue

            prop_info = PROPERTY_MAP[internal_key]
            pid = prop_info["pid"]
            value_label = ""

            if prop_info.get("datatype") == "item":
                # Item-wertige Property: NOMAD-String -> QID. Unbekannte
                # Auspraegungen werden nicht geraten.
                mapped = prop_info.get("value_map", {}).get(str(value))
                if mapped is None:
                    proposals.append(
                        {
                            "status": f"MANUELLE_KLAERUNG_NOETIG (Wert '{value}' "
                            f"nicht in value_map fuer {pid})",
                            "qid": wd_match["qid"],
                            "label": wd_match["label"],
                            "property": f"{pid} ({prop_info['label']})",
                            "value": value,
                            "formula": entry["formula"],
                            "entry_id": entry["entry_id"],
                            "doi": entry["doi"],
                            "doi_url": entry["doi_url"],
                        }
                    )
                    continue
                value, value_label = mapped

            time.sleep(REQUEST_DELAY_SEC)
            already_present = item_has_statement(wd_match["qid"], pid)

            proposals.append(
                {
                    "status": "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
                    "qid": wd_match["qid"],
                    "label": wd_match["label"],
                    "property": f"{pid} ({prop_info['label']})",
                    "value": value,
                    "value_label": value_label,
                    "datatype": prop_info.get("datatype", "quantity"),
                    "unit_qid": prop_info["unit_qid"],
                    "formula": entry["formula"],
                    "entry_id": entry["entry_id"],
                    "doi": entry["doi"],
                    "doi_url": entry["doi_url"],
                }
            )

    return proposals


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

def write_csv(proposals: list, path: str = "vorschlaege.csv") -> None:
    fieldnames = [
        "status",
        "qid",
        "label",
        "property",
        "value",
        "value_label",
        "datatype",
        "unit_qid",
        "formula",
        "entry_id",
        "doi",
        "doi_url",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in proposals:
            writer.writerow(row)
    print(f"Vorschlagsliste geschrieben nach: {path}", file=sys.stderr)


def write_quickstatements_draft(proposals: list, path: str = "quickstatements_entwurf.txt") -> None:
    """Erzeugt einen QuickStatements-V1-Entwurf NUR fuer Zeilen mit
    status == 'VORSCHLAG' (also: bestehendes Item, Property noch nicht
    gesetzt, DOI vorhanden). Diese Datei ist ein ENTWURF - erst nach
    manueller Pruefung jeder Zeile in QuickStatements einspielen!
    """
    lines = [
        "# ENTWURF - vor Verwendung jede Zeile manuell pruefen!",
        "# Format: QID<TAB>PID<TAB>Wert<TAB>S248<TAB>Referenz-Item (DOI als externe ID separat ergaenzen)",
    ]
    for row in proposals:
        if row.get("status") != "VORSCHLAG":
            continue
        qid = row["qid"]
        pid = row["property"].split(" ")[0]
        doi = row["doi"]
        # Item-wertige Aussagen stehen als blankes QID (z. B. Q473227),
        # Mengenwerte als Zahl. Ein in Anfuehrungszeichen gesetztes QID wuerde
        # QuickStatements als Zeichenkette interpretieren.
        value = row["value"]
        # P356 = DOI (als Referenz-Statement fuer die Quelle empfohlen,
        # zusaetzlich zu einem eigenen "stated in"-Item, falls vorhanden)
        lines.append(f"{qid}\t{pid}\t{value}\tS854\t\"{row.get('doi_url', '')}\"")
        klartext = f" ({row['value_label']})" if row.get("value_label") else ""
        lines.append(
            f"# Quelle: DOI {doi} / NOMAD entry_id {row['entry_id']}{klartext}"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"QuickStatements-Entwurf geschrieben nach: {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elements", nargs="*", default=None, help="z. B. --elements Ti O")
    parser.add_argument("--max", type=int, default=50, help="max. Anzahl NOMAD-Eintraege")
    parser.add_argument("--out", default="vorschlaege.csv")
    parser.add_argument("--qs-out", default="quickstatements_entwurf.txt")
    args = parser.parse_args()

    proposals = build_proposals(args.elements, args.max)
    write_csv(proposals, args.out)
    write_quickstatements_draft(proposals, args.qs_out)

    n_vorschlag = sum(1 for p in proposals if p.get("status") == "VORSCHLAG")
    n_vorhanden = sum(1 for p in proposals if p.get("status") == "BEREITS_VORHANDEN")
    n_klaerung = sum(1 for p in proposals if "KLAERUNG" in p.get("status", ""))
    print(
        f"\nZusammenfassung: {n_vorschlag} neue Vorschlaege, "
        f"{n_vorhanden} bereits vorhanden, {n_klaerung} zur manuellen Klaerung.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
