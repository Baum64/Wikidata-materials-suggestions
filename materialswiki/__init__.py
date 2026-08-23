"""Materials Project -> Wikidata: Vorschlagsgenerator.

Siehe README.md in diesem Verzeichnis. Das Paket schreibt niemals selbst nach
Wikidata; es erzeugt ausschliesslich Vorschlagslisten zur manuellen Pruefung.

Der Code liegt in Schichten, die einzeln ladbar sind - wer nur Formeln
zerlegen will, braucht weder Netz noch Wikidata:

    konfiguration  Kennungen, Endpunkte, Schluessel aus .env
    netz           HTTP: Drosselung je Gegenstelle, Retry
    properties     Property-Tabellen, Einheiten, Plausibilitaetsschranken
    formeln        Summenformeln zerlegen und schreiben
    ausgabe        Referenzmodell, Vorschlagszeile, CSV und QuickStatements
    wikidata       Vokabular und Itemzustand aus Wikidata
    cli            Quellenstufen, Ableitungen, Kaskade, Kommandozeile
"""
from .ausgabe import write_csv, write_quickstatements_draft
from .cli import build_proposals, fetch_mp_materials, proposals_for_material
from .formeln import formula_candidates, parse_formula
from .wikidata import find_wikidata_item_by_formula, item_has_statement

__all__ = [
    "build_proposals",
    "fetch_mp_materials",
    "find_wikidata_item_by_formula",
    "formula_candidates",
    "item_has_statement",
    "parse_formula",
    "proposals_for_material",
    "write_csv",
    "write_quickstatements_draft",
]
