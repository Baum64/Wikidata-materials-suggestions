"""Formel-Normalisierung und Infobox-Parser - alles netzwerkfrei."""
import pytest

from materialswiki.cli import (
    formula_candidates,
    parse_de_temperature,
    parse_formula,
    wikipedia_en_chem_values,
)


# --- parse_formula --------------------------------------------------------

@pytest.mark.parametrize("formel, erwartet", [
    # NOMAD schreibt alphabetisch mit ASCII-Ziffern
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
    """Der eigentliche Zweck: O2Ti (NOMAD) und TiO₂ (Wikidata) sind dasselbe."""
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


# --- formula_candidates ---------------------------------------------------

def test_anorganisch_wird_konventionell_geschrieben():
    """Elektropositiver Partner zuerst - so steht es in Wikidata."""
    assert formula_candidates(parse_formula("O2Ti"))[0] == "TiO₂"
    assert formula_candidates(parse_formula("O3Al2"))[0] == "Al₂O₃"


def test_organisch_wird_in_hill_geschrieben():
    assert formula_candidates(parse_formula("C15H22O3"))[0] == "C₁₅H₂₂O₃"


def test_carbid_ist_anorganisch_trotz_kohlenstoff():
    """Regression: Hill haette SiC als 'CSi' geschrieben - in Wikidata
    nicht auffindbar, obwohl das Item existiert."""
    assert "SiC" in formula_candidates(parse_formula("CSi"))
    assert "TiC" in formula_candidates(parse_formula("CTi"))


def test_kandidaten_enthalten_beide_ziffernarten():
    kandidaten = formula_candidates(parse_formula("O2Ti"))
    assert "TiO₂" in kandidaten and "TiO2" in kandidaten


def test_ohne_ziffern_keine_doppelten_kandidaten():
    assert formula_candidates(parse_formula("NaCl")) == ["NaCl", "ClNa"]


# --- Temperaturen aus der Verbindungsinfobox ------------------------------

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


# --- Chembox (englische Verbindungsinfobox) -------------------------------

def test_chembox_kelvin_schlaegt_celsius():
    werte = wikipedia_en_chem_values({"MeltingPtK": "2116", "MeltingPtC": "1843"})
    assert werte["melting_point"][0] == pytest.approx(2116.0)


def test_chembox_dichte_wird_in_kg_pro_kubikmeter_umgerechnet():
    werte = wikipedia_en_chem_values({"Density": "4.23 g/cm3"})
    assert werte["density"][0] == pytest.approx(4230.0)


def test_chembox_unsinnige_cas_wird_verworfen():
    assert wikipedia_en_chem_values({"CASNo": "siehe Text"}) == {}
