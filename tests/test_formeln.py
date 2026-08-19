"""Formeln: Normalisierung fuer den Abgleich, Zerlegung fuer P527,
Infobox-Parser. Alles netzwerkfrei."""
import pytest

from materialswiki import cli
from materialswiki.cli import (
    elemente_aus_formel,
    formel_proposals_for_item,
    formula_candidates,
    parse_de_temperature,
    parse_formula,
    wikipedia_en_chem_values,
)


# ===========================================================================
# parse_formula: exakte Stoechiometrie fuer den Item-Abgleich
# ===========================================================================

@pytest.mark.parametrize("formel, erwartet", [
    # Datenbanken schreiben alphabetisch mit ASCII-Ziffern
    ("O2Ti", {"O": 2, "Ti": 1}),
    ("N29O3Ti31", {"N": 29, "O": 3, "Ti": 31}),
    # Wikidata schreibt tiefgestellt
    ("TiO₂", {"Ti": 1, "O": 2}),
    ("C₁₅H₂₂O₃", {"C": 15, "H": 22, "O": 3}),
    # Klammern, auch geschachtelt
    ("Ca(OH)2", {"Ca": 1, "O": 2, "H": 2}),
    ("K4(Fe(CN)6)", {"K": 4, "Fe": 1, "C": 6, "N": 6}),
])
def test_formel_wird_in_zusammensetzung_zerlegt(formel, erwartet):
    assert parse_formula(formel) == erwartet


def test_gleiche_zusammensetzung_egal_wie_geschrieben():
    """Der eigentliche Zweck: O2Ti und TiO₂ (Wikidata) sind dasselbe."""
    assert parse_formula("O2Ti") == parse_formula("TiO₂") == parse_formula("TiO2")


@pytest.mark.parametrize("formel", [
    "CuSO4·5H2O",   # Hydratpunkt
    "SO4^2-",       # Ladung
    "Xx2",          # kein Elementsymbol
    "Ca(OH2",       # Klammer nicht geschlossen
    "Ca)OH(2",      # Klammer falsch herum
    "siehe Text",   # Freitext
    "",
])
def test_undeutbares_wird_verworfen_statt_geraten(formel):
    assert parse_formula(formel) is None


@pytest.mark.parametrize("formel, erwartet, begruendung", [
    # Anorganisch: elektropositiver Partner zuerst - so steht es in Wikidata
    ("O2Ti", "TiO₂", "konventionell"),
    ("O3Al2", "Al₂O₃", "konventionell"),
    # Organisch (C UND H): Hill
    ("C15H22O3", "C₁₅H₂₂O₃", "Hill"),
])
def test_bevorzugte_schreibweise(formel, erwartet, begruendung):
    assert formula_candidates(parse_formula(formel))[0] == erwartet, begruendung


def test_carbid_ist_anorganisch_trotz_kohlenstoff():
    """Regression: Hill haette SiC als 'CSi' geschrieben - in Wikidata
    nicht auffindbar, obwohl das Item existiert."""
    assert "SiC" in formula_candidates(parse_formula("CSi"))
    assert "TiC" in formula_candidates(parse_formula("CTi"))


def test_kandidaten_decken_beide_ziffernarten_ohne_dubletten_ab():
    kandidaten = formula_candidates(parse_formula("O2Ti"))
    assert "TiO₂" in kandidaten and "TiO2" in kandidaten
    # Ohne Ziffern faellt die tief-/normalgestellte Doppelung weg
    assert formula_candidates(parse_formula("NaCl")) == ["NaCl", "ClNa"]


# ===========================================================================
# Infobox-Parser: Temperaturen und Chembox
# ===========================================================================

@pytest.mark.parametrize("roh, kelvin", [
    ("1855 [[Grad Celsius|°C]]", 2128.15),
    ("2900 °C", 3173.15),
    ("1843 K", 1843.0),          # schon Kelvin, nicht umrechnen
    ("1855 °C (2128 K)", 2128.0),  # Kelvin gewinnt
    ("1.234,5 °C", 1507.65),     # deutsches Dezimalkomma
])
def test_celsius_wird_nach_kelvin_umgerechnet(roh, kelvin):
    assert parse_de_temperature(roh) == pytest.approx(kelvin)


@pytest.mark.parametrize("roh", [
    "1843",                       # Einheit fehlt -> 273,15 Unterschied moeglich
    "100–120 °C",                 # Bereich
    "Zersetzung ab 400 °C",       # kein Schmelzpunkt
    "> 300 °C",                   # Ungleichung
    "Graphit: 3800 °C<br />Diamant: 3550 °C",  # mehrere Modifikationen
])
def test_unsichere_temperatur_wird_verworfen(roh):
    assert parse_de_temperature(roh) is None


