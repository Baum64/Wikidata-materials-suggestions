"""Materials Project -> Wikidata: Vorschlagsgenerator.

Siehe README.md in diesem Verzeichnis. Das Paket schreibt niemals selbst nach
Wikidata; es erzeugt ausschliesslich Vorschlagslisten zur manuellen Pruefung.
"""
from .cli import (
    build_proposals,
    fetch_mp_materials,
    find_wikidata_item_by_formula,
    formula_candidates,
    item_has_statement,
    parse_formula,
    proposals_for_material,
    write_csv,
    write_quickstatements_draft,
)

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
