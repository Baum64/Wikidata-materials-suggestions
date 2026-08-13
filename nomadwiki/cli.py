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
  (Schmelzpunkt, Siedepunkt, Dichte, Molmasse). Mechanische Kenngrößen wie
  E-Modul haben aktuell KEINE etablierte Property - nicht ergänzen, bevor das
  nicht auf wikidata.org geprüft wurde.

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
    # Beispiel weiterer Felder - vor Gebrauch prüfen/ergänzen:
    # "results.properties.thermodynamic.melting_point": "melting_point",
}

# Interner Schlüssel -> (Wikidata-Property, Einheit-QID, Beschreibung)
# NUR mit auf wikidata.org verifizierten Properties befüllen!
PROPERTY_MAP = {
    "density": {
        "pid": "P2054",
        "unit_qid": "Q844211",  # Kilogramm pro Kubikmeter (prüfen!)
        "label": "Dichte",
    },
    "melting_point": {
        "pid": "P2101",
        "unit_qid": "Q11579",  # Kelvin
        "label": "Schmelzpunkt",
    },
    "boiling_point": {
        "pid": "P2102",
        "unit_qid": "Q11579",  # Kelvin
        "label": "Siedepunkt",
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
    payload = {
        "required": {
            "include": list(NOMAD_FIELD_MAP.keys()),
        }
    }
    resp = requests.post(
        f"{NOMAD_API}/entries/{entry_id}/archive/query",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    if resp.status_code != 200:
        return {}
    return resp.json().get("data", {})


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

            time.sleep(REQUEST_DELAY_SEC)
            already_present = item_has_statement(wd_match["qid"], pid)

            proposals.append(
                {
                    "status": "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
                    "qid": wd_match["qid"],
                    "label": wd_match["label"],
                    "property": f"{pid} ({prop_info['label']})",
                    "value": value,
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
        value = row["value"]
        doi = row["doi"]
        # P356 = DOI (als Referenz-Statement fuer die Quelle empfohlen,
        # zusaetzlich zu einem eigenen "stated in"-Item, falls vorhanden)
        lines.append(f"{qid}\t{pid}\t{value}\tS854\t\"{row.get('doi_url', '')}\"")
        lines.append(f"# Quelle: DOI {doi} / NOMAD entry_id {row['entry_id']}")

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