def test_chembox_einheit_steckt_im_feldnamen():
    """Kelvin-Feld schlaegt Celsius-Feld, damit nicht umgerechnet werden muss;
    die Dichte steht schon in der Zieleinheit g/cm³."""
    werte = wikipedia_en_chem_values(
        {"MeltingPtK": "2116", "MeltingPtC": "1843", "Density": "4.23 g/cm3"})
    assert werte["melting_point"][0] == pytest.approx(2116.0)
    assert werte["density"][0] == pytest.approx(4.23)


def test_chembox_unsinnige_cas_wird_verworfen():
    assert wikipedia_en_chem_values({"CASNo": "siehe Text"}) == {}


# ===========================================================================
# elemente_aus_formel: Elementmenge fuer P527 (toleranter, siehe README)
# ===========================================================================

@pytest.mark.parametrize("formel, erwartet", [
    # Das Vorbild aus Wikidata (Q283): H2O -> H:2, O:1.
    ("H₂O", {"H": 2, "O": 1}),
    ("SiO₂", {"Si": 1, "O": 2}),
    ("NaCl", {"Na": 1, "Cl": 1}),
    # Klammern samt Faktor, mehrfach geschachtelt.
    ("KMg₃(AlSi₃O₁₀)(OH)₂", {"K": 1, "Mg": 3, "Al": 1, "Si": 3,
                             "O": 12, "H": 2}),
    # Hydrat: die Zahl hinter dem Punkt multipliziert NUR das Kristallwasser.
    # 4 O aus dem Sulfat + 5 O aus dem Wasser = 9.
    ("CuSO₄·5H₂O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
    # Hochgestellte Ladungen tragen nichts zur Zusammensetzung bei.
    ("Fe³⁺₂O₃", {"Fe": 2, "O": 3}),
    # ASCII-Ladung: "Te6+" ist eine Oxidationsstufe, kein Index 6.
    ("Cu₂Te⁶⁺O₄(OH)₂", {"Cu": 2, "Te": 1, "O": 6, "H": 2}),
    # Leerstellensymbol markiert eine unbesetzte Gitterposition.
    ("☐Na₂Fe₅Si₈O₂₂(OH)₂", {"Na": 2, "Fe": 5, "Si": 8, "O": 24, "H": 2}),
])
def test_zerlegung_eindeutig(formel, erwartet):
    sicher, unsicher = elemente_aus_formel(formel)
    assert sicher == erwartet
    assert unsicher == set()


# ---------------------------------------------------------------------------
# Mischreihen - der eigentliche Knackpunkt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formel, sicher, unsicher, fall", [
    # (Fe,Mg) heisst Fe ODER Mg - beide zu behaupten waere fuer jedes
    # Endglied der Reihe falsch.
    ("(Fe,Mg)₂SiO₄", {"Si": 1, "O": 4}, {"Fe", "Mg"},
     "Alternativen bleiben aussen vor"),
    # (V⁵⁺,V⁴⁺) nennt zweimal Vanadium - nur die Oxidationsstufe wechselt.
    ("Ca(V⁵⁺,V⁴⁺)₄O₁₀·5H₂O", {"Ca": 1, "V": 4, "O": 15, "H": 10}, set(),
     "gleiches Element in allen Zweigen ist sicher"),
    # Sauerstoff ist durch O₂₀ gesichert; wie viel aus (OH,F) dazukommt, nicht.
    ("Al₁₃Si₅O₂₀(OH,F)₁₈Cl", {"Al": 13, "Si": 5, "O": None, "Cl": 1},
     {"H", "F"}, "ausserhalb der Mischreihe -> Element ja, Anzahl nein"),
    ("(Ni,Fe)", {}, {"Ni", "Fe"}, "reine Mischreihe: kein sicheres Element"),
    # ·nH₂O: dass Wasser drin ist, steht fest, wie viel nicht. Silicium
    # bleibt davon unberuehrt und behaelt seine Anzahl.
    ("SiO₂·nH₂O", {"Si": 1, "O": None, "H": None}, set(),
     "variable Wassermenge"),
    # Gebrochene Indizes gehoeren nicht in P1114 - die Elemente schon.
    ("Ag₁.₁Hg₀.₉", {"Ag": None, "Hg": None}, set(),
     "nichtstoechiometrische Phase"),
])
def test_zerlegung_unterscheidet_sicher_von_moeglich(formel, sicher, unsicher,
                                                     fall):
    assert elemente_aus_formel(formel) == (sicher, unsicher), fall


@pytest.mark.parametrize("formel", [
    "Cu₂₋ₓAlₓ(H₂₋ₓSi₂O₅)(OH)₄",   # Variable im Index
    "Ca(UO₂)₂(PO₄)₂·(10-12)H₂O",   # Bereichsangabe
    "(SiO₃",                        # Klammer nicht geschlossen
    "Xx₂O₃",                        # kein Elementsymbol
    "",
])
def test_nicht_deutbare_formeln(formel):
    assert elemente_aus_formel(formel) is None


# ---------------------------------------------------------------------------
# Vorschlagszeilen
# ---------------------------------------------------------------------------

