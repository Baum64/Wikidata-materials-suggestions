"""
Werkstoff-Datenquellen -> Wikidata: Vorschlagsgenerator (Multi-Source)
========================================================================

Ergaenzung zu materialswiki/cli.py um weitere freie Quellen. Grundprinzipien
bleiben unveraendert:

  - Es werden NIEMALS neue Wikidata-Items angelegt, nur bestehende ergaenzt.
  - Es wird NICHTS automatisch nach Wikidata geschrieben, nur eine
    Vorschlagsliste (Markdown-Tabelle) + QuickStatements-Entwurf zur
    manuellen Pruefung.
  - Referenzierung: DOI wird bevorzugt. Ist keine DOI verfuegbar, wird
    "Referenz-URL" (P854) + "Abgerufen am" (P813) als Fallback verwendet.

Unterstuetzte Quellen
----------------------
  1. Materials Project -> DOI-Referenz (Referenzpublikation der Datenbank,
                          da einzelne Eintraege i. d. R. keine eigene DOI haben)
  2. PubChem        -> URL-Referenz (PubChem vergibt keine Eintrags-DOIs;
                          jeder Wert erhaelt automatisch P854 + P813)

WICHTIG vor dem Einsatz
------------------------
- USER_AGENT unten mit echten Kontaktdaten fuellen.
- MP_API_KEY (Materials Project) selbst eintragen (kostenloser Account
  auf https://next-gen.materialsproject.org/api noetig).
- PROPERTY_MAP nur mit auf wikidata.org verifizierten P-Nummern befuellen.
  Mechanische Kenngroessen (E-Modul, Zugfestigkeit) sind hier bewusst NICHT
  enthalten, da aktuell keine etablierte Wikidata-Property existiert.
- Formel-basiertes Matching ist ein Heuristik-Schritt, kein Beweis der
  Identitaet -> jede Zeile vor dem Uebertragen manuell gegenpruefen,
  besonders bei Polymorphen/Isomeren (status "MANUELLE_KLAERUNG_NOETIG").

Aufruf
------
  python werkstoffe_wikidata_vorschlaege.py --formulas TiO2 Fe2O3 NaCl \
      --sources materials_project pubchem
"""

import argparse
import datetime as dt
import os
import sys
import time
from typing import Optional

# konfig.py liegt im Repo-Wurzelverzeichnis.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import konfig  # noqa: E402

