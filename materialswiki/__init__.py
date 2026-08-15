"""NOMAD -> Wikidata: Vorschlagsgenerator.

Siehe README.md in diesem Verzeichnis. Das Paket schreibt niemals selbst nach
Wikidata; es erzeugt ausschliesslich Vorschlagslisten zur manuellen Pruefung.
"""
from .cli import (
    build_proposals,
    fetch_entry_values,
    fetch_nomad_entries_with_doi,
    find_wikidata_item_by_formula,
    item_has_statement,
    write_csv,
    write_quickstatements_draft,
)

__all__ = [
    "build_proposals",
    "fetch_entry_values",
    "fetch_nomad_entries_with_doi",
    "find_wikidata_item_by_formula",
    "item_has_statement",
    "write_csv",
    "write_quickstatements_draft",
]
