"""Punktgruppe (P589) aus der Raumgruppe und Laengenausdehnungskoeffizient
(P5672) aus der englischen Elementinfobox. Alles netzwerkfrei."""
import pytest

from materialswiki import cli, wikidata
from materialswiki.cli import (
    parse_thermal_expansion,
    punktgruppe_proposals_for_item,
    waermeausdehnung_proposals_for_item,
)

# Raumgruppe 194 (P6_3/mmc, Graphit) -> Punktgruppe 6/mmm.
RAUMGRUPPEN = {
    194: {"qid": "Q15042088", "label": "Raumgruppe 194",
          "cs_qid": "Q663314", "cs_label": "hexagonal",
          "pg_qid": "Q13362368", "pg_label": "Dihexagonal-dipyramidal"},
    225: {"qid": "Q15041891", "label": "Raumgruppe 225",
          "cs_qid": "Q473227", "cs_label": "kubisch",
          "pg_qid": "", "pg_label": ""},
}


@pytest.fixture
def item():
    return {"qid": "Q5309", "label": "Graphit", "ambiguous": False,
            "title_de": "Graphit", "title_en": "Graphite"}


@pytest.fixture(autouse=True)
def tabelle(monkeypatch):
    monkeypatch.setattr(wikidata, "fetch_space_group_qids", lambda: RAUMGRUPPEN)
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: False)


def setze_raumgruppen(qid, sg_qids):
    wikidata._ITEM_RAUMGRUPPE_CACHE[qid] = list(sg_qids)


# ===========================================================================
# P589: nachgeschlagen, nicht abgeleitet
# ===========================================================================

def test_punktgruppe_kommt_vom_raumgruppen_item(item):
    setze_raumgruppen("Q5309", ["Q15042088"])
    zeilen = punktgruppe_proposals_for_item(item)

    assert len(zeilen) == 1
    assert zeilen[0]["status"] == "VORSCHLAG"
    assert zeilen[0]["_pid"] == "P589"
    assert zeilen[0]["value"] == "Q13362368"
    assert zeilen[0]["source"] == "Raumgruppe"


def test_nachschlagen_geht_ohne_beleg_raus(item):
    """Der Wert steht schon am Item, nur in einer anderen Property - es gibt
    keine externe Quelle, die man zitieren koennte."""
    setze_raumgruppen("Q5309", ["Q15042088"])
    zeile = punktgruppe_proposals_for_item(item)[0]

    assert zeile["_ohne_beleg"] is True
    assert zeile["ref_doi"] == ""
    assert "Raumgruppe 194" in zeile["ref_note"]


def test_ohne_raumgruppe_am_item_keine_zeile(item):
    setze_raumgruppen("Q5309", [])
    assert punktgruppe_proposals_for_item(item) == []


def test_mehrere_raumgruppen_werden_zur_klaerung_ausgewiesen(item):
    """56 Items tragen mehr als eine Raumgruppe - meist mehrere
    Modifikationen. Welche gemeint ist, entscheidet die Fachfrage."""
    setze_raumgruppen("Q5309", ["Q15042088", "Q15041891"])
    zeilen = punktgruppe_proposals_for_item(item)

    assert len(zeilen) == 1
    assert zeilen[0]["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert "Raumgruppe 194" in zeilen[0]["status"]
    assert zeilen[0]["value"] == ""


def test_raumgruppe_ohne_punktgruppe_ergibt_nichts(item):
    """Sechs der 236 Raumgruppen-Items fuehren keine Punktgruppe - dann wird
    nicht geraten."""
    setze_raumgruppen("Q5309", ["Q15041891"])
    assert punktgruppe_proposals_for_item(item) == []


def test_belegte_property_wird_uebersprungen(item):
    setze_raumgruppen("Q5309", ["Q15042088"])
    assert punktgruppe_proposals_for_item(item, skip_pids={"P589"}) == []


def test_bestehende_punktgruppe_wird_nicht_ergaenzt(monkeypatch, item):
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: True)
    setze_raumgruppen("Q5309", ["Q15042088"])
    zeilen = punktgruppe_proposals_for_item(item)

    assert [z["status"] for z in zeilen] == ["BEREITS_VORHANDEN"]


# ===========================================================================
# P5672: Wert und Temperatur aus der Infobox
# ===========================================================================