import requests

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Kontaktadresse und Schluessel aus der Umgebung (konfig spiegelt
# .env.api-keys hinein).
USER_AGENT = ("MaterialsWikidataSuggestBot/0.2 "
              f'(mailto:{konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")})')
HEADERS = {"User-Agent": USER_AGENT}

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

MP_API = "https://api.materialsproject.org"
# Eigener Schluessel moeglich; leer -> der gemeinsame MP_API_KEY.
MP_API_KEY = (konfig.wert("MP_API_KEY_WERKSTOFFE")
              or konfig.wert("MP_API_KEY"))
MP_DATASET_DOI = "10.1063/1.4812323"  # Jain et al. 2013, Referenzpublikation der Materials Project Datenbank

PUBCHEM_PUG_REST = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_PUG_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"

REQUEST_DELAY_SEC = 1.0

# Interner Schluessel -> (Wikidata-Property, Einheit-QID, Beschreibung)
# NUR verifizierte Properties!
PROPERTY_MAP = {
    "density": {"pid": "P2054", "unit_qid": "Q844211", "label": "Dichte"},
    "melting_point": {"pid": "P2101", "unit_qid": "Q11579", "label": "Schmelzpunkt"},
    "boiling_point": {"pid": "P2102", "unit_qid": "Q11579", "label": "Siedepunkt"},
}


# ---------------------------------------------------------------------------
# Referenz-Modell
# ---------------------------------------------------------------------------

class Reference:
    """Repraesentiert eine Wikidata-Referenz: bevorzugt DOI, sonst URL+Datum."""

    def __init__(self, doi: Optional[str] = None, url: Optional[str] = None,
                 retrieved: Optional[str] = None, note: str = ""):
        self.doi = doi
        self.url = url
        self.retrieved = retrieved or dt.date.today().isoformat()
        self.note = note

    @property
    def mode(self) -> str:
        return "DOI" if self.doi else "URL+Datum"

    def as_table_fields(self) -> dict:
        return {
            "ref_mode": self.mode,
            "ref_doi": self.doi or "",
            "ref_url": self.url or (f"https://doi.org/{self.doi}" if self.doi else ""),
            "ref_retrieved": self.retrieved if self.mode == "URL+Datum" else "",
            "ref_note": self.note,
        }

    def as_quickstatements(self) -> str:
        """QuickStatements-Snippet fuer die Referenz (an Statement-Zeile anhaengen)."""
        if self.doi:
            # P356 = DOI, als Referenz-Statement
            return f'\tS356\t"{self.doi}"'
        # Fallback: Referenz-URL + Abrufdatum
        date_qs = f"+{self.retrieved}T00:00:00Z/11"
        return f'\tS854\t"{self.url}"\tS813\t{date_qs}'


# ---------------------------------------------------------------------------
# Quelle 1: Materials Project (DOI-Referenz auf Datenbank-Publikation)
# ---------------------------------------------------------------------------

def fetch_materials_project(formulas: list) -> list:
    results = []
    if not MP_API_KEY:
        print("WARNUNG: MP_API_KEY nicht gesetzt - Materials Project wird uebersprungen.", file=sys.stderr)
        return results

    headers = dict(HEADERS)
    headers["X-API-KEY"] = MP_API_KEY

    for formula in formulas:
        resp = requests.get(
            f"{MP_API}/materials/summary/",
            params={"formula": formula, "_fields": "material_id,formula_pretty,density"},
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            continue
        for item in resp.json().get("data", []):
            density = item.get("density")
            if density is None:
                continue
            results.append({
                "source": "MaterialsProject",
                "formula": item.get("formula_pretty", formula),
                "internal_key": "density",
                "value": density,
                "reference": Reference(
                    doi=MP_DATASET_DOI,
                    note=f"Materials Project ID {item.get('material_id')}",
                ),
            })
        time.sleep(REQUEST_DELAY_SEC)
    return results


# ---------------------------------------------------------------------------
# Quelle 2: PubChem (URL+Datum-Referenz, da keine Eintrags-DOI)
# ---------------------------------------------------------------------------

def _pubchem_cid_for_formula(formula: str) -> Optional[str]:
    resp = requests.get(
        f"{PUBCHEM_PUG_REST}/compound/formula/{formula}/cids/JSON",
        headers=HEADERS, timeout=30,
    )
    if resp.status_code != 200:
        return None
    cids = resp.json().get("IdentifierList", {}).get("CID", [])
    return str(cids[0]) if cids else None


def _pubchem_experimental_property(cid: str, heading: str) -> Optional[str]:
    """Liest einen Wert aus dem PUG-View 'Experimental Properties'-Abschnitt.
    heading z. B. 'Melting Point', 'Boiling Point', 'Density'.
    Rueckgabe ist der Rohtext (muss vor Uebernahme geparst/normalisiert werden!).
    """
    resp = requests.get(f"{PUBCHEM_PUG_VIEW}/data/compound/{cid}/JSON", headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return None
    data = resp.json()

    def walk(sections):
        for sec in sections:
            if sec.get("TOCHeading") == heading:
                for info in sec.get("Information", []):
                    val = info.get("Value", {})
                    strings = val.get("StringWithMarkup", [])
                    if strings:
                        return strings[0].get("String")
            if "Section" in sec:
                found = walk(sec["Section"])
                if found:
                    return found
        return None

    record = data.get("Record", {})
    return walk(record.get("Section", []))


def fetch_pubchem(formulas: list) -> list:
    results = []
    property_headings = {
        "melting_point": "Melting Point",
        "boiling_point": "Boiling Point",
        "density": "Density",
    }
    for formula in formulas:
        cid = _pubchem_cid_for_formula(formula)
        time.sleep(REQUEST_DELAY_SEC)
        if not cid:
            continue
        for internal_key, heading in property_headings.items():
            raw_value = _pubchem_experimental_property(cid, heading)
            time.sleep(REQUEST_DELAY_SEC)
            if not raw_value:
                continue
            url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
            results.append({
                "source": "PubChem",
                "formula": formula,
                "internal_key": internal_key,
                "value": raw_value,  # ACHTUNG: Rohtext, vor QS-Import normalisieren/Einheit parsen!
                "reference": Reference(url=url, note=f"PubChem CID {cid} - Wert unstrukturiert, manuell pruefen"),
            })
    return results


# ---------------------------------------------------------------------------
# Wikidata-Abgleich (wie in cli.py: nur bestehende Items, kein Neuanlegen)
# ---------------------------------------------------------------------------

def find_wikidata_item_by_formula(formula: str) -> Optional[dict]:
    sparql = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item wdt:P274 "{formula}" .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    LIMIT 5
    """
    resp = requests.get(WIKIDATA_SPARQL, params={"query": sparql, "format": "json"}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    if not bindings:
        return None
    if len(bindings) > 1:
        return {"ambiguous": True}
    b = bindings[0]
    qid = b["item"]["value"].rsplit("/", 1)[-1]
    return {"qid": qid, "label": b.get("itemLabel", {}).get("value", qid), "ambiguous": False}


def item_has_statement(qid: str, pid: str) -> bool:
    resp = requests.get(
        WIKIDATA_API,
        params={"action": "wbgetclaims", "entity": qid, "property": pid, "format": "json"},
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return bool(resp.json().get("claims", {}).get(pid))


# ---------------------------------------------------------------------------
# Vorschlaege zusammenstellen
# ---------------------------------------------------------------------------

def build_proposals(raw_entries: list) -> list:
    proposals = []
    formula_cache = {}

    for entry in raw_entries:
        if entry.get("internal_key") not in PROPERTY_MAP:
            continue  # Eintraege ohne nachgeladenen Wert

        formula = entry["formula"]
        if formula not in formula_cache:
            time.sleep(REQUEST_DELAY_SEC)
            formula_cache[formula] = find_wikidata_item_by_formula(formula)
        wd_match = formula_cache[formula]

        if wd_match is None:
            continue
        if wd_match.get("ambiguous"):
            proposals.append({
                "status": "MANUELLE_KLAERUNG_NOETIG (mehrdeutige Formel)",
                "source": entry["source"], "formula": formula,
            })
            continue

        prop_info = PROPERTY_MAP[entry["internal_key"]]
        pid = prop_info["pid"]

        time.sleep(REQUEST_DELAY_SEC)
        already_present = item_has_statement(wd_match["qid"], pid)

        row = {
            "status": "BEREITS_VORHANDEN" if already_present else "VORSCHLAG",
            "source": entry["source"],
            "qid": wd_match["qid"],
            "label": wd_match["label"],
            "property": f"{pid} ({prop_info['label']})",
            "value": entry["value"],
            "formula": formula,
        }
        row.update(entry["reference"].as_table_fields())
        row["_ref_obj"] = entry["reference"]
        row["_pid"] = pid
        proposals.append(row)

    return proposals


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

def _md_zelle(wert) -> str:
    """Ein Wert als Markdown-Tabellenzelle: Pipe maskiert, Zeilenumbruch zu <br>."""
    return (str(wert if wert is not None else "")
            .replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r\n", " ").replace("\n", "<br>").replace("\r", " "))


def write_markdown(proposals: list, path: str) -> None:
    spalten = ["status", "source", "qid", "label", "property", "value", "formula",
               "ref_mode", "ref_doi", "ref_url", "ref_retrieved", "ref_note"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(spalten) + " |\n")
        f.write("|" + "|".join(["---"] * len(spalten)) + "|\n")
        for row in proposals:
            f.write("| " + " | ".join(_md_zelle(row.get(s, "")) for s in spalten)
                    + " |\n")
    print(f"Vorschlagsliste: {path}", file=sys.stderr)


def write_quickstatements_draft(proposals: list, path: str) -> None:
    lines = [
        "# ENTWURF - jede Zeile vor Verwendung manuell pruefen!",
        "# PubChem-Werte sind Rohtext (unstrukturiert) - Einheit/Zahl vor Uebernahme normalisieren.",
    ]
    for row in proposals:
        if row.get("status") != "VORSCHLAG":
            continue
        ref = row["_ref_obj"]
        lines.append(f"{row['qid']}\t{row['_pid']}\t{row['value']}{ref.as_quickstatements()}")
        lines.append(f"# Quelle: {row['source']} ({ref.mode}) - {ref.note}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"QuickStatements-Entwurf: {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formulas", nargs="+", required=True, help="z. B. --formulas TiO2 Fe2O3 NaCl")
    parser.add_argument("--sources", nargs="+", default=["materials_project", "pubchem"],
                         choices=["materials_project", "pubchem"])
    parser.add_argument("--out", default="werkstoffe_vorschlaege.md")
    parser.add_argument("--qs-out", default="werkstoffe_qs_entwurf.txt")
    args = parser.parse_args()

    raw_entries = []
    if "materials_project" in args.sources:
        raw_entries += fetch_materials_project(args.formulas)
    if "pubchem" in args.sources:
        raw_entries += fetch_pubchem(args.formulas)

    proposals = build_proposals(raw_entries)
    write_markdown(proposals, args.out)
    write_quickstatements_draft(proposals, args.qs_out)

    n_vorschlag = sum(1 for p in proposals if p.get("status") == "VORSCHLAG")
    n_doi = sum(1 for p in proposals if p.get("ref_mode") == "DOI" and p.get("status") == "VORSCHLAG")
    n_url = n_vorschlag - n_doi
    print(f"\n{n_vorschlag} Vorschlaege ({n_doi} mit DOI, {n_url} mit URL+Datum-Referenz).", file=sys.stderr)


if __name__ == "__main__":
    main()
