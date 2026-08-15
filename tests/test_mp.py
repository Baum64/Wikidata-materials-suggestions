"""Materials-Project-Anbindung: Feldabbildung und Einheiten - netzwerkfrei."""
import pytest

from materialswiki.cli import (
    MP_DOI,
    MP_FIELD_MAP,
    PROPERTY_MAP,
    mp_value,
    proposals_for_material,
)


# Ein realistisches MP-Dokument (Feldnamen aus dem OpenAPI-Schema SummaryDoc).
RUTIL = {
    "material_id": "mp-2657",
    "formula_pretty": "TiO2",
    "formula": "TiO2",
    "theoretical": False,
    "is_stable": True,
    "energy_above_hull": 0.0,
    "database_IDs": {"icsd": ["icsd-33837"]},
    "density": 4.24,                       # g/cm^3
    "symmetry": {"crystal_system": "Tetragonal"},
    "bulk_modulus": {"voigt": 216.0, "reuss": 210.0, "vrh": 213.0},   # GPa
    "shear_modulus": {"voigt": 105.0, "reuss": 99.0, "vrh": 102.0},   # GPa
    "homogeneous_poisson": 0.28,
}

WD = {"qid": "Q320603", "label": "Rutil", "ambiguous": False}


@pytest.fixture(autouse=True)
def leeres_item(monkeypatch):
    """Wikidata-Abfrage abklemmen: das Item traegt noch keine Aussage."""
    monkeypatch.setattr("materialswiki.cli.item_has_statement",
                        lambda qid, pid: False)


def nach_pid(rows):
    return {r["_pid"]: r for r in rows}


# --- Einheitenumrechnung, der eigentliche Fallstrick ----------------------

def test_dichte_wird_von_g_pro_cm3_nach_kg_pro_m3_gerechnet():
    """MP liefert g/cm³, Wikidata P2054 erwartet kg/m³."""
    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    assert zeilen["P2054"]["value"] == pytest.approx(4240.0)


def test_moduln_werden_von_gpa_nach_pascal_gerechnet():
    """MP liefert GPa, Wikidata P5668/P5673 erwarten Pascal."""
    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    assert zeilen["P5668"]["value"] == pytest.approx(2.13e11)
    assert zeilen["P5673"]["value"] == pytest.approx(1.02e11)


def test_moduln_nehmen_das_voigt_reuss_hill_mittel():
    """Nicht voigt (216) oder reuss (210), sondern vrh (213)."""
    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    assert zeilen["P5668"]["value"] == pytest.approx(213.0 * 1e9)


def test_poissonzahl_bleibt_dimensionslos():
    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    assert zeilen["P5593"]["value"] == pytest.approx(0.28)
    assert zeilen["P5593"]["unit_qid"] == ""


# --- Kristallsystem -------------------------------------------------------

def test_kristallsystem_wird_trotz_grossschreibung_abgebildet():
    """MP schreibt 'Tetragonal', die value_map fuehrt 'tetragonal'."""
    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    assert zeilen["P556"]["value"] == "Q503601"
    assert zeilen["P556"]["status"] == "VORSCHLAG"


def test_unbekanntes_kristallsystem_wird_nicht_geraten():
    doc = {**RUTIL, "symmetry": {"crystal_system": "Amorph"}}
    zeilen = [r for r in proposals_for_material(doc, WD) if r["_pid"] == "P556"]
    assert "MANUELLE_KLAERUNG_NOETIG" in zeilen[0]["status"]


# --- Beleg ----------------------------------------------------------------

def test_beleg_traegt_datenbank_doi_und_mp_id():
    """Einzelne MP-Materialien haben keine eigene DOI - belegt wird mit der
    Referenzpublikation, identifiziert ueber die mp-ID."""
    zeile = proposals_for_material(RUTIL, WD)[0]
    assert zeile["ref_doi"] == MP_DOI
    assert "mp-2657" in zeile["ref_note"]