KUPFER = {"thermal expansion comment":
          '{{val|16.64|e=−6}}/K (at&nbsp;20&nbsp;°C)<ref name="Arblaster" />'}
TITAN = {"thermal expansion comment":
         "{{val|9.68|e=−6}}/K (at&nbsp;20&nbsp;°C){{efn|text=The thermal "
         "expansion is [[Anisotropy|anisotropic]]: ...}}"}


@pytest.mark.parametrize("felder, erwartet", [
    # Regelform der heutigen Vorlagen
    (KUPFER, (16.64, 20.0, False)),
    # Aeltere Vorlagen: Zahl schon in um/(m*K), Temperatur im Feldnamen
    ({"thermal expansion at 25": "60.4"}, (60.4, 25.0, False)),
    # Iridium schreibt die Einheit in die Vorlage
    ({"thermal expansion comment":
      '{{val|6.47|e=−6|u=K<sup>−1</sup>}} (at&nbsp;20&nbsp;°C)'},
     (6.47, 20.0, False)),
    # Anisotrop: Wert ist das Mittel alpha_V/3
    (TITAN, (9.68, 20.0, True)),
])
def test_infoboxformen_werden_gelesen(felder, erwartet):
    assert parse_thermal_expansion(felder) == erwartet


@pytest.mark.parametrize("felder", [
    # "Raumtemperatur" ist keine Temperaturangabe, mit der man rechnen darf
    {"thermal expansion comment": "(at&nbsp;{{abbr|r.t.|room temperature}})"},
    # Wert einer Modifikation, nicht des Stoffs
    {"thermal expansion at 25": "diamond: 0.8"},
    {"thermal expansion at 25": "β form: 5–7"},
    {},
])
def test_unbestimmtes_wird_verworfen(felder):
    assert parse_thermal_expansion(felder) is None


@pytest.fixture
def kupfer_item():
    return {"qid": "Q753", "label": "Kupfer", "ambiguous": False}


@pytest.fixture(autouse=True)
def kein_gas(monkeypatch):
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: False)


def test_ausdehnung_traegt_ihre_temperatur(kupfer_item):
    zeilen = waermeausdehnung_proposals_for_item(
        kupfer_item, KUPFER, "https://en.wikipedia.org/x", "", set())

    assert len(zeilen) == 1
    assert zeilen[0]["_pid"] == "P5672"
    assert zeilen[0]["value"] == pytest.approx(16.64)
    assert zeilen[0]["unit_qid"] == "Q56025776"     # um/(m*K)
    assert zeilen[0]["_qualifiers"] == [("P2076", "20U25267", "20 °C")]


def test_anisotrope_ausdehnung_wird_zur_klaerung_ausgewiesen(kupfer_item):
    """Bei anisotropen Kristallen haengt der Koeffizient von der Achse ab;
    die Infobox nennt das Mittel. Ein einzelner Wert waere eine Halbwahrheit."""
    zeilen = waermeausdehnung_proposals_for_item(
        kupfer_item, TITAN, "https://en.wikipedia.org/x", "", set())

    assert zeilen[0]["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert "anisotrop" in zeilen[0]["status"]


def test_gase_bekommen_keinen_festkoerperwert(monkeypatch, kupfer_item):
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: True)
    assert waermeausdehnung_proposals_for_item(
        kupfer_item, KUPFER, "https://en.wikipedia.org/x", "", set()) == []


def test_unplausibler_wert_wird_nicht_vorgeschlagen(kupfer_item):
    felder = {"thermal expansion comment":
              '{{val|850.0|e=−6}}/K (at&nbsp;20&nbsp;°C)'}
    assert waermeausdehnung_proposals_for_item(
        kupfer_item, felder, "https://en.wikipedia.org/x", "", set()) == []


def test_entwurfszeile_traegt_einheit_und_temperatur(kupfer_item, tmp_path):
    zeilen = waermeausdehnung_proposals_for_item(
        kupfer_item, KUPFER, "https://en.wikipedia.org/x", "", set())
    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    aussage = [z for z in pfad.read_text(encoding="utf-8").splitlines()
               if z.startswith("Q753")][0]

    assert aussage.split("\t")[:5] == [
        "Q753", "P5672", "16.64U56025776", "P2076", "20U25267"]
