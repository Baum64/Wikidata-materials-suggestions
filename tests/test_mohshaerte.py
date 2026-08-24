"""Mohshaerte (P1088) aus den Wikipedia-Infoboxen. Alles netzwerkfrei.

Das Feld heisst in {{Infobox Chemisches Element}} und in {{Infobox Mineral}}
gleich ("Mohshärte"), in der englischen Elementvorlage "Mohs hardness".
Gemessen am 2026-08-23 fuehren es alle 60 Artikel einer Mineral-Stichprobe -
aber nur 20 davon mit EINEM Wert; der Rest nennt einen Bereich ("2 bis 3")
oder gar keine Zahl ("nicht definiert"). Genau diese Faelle stehen unten.
"""
import pytest

from materialswiki import infobox, wikidata
from materialswiki.cli import (
    PROPERTY_MAP, parse_de_number, quickstatements_value, wikipedia_de_values,
    wikipedia_values,
)


@pytest.fixture
def item():
    return {"qid": "Q41302", "label": "Quarz", "ambiguous": False,
            "title_de": "Quarz", "title_en": "Quartz"}


@pytest.fixture(autouse=True)
def bestand(monkeypatch):
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: False)
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: False)


# ---------------------------------------------------------------------------
# Was die Infoboxen wirklich schreiben
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("roh, erwartet", [
    ("3,0", 3.0),                                   # Kupfer, Elementinfobox
    ("7", 7.0),                                     # Quarz, Infobox Mineral
    ('7<ref name="Bačík et al. 2013" />', 7.0),     # Oxy-Schoerl
    ("4,5", 4.5),                                   # Rappoldit
    ("≈&nbsp;5<ref name='x' />", 5.0),              # Oxycalciopyrochlor
    ("2 bis 3", None),                              # Bereich - Saleeit
    ("6,5 bis 7", None),                            # Anduoit
    ("''nicht definiert''", None),                  # Avogadrit
    ("nicht bestimmt", None),                       # Protoenstatit
    ("geschätzt: 5<ref name='x' />", None),         # Ezochiit, beschriftet
    ("6 bis 6,5 (2 wenn massiv)", None),            # Pyrolusit
])
def test_deutsches_feld(roh, erwartet):
    assert parse_de_number(roh) == erwartet


def test_feldkarte_greift_fuer_element_und_mineral():
    """Ein Eintrag, zwei Vorlagen - die Feldnamen sind identisch."""
    for roh in ("3,0", "7"):
        werte = wikipedia_de_values({"Mohshärte": roh})
        assert werte["mohs_hardness"][0] == float(roh.replace(",", "."))


@pytest.mark.parametrize("roh, erwartet", [
    ("3.0", 3.0),          # Template:Infobox copper
    ("2.5", 2.5),          # Template:Infobox gold
    ("2.5–3", None),       # Bereich mit Gedankenstrich
])
def test_englisches_feld(roh, erwartet):
    werte = wikipedia_values({"Mohs hardness": roh})
    assert werte.get("mohs_hardness", (None,))[0] == erwartet


# ---------------------------------------------------------------------------
# Die fertige Zeile
# ---------------------------------------------------------------------------

def zeilen_zu(roh, item, monkeypatch):
    monkeypatch.setattr(
        infobox, "fetch_de_wikipedia_infobox",
        lambda titel: ({"Mohshärte": roh}, "https://de.wikipedia.org/x", ""),
    )
    return infobox.wikipedia_de_proposals_for_item(item, item["title_de"], set())


def test_zeile_traegt_p1088_ohne_einheit(item, monkeypatch):
    """P1088 laesst laut Constraint nur die Einheit '1' zu - im Entwurf
    steht deshalb die blanke Zahl, kein 'U...'."""
    zeile = zeilen_zu("7", item, monkeypatch)[0]

    assert zeile["status"] == "VORSCHLAG"
    assert zeile["_pid"] == "P1088"
    assert zeile["value"] == 7.0
    assert quickstatements_value(zeile) == "7.0"  # ohne "U...", also einheitenlos


def test_unter_der_skala_kommt_in_die_klaerung(item, monkeypatch):
    """Caesium steht mit 0,2 in der Infobox - ein richtiger Wert, den P1088
    wegen seines Bereichs-Constraints (1..10) trotzdem nicht annimmt. Er
    wird ausgewiesen, nicht verworfen."""
    zeile = zeilen_zu("0,2", item, monkeypatch)[0]

    assert zeile["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert zeile["value"] == 0.2


def test_diamant_darf_die_10_haben(item, monkeypatch):
    zeile = zeilen_zu("10", item, monkeypatch)[0]
    assert zeile["status"] == "VORSCHLAG"


def test_am_gas_gibt_es_keine_haerte(item, monkeypatch):
    """Haerte ist eine Festkoerpergroesse - siehe NUR_FESTKOERPER."""
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: True)
    assert zeilen_zu("7", item, monkeypatch) == []


def test_property_steht_im_benchmark_snapshot():
    """P1088 steht seit dem 2026-08-23 unter 'Mechanical' auf der
    Projektseite; die Feldkarten bedienen genau diese PID."""
    import json
    import os

    pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "benchmark", "properties_snapshot.json")
    with open(pfad, encoding="utf-8") as f:
        snapshot = json.load(f)

    assert PROPERTY_MAP["mohs_hardness"]["pid"] == "P1088"
    assert "P1088" in snapshot["Mechanical"]