def test_beleg_nennt_qualitaetsmerkmale():
    """Beim Durchsehen soll ohne Nachschlagen erkennbar sein, worauf der
    Wert beruht."""
    note = proposals_for_material(RUTIL, WD)[0]["ref_note"]
    assert "experimentell nachgewiesen" in note
    assert "stabil" in note
    assert "icsd-33837" in note


def test_beleg_weist_werte_als_berechnet_aus():
    """MP-Werte sind DFT-Rechnungen, keine Messungen. Bei den elastischen
    Moduln weichen sie 17-41 % vom Handbuchwert ab - das darf beim
    Durchsehen nicht unsichtbar bleiben."""
    for zeile in proposals_for_material(RUTIL, WD):
        assert "berechnet (DFT)" in zeile["ref_note"]


# --- Bestimmungsmethode (P459) -------------------------------------------

def test_jede_mp_aussage_traegt_p459_dft():
    """Der Beleg sagt WOHER der Wert kommt, der Qualifikator WIE er
    bestimmt wurde. Ohne ihn stuende am Wikidata-Item eines Werkstoffs eine
    Rechnung, die wie eine Messung aussieht."""
    from materialswiki.cli import DETERMINATION_PID, DFT_QID

    for zeile in proposals_for_material(RUTIL, WD):
        assert (DETERMINATION_PID, DFT_QID, "Dichtefunktionaltheorie") \
            in zeile["_qualifiers"]


def test_bestimmungsmethode_steht_lesbar_in_der_csv():
    zeile = proposals_for_material(RUTIL, WD)[0]
    assert zeile["bestimmungsmethode"] == \
        "P459=Q1048589 (Dichtefunktionaltheorie)"


def test_qualifikator_landet_vor_dem_beleg_in_quickstatements(tmp_path):
    """QuickStatements V1: Aussage, dann Qualifikatoren (P...), dann Belege
    (S...) - alles in einer Zeile. Steht der Beleg vor dem Qualifikator,
    haengt QuickStatements den Qualifikator an die Referenz statt an die
    Aussage."""
    from materialswiki.cli import write_quickstatements_draft

    zeilen = [r for r in proposals_for_material(RUTIL, WD)
              if r["_pid"] == "P2054"]
    pfad = tmp_path / "e.txt"
    write_quickstatements_draft(zeilen, str(pfad))
    aussage = [z for z in pfad.read_text(encoding="utf-8").splitlines()
               if z.startswith("Q320603")][0]
    felder = aussage.split("\t")
    assert felder[:3] == ["Q320603", "P2054", "4240.0U844211"]
    assert felder[3:5] == ["P459", "Q1048589"]
    assert felder[5].startswith("S")  # Beleg erst danach


def test_wikipedia_werte_bekommen_keine_methode():
    """Literaturwerte: mit welcher Methode sie bestimmt wurden, steht in der
    Infobox nicht - eine Methode zu behaupten waere geraten."""
    from materialswiki.cli import Reference, make_row

    zeile = make_row(
        "VORSCHLAG", "Wikipedia (de)", WD, PROPERTY_MAP["density"],
        4230.0, "", Reference(imported_from="Q48183",
                              import_url="https://de.wikipedia.org/x"),
    )
    assert zeile["_qualifiers"] == []
    assert zeile["bestimmungsmethode"] == ""


# --- Paginierung ----------------------------------------------------------

class FakeResponse:
    status_code = 200
    ok = True

    def __init__(self, docs):
        self._docs = docs

    def json(self):
        return {"data": self._docs, "meta": {"max_limit": 1000}}