@pytest.fixture
def elementtabelle(monkeypatch):
    monkeypatch.setattr(cli, "_ELEMENT_QID_CACHE", {
        "H": {"qid": "Q556", "label": "Wasserstoff", "name_en": "hydrogen",
              "title_de": "Wasserstoff"},
        "O": {"qid": "Q629", "label": "Sauerstoff", "name_en": "oxygen",
              "title_de": "Sauerstoff"},
        "Fe": {"qid": "Q677", "label": "Eisen", "name_en": "iron",
               "title_de": "Eisen"},
        "Mg": {"qid": "Q660", "label": "Magnesium", "name_en": "magnesium",
               "title_de": "Magnesium"},
        "Si": {"qid": "Q670", "label": "Silicium", "name_en": "silicon",
               "title_de": "Silicium"},
    })


@pytest.fixture
def item():
    return {"qid": "Q283", "label": "Wasser", "ambiguous": False,
            "title_de": "Wasser", "title_en": "Water"}


def test_vorschlag_je_element_mit_anzahl(monkeypatch, elementtabelle, item):
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)
    zeilen = formel_proposals_for_item(item, "H₂O")

    assert [z["value"] for z in zeilen] == ["Q556", "Q629"]  # sortiert: H, O
    assert all(z["status"] == "VORSCHLAG" for z in zeilen)
    assert all(z["_pid"] == "P527" for z in zeilen)
    assert all(z["source"] == "Formel" for z in zeilen)
    # Anzahl als Qualifikator P1114 - wie am Vorbild Q283.
    assert zeilen[0]["_qualifiers"] == [("P1114", "2", "Anzahl 2")]
    assert zeilen[1]["_qualifiers"] == [("P1114", "1", "Anzahl 1")]


def test_abgeleitete_aussage_geht_ohne_beleg_raus(monkeypatch, elementtabelle,
                                                  item):
    """Es gibt keine externe Quelle - ein 'importiert aus Wikidata' waere
    zirkulaer. Die Herkunft bleibt trotzdem pruefbar in der Notiz."""
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)
    zeile = formel_proposals_for_item(item, "H₂O")[0]

    assert zeile["_ohne_beleg"] is True
    assert zeile["ref_doi"] == ""
    assert zeile["ref_url"] == ""
    assert "H₂O" in zeile["ref_note"]


def test_entwurf_enthaelt_keine_s_angabe(monkeypatch, elementtabelle, item,
                                         tmp_path):
    """Die Probe aufs Exempel: im QuickStatements-Entwurf darf hinter der
    Aussage der Qualifikator stehen, aber kein Beleg-Snak."""
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)
    zeilen = formel_proposals_for_item(item, "H₂O")

    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    aussagen = [z for z in pfad.read_text(encoding="utf-8").splitlines()
                if z.startswith("Q283")]

    assert aussagen == [
        "Q283\tP527\tQ556\tP1114\t2",
        "Q283\tP527\tQ629\tP1114\t1",
    ]


def test_ohne_anzahl_kein_qualifikator(monkeypatch, elementtabelle, item):
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)
    zeilen = formel_proposals_for_item(item, "SiO₂·nH₂O")
    nach_wert = {z["value"]: z for z in zeilen}

    assert nach_wert["Q670"]["_qualifiers"] == [("P1114", "1", "Anzahl 1")]
    assert nach_wert["Q629"]["_qualifiers"] == []
    assert "Anzahl nicht bestimmbar" in nach_wert["Q629"]["ref_note"]


def test_mischreihe_wird_zur_klaerung_ausgewiesen(monkeypatch, elementtabelle,
                                                  item):
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)
    zeilen = formel_proposals_for_item(item, "(Fe,Mg)₂SiO₄")

    vorgeschlagen = {z["value"] for z in zeilen if z["status"] == "VORSCHLAG"}
    assert vorgeschlagen == {"Q670", "Q629"}  # Si und O, nicht Fe/Mg
    klaerung = [z for z in zeilen if "KLAERUNG" in z["status"]]
    assert len(klaerung) == 1
    assert "Eisen" in klaerung[0]["status"]
    assert "Magnesium" in klaerung[0]["status"]


def test_bestehende_p527_wird_nicht_ergaenzt(monkeypatch, elementtabelle,
                                              item):
    """Quarz traegt P527 -> Siliciumdioxid. Elemente danebenzusetzen wuerde
    zwei Modellierungen vermischen."""
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: True)
    zeilen = formel_proposals_for_item(item, "H₂O")

    assert all(z["status"] == "BEREITS_VORHANDEN" for z in zeilen)


def test_keine_zeile_wo_nichts_zu_behaupten_ist(monkeypatch, elementtabelle,
                                                 item):
    """Zwei Gruende, gar nichts zu liefern: die Property ist schon von einer
    frueheren Stufe belegt, oder das Elementsymbol hat kein Wikidata-Item -
    dann wird nicht geraten."""
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)
    assert formel_proposals_for_item(item, "H₂O", skip_pids={"P527"}) == []
    assert formel_proposals_for_item(item, "NaCl") == []  # Na/Cl fehlen