def test_mehr_als_eine_seite_wird_nachgeholt(monkeypatch):
    """Regression: frueher stand hier min(max_entries, 100). Die API liefert
    dann klaglos 100 Dokumente statt der angeforderten 250 - man merkt es
    nicht, die Ausbeute ist einfach still gedeckelt."""
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "test")
    monkeypatch.setattr(cli, "MP_MAX_LIMIT", 100)  # kleine Seiten erzwingen
    gesehen = []

    def fake(method, url, **kw):
        p = kw["params"]
        gesehen.append((p["_skip"], p["_limit"]))
        start = p["_skip"]
        return FakeResponse([
            {"material_id": f"mp-{i}", "formula_pretty": "TiO2"}
            for i in range(start, start + p["_limit"])
        ])

    monkeypatch.setattr(cli, "request_with_retry", fake)
    mats = cli.fetch_mp_materials(["Ti"], 250)

    assert len(mats) == 250
    assert len({m["material_id"] for m in mats}) == 250  # keine Dubletten
    assert gesehen == [(0, 100), (100, 100), (200, 50)]


def test_kurze_seite_beendet_die_schleife(monkeypatch):
    """Weniger Treffer als angefordert: nicht endlos weiterfragen."""
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "test")
    aufrufe = []

    def fake(method, url, **kw):
        aufrufe.append(kw["params"]["_skip"])
        return FakeResponse([
            {"material_id": "mp-1", "formula_pretty": "TiO2"},
            {"material_id": "mp-2", "formula_pretty": "TiO2"},
        ])

    monkeypatch.setattr(cli, "request_with_retry", fake)
    assert len(cli.fetch_mp_materials(["Ti"], 500)) == 2
    assert aufrufe == [0]  # genau eine Anfrage


# --- User-Agent -----------------------------------------------------------

def test_mp_user_agent_enthaelt_kein_bot():
    """Regression: die MP-WAF antwortet auf jede Kennung mit 'Bot' im Namen
    mit HTTP 403 - noch bevor sie den API-Schluessel prueft. Der
    Wikimedia-User-Agent traegt 'Bot' und muss das auch; fuer MP braucht es
    deshalb eine eigene Kennung."""
    from materialswiki.cli import MP_USER_AGENT, USER_AGENT

    assert "bot" not in MP_USER_AGENT.lower(), MP_USER_AGENT
    assert "Bot" in USER_AGENT  # Wikimedia-Richtlinie, bleibt so
    assert MP_USER_AGENT != USER_AGENT


def test_mp_header_setzt_schluessel_und_eigene_kennung(monkeypatch):
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "testschluessel")
    kopf = cli.mp_headers()
    assert kopf["X-API-KEY"] == "testschluessel"
    assert "bot" not in kopf["User-Agent"].lower()


def test_fehlender_schluessel_meldet_sich_verstaendlich(monkeypatch):
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "")
    with pytest.raises(cli.MissingApiKey, match="MP_API_KEY"):
        cli.mp_headers()


# --- Robustheit -----------------------------------------------------------

def test_fehlende_felder_erzeugen_keine_zeilen():
    mager = {"material_id": "mp-1", "formula_pretty": "XY", "formula": "XY"}
    assert proposals_for_material(mager, WD) == []


def test_nichtzahlen_werden_verworfen_statt_gedeutet():
    assert mp_value("keine Zahl", 1000.0) is None
    assert mp_value(None, 1000.0) is None
    assert mp_value(True, 1000.0) is None


# --- Konsistenz der Abbildung --------------------------------------------

def test_jeder_mp_pfad_zeigt_auf_eine_bekannte_property():
    """Ein Tippfehler im Schluessel wuerde die Groesse still verschwinden
    lassen - hier faellt er auf."""
    for pfad, (schluessel, _) in MP_FIELD_MAP.items():
        assert schluessel in PROPERTY_MAP, f"{pfad} -> unbekannt: {schluessel}"


def test_itemwertige_groessen_haben_keinen_faktor():
    for pfad, (schluessel, faktor) in MP_FIELD_MAP.items():
        ist_item = PROPERTY_MAP[schluessel].get("datatype") == "item"
        assert ist_item == (faktor is None), f"{pfad}: Faktor passt nicht zum Typ"
