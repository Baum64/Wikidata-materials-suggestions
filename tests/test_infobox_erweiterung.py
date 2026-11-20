"""Erweiterte Infobox-Feldkarten (2026-11-20). Alles netzwerkfrei.

Neu bedient: Schmelz- und Verdampfungswaerme (P2066/P2116), Phasenpunkte
(P873), Dampfdruck (P2119), molares Volumen (P2807), Elektronegativitaet
(P1108), erste Ionisierungsenergie (P2260), die drei Radien
(P14936/P14937/P14938), E-Modul (P5480), Temperaturleitfaehigkeit (P5674),
EG- und ECHA-Nummer (P232/P2566) sowie aus der en-Vorlage die gemessenen
Kompressions-/Schubmoduln und die Poissonzahl.

Die Rohwerte unten sind an den echten Vorlagen abgelesen (Eisen, Natrium,
Wasserstoff, Stickstoff, Beryllium) - genau diese Schreibweisen muessen
die Parser verkraften.
"""
import pytest

from materialswiki import infobox, wikidata
from materialswiki.cli import (
    PROPERTY_MAP, STUFEN_PIDS, parse_de_number, parse_phasenpunkte,
    parse_wiki_number, phasenpunkt_proposals_for_item, pflicht_qualifikatoren,
    wikipedia_de_values, wikipedia_values, write_quickstatements_draft,
)

EISEN = {"qid": "Q677", "label": "Eisen", "ambiguous": False}
STICKSTOFF = {"qid": "Q627", "label": "Stickstoff", "ambiguous": False}
WASSERSTOFF = {"qid": "Q556", "label": "Wasserstoff", "ambiguous": False}

EISEN_DE = {
    "Schmelzpunkt_K": "1811",
    "Siedepunkt_K": "3134",
    "Schmelzwärme": "13,8",
    "Verdampfungswärme": '354 kJ·mol<sup>−1</sup><ref name="Zhang" />',
    "Elektronegativität": "1,83",
    "Atomradius": "140",
    "KovalenterRadius": "low-spin: 123 pm, high-spin: 152",
    "MolaresVolumen": "7,09·10<sup>−6</sup>",
    "EG-Nummer": "231-096-4",
    "ECHA-ID": "100.028.270",
    "Dampfdruck": "",
    "RefTempDampfdruck_K": "",
}

EISEN_EN = {
    "melting point K": "1811",
    "boiling point K": "3134",
    "heat fusion": "13.81",
    "heat vaporization": "340",
    "electronegativity": "1.83",
    "ionization energy 1": "762.5",
    "atomic radius": "126",
    "covalent radius": "Low spin: 132±3 pm<br/>High spin: 152±6",
    "Van der Waals radius": "194 [https://periodic.lanl.gov/26.shtml]",
    "Young's modulus": "211",
    "Shear modulus": "82",
    "Bulk modulus": "170",
    "Poisson ratio": "0.29",
}

WASSERSTOFF_EN = {
    "triple point K": "13.8033",
    "triple point kPa": "7.041",
    "critical point K": '33.19<ref name="SVA2017">{{cite book|doi=10.1000/sva}}</ref>',
    "critical point MPa": '1.313<ref name="SVA2017" />',
}
WASSERSTOFF_ARTIKEL = ('| critical point K = 33.19<ref name="SVA2017">'
                       '{{cite book|doi=10.1000/sva}}</ref>')


@pytest.fixture(autouse=True)
def bestand(monkeypatch):
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: False)
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: False)
    monkeypatch.setattr(wikidata, "item_hat_merkmal", lambda qid, ziel: False)


def zeilen_de(match, fields):
    return infobox._infobox_proposals(
        match, wikipedia_de_values(fields), set(),
        "Wikipedia (de)", "Q48183", "https://de.wikipedia.org/w/index.php?oldid=1")


def zeilen_en(match, fields):
    return infobox._infobox_proposals(
        match, wikipedia_values(fields), set(),
        "Wikipedia (en)", "Q328", "https://en.wikipedia.org/w/index.php?oldid=1")


def je_pid(zeilen):
    return {z["_pid"]: z for z in zeilen}


def qs_text(tmp_path, zeilen):
    pfad = tmp_path / "qs.txt"
    write_quickstatements_draft(zeilen, str(pfad))
    return pfad.read_text(encoding="utf-8")


# ===========================================================================
# Zahlschreibweisen
# ===========================================================================

@pytest.mark.parametrize("roh, erwartet", [
    ('354 kJ·mol<sup>−1</sup><ref name="Zhang" />', 354.0),   # Eisen
    ("127,6&nbsp;kJ/mol<ref name=\"NIST\"/>", 127.6),          # Lithium
    ("7,09·10<sup>−6</sup>", 7.09e-6),                          # Eisen
    ("4,85&#8239;·&#8239;10<sup>−6</sup>", 4.85e-6),            # Beryllium
    ("102,5", 102.5),                                           # Schwefel
    # verworfen: Modifikation, Aggregatzustand vor der Zahl, Bereich
    ("(fest) 21,00&nbsp;·&nbsp;10<sup>−6</sup>", None),         # Helium
    ("[[Sublimation (Physik)|Sublimation]]: 715 kJ·mol<sup>−1</sup>", None),
    ("low-spin: 123 pm, high-spin: 152", None),
])
def test_deutsche_schreibweisen(roh, erwartet):
    wert = parse_de_number(roh)
    if erwartet is None:
        assert wert is None
    else:
        assert wert == pytest.approx(erwartet)


@pytest.mark.parametrize("roh, erwartet", [
    ("31±5", 31.0),                                     # Wasserstoff, kovalent
    ("194 [https://periodic.lanl.gov/26.shtml]", 194.0),  # Eisen, vdW
    ("10,800", 10800.0),                                # Kohlenstoff, Tripelpunkt kPa
    ("(N<sub>2</sub>) 0.72", None),                     # Molekuelbezug
    ("diamond: 1050", None),                            # Modifikation
    ("130–188", None),                                  # Bereich
    ("4.9{{dubious|reason=x}}", None),                  # Restvorlage
])
def test_englische_schreibweisen(roh, erwartet):
    assert parse_wiki_number(roh) == erwartet


# ===========================================================================
# Feldkarten: was aus den Vorlagen herauskommt
# ===========================================================================

def test_deutsche_elementinfobox_liefert_die_neuen_groessen():
    werte = wikipedia_de_values(EISEN_DE)
    assert werte["molar_fusion_enthalpy"][0] == 13.8
    assert werte["molar_vaporization_enthalpy"][0] == 354.0
    assert werte["electronegativity"][0] == 1.83
    assert werte["atomic_radius"][0] == 140.0
    assert werte["molar_volume"][0] == pytest.approx(7.09e-6)
    assert werte["ec_number"][0] == "231-096-4"
    assert werte["echa_infocard"][0] == "100.028.270"
    # mehrdeutig (zwei Spinzustaende) -> nichts
    assert "covalent_radius" not in werte
    # leerer Dampfdruck -> nichts
    assert "vapor_pressure" not in werte


def test_englische_elementinfobox_liefert_die_neuen_groessen():
    werte = wikipedia_values(EISEN_EN)
    assert werte["molar_fusion_enthalpy"][0] == 13.81
    assert werte["ionization_energy"][0] == 762.5
    assert werte["van_der_waals_radius"][0] == 194.0
    assert werte["tensile_modulus"][0] == 211.0
    assert werte["shear_modulus"][0] == 82.0
    assert werte["bulk_modulus"][0] == 170.0
    assert werte["poisson_ratio"][0] == 0.29
    assert "covalent_radius" not in werte


@pytest.mark.parametrize("feld, roh", [
    ("EG-Nummer", "{{EG-Nummer|231-096-4}}"),
    ("EG-Nummer", "231-096-4, 231-097-1"),
    ("ECHA-ID", "100.028"),
])
def test_kennungen_nur_im_exakten_format(feld, roh):
    werte = wikipedia_de_values({feld: roh})
    assert "ec_number" not in werte and "echa_infocard" not in werte


# ===========================================================================
# Pflicht-Qualifikatoren
# ===========================================================================

def test_schmelzwaerme_traegt_den_schmelzpunkt(tmp_path):
    """P2066 verlangt P2076 - die Temperatur ist der Schmelzpunkt derselben
    Infobox, in Kelvin."""
    zeile = je_pid(zeilen_de(EISEN, EISEN_DE))["P2066"]
    assert zeile["status"] == "VORSCHLAG"
    assert zeile["_qualifiers"][0][:2] == ("P2076", "1811U11579")

    qs = qs_text(tmp_path, [zeile])
    assert "Q677\tP2066\t13.8U752197\tP2076\t1811U11579\tS143\tQ48183" in qs


def test_verdampfungswaerme_traegt_den_siedepunkt():
    zeile = je_pid(zeilen_de(EISEN, EISEN_DE))["P2116"]
    assert zeile["status"] == "VORSCHLAG"
    assert zeile["_qualifiers"][0][:2] == ("P2076", "3134U11579")


def test_ohne_schmelzpunkt_keine_aussage_sondern_klaerung():
    felder = dict(EISEN_DE, Schmelzpunkt_K="")
    zeile = je_pid(zeilen_de(EISEN, felder))["P2066"]
    assert zeile["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert "P2076" in zeile["status"]


def test_molekulare_elemente_gehen_in_die_klaerung():
    """de fuehrt die Schmelzwaerme des Stickstoffs pro Atom (0,36), en pro
    N2 (0,72) - der Molbezug ist nicht entscheidbar."""
    felder = {"Schmelzpunkt_K": "63,15", "Siedepunkt_K": "77,35",
              "Schmelzwärme": "0,36",
              "Verdampfungswärme": "5,58 kJ·mol<sup>−1</sup>",
              "Elektronegativität": "3,04"}
    zeilen = je_pid(zeilen_de(STICKSTOFF, felder))
    for pid in ("P2066", "P2116"):
        assert zeilen[pid]["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
        assert "N2" in zeilen[pid]["status"]
    # Atomare Groessen sind davon nicht betroffen
    assert zeilen["P1108"]["status"] == "VORSCHLAG"


def test_molbezug_nur_fuer_die_enthalpien():
    qualifier, klaerung, _ = pflicht_qualifikatoren(
        "electronegativity", {}, "Q627")
    assert (qualifier, klaerung) == ([], None)


def test_ionisierungsenergie_traegt_die_seriennummer(tmp_path):
    zeile = je_pid(zeilen_en(EISEN, EISEN_EN))["P2260"]
    assert zeile["status"] == "VORSCHLAG"
    qs = qs_text(tmp_path, [zeile])
    assert 'Q677\tP2260\t762.5U752197\tP1545\t"1"\tS143\tQ328' in qs


def test_e_modul_bekommt_raumtemperatur_mit_hinweis():
    """P5480 verlangt P2076, die Vorlage nennt keine Temperatur - 20 °C wie
    bei der Dichte, und das steht ausdruecklich in der Notiz."""
    zeile = je_pid(zeilen_en(EISEN, EISEN_EN))["P5480"]
    assert zeile["_qualifiers"] == [("P2076", "20U25267", "20 °C")]
    assert "20 °C angenommen" in zeile["ref_note"]


def test_e_modul_und_molares_volumen_nicht_an_gasen(monkeypatch):
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: True)
    pids = set(je_pid(zeilen_en(EISEN, EISEN_EN))) | set(
        je_pid(zeilen_de(EISEN, EISEN_DE)))
    assert "P5480" not in pids and "P2807" not in pids
    assert "P1108" in pids  # atomare Groesse bleibt


def test_dampfdruck_nur_mit_bezugstemperatur(tmp_path):
    felder = {"Dampfdruck": "1",
              "RefTempDampfdruck_K": ("554<ref name=\"crc\">David R. Lide: "
                                      "CRC Handbook. ISBN 0-8493-0484-9.</ref>")}
    zeile = je_pid(zeilen_de({"qid": "Q658", "label": "Natrium"}, felder))["P2119"]
    assert zeile["status"] == "VORSCHLAG"
    # Der Beleg steht am Temperaturfeld - er wird trotzdem gefunden.
    assert zeile["ref_isbn"] == "0-8493-0484-9"
    qs = qs_text(tmp_path, [zeile])
    assert "Q658\tP2119\t1.0U44395\tP2076\t554U11579\tS957" in qs


def test_kennungen_gehen_ohne_beleg_raus():
    zeilen = je_pid(zeilen_de(EISEN, EISEN_DE))
    for pid in ("P232", "P2566"):
        assert zeilen[pid]["_ohne_beleg"] is True
        assert zeilen[pid]["ref_url"] == ""


def test_unplausible_verdampfungswaerme_wird_ausgewiesen():
    """Neptunium: de schreibt 1420 kJ/mol (en: 336) - das gehoert vor Augen."""
    felder = {"Siedepunkt_K": "4273",
              "Verdampfungswärme": "1420 kJ·mol<sup>−1</sup>"}
    zeile = je_pid(zeilen_de({"qid": "Q1105", "label": "Neptunium"}, felder))["P2116"]
    assert zeile["status"].startswith("MANUELLE_KLAERUNG_NOETIG (unplausibler")


# ===========================================================================
# Phasenpunkte (P873)
# ===========================================================================

def test_phasenpunkte_lesen():
    punkte = parse_phasenpunkte(WASSERSTOFF_EN)
    assert [(p[0], p[1], p[2], p[4]) for p in punkte] == [
        ("triple point", 13.8033, 7.041, "kPa"),
        ("critical point", 33.19, 1.313, "MPa"),
    ]


def test_phasenpunkt_ohne_druck_entfaellt():
    assert parse_phasenpunkte({"triple point K": "1090",
                               "triple point kPa": ""}) == []


def test_phasenpunkte_tragen_temperatur_und_druck(tmp_path):
    zeilen = phasenpunkt_proposals_for_item(
        WASSERSTOFF, WASSERSTOFF_EN, "https://x", WASSERSTOFF_ARTIKEL, set())
    assert [z["value"] for z in zeilen] == ["Q106410", "Q111059"]
    qs = qs_text(tmp_path, zeilen)
    assert ("Q556\tP873\tQ106410\tP2076\t13.8033U11579"
            "\tP2077\t7.041U21064807") in qs
    assert ("Q556\tP873\tQ111059\tP2076\t33.19U11579"
            "\tP2077\t1.313U21062777\tS356\t\"10.1000/sva\"") in qs


def test_phasenpunkt_wird_wertgenau_geprueft():
    """Ein vorhandener Tripelpunkt darf den kritischen Punkt nicht
    unterdruecken - geprueft wird der WERT von P873, nicht die PID."""
    wikidata._MERKMAL_CACHE["Q556"] = {"P1552": set(), "P873": {"Q106410"}}
    zeilen = phasenpunkt_proposals_for_item(
        WASSERSTOFF, WASSERSTOFF_EN, "https://x", WASSERSTOFF_ARTIKEL, set())
    assert [(z["value"], z["status"]) for z in zeilen] == [
        ("Q106410", "BEREITS_VORHANDEN"), ("Q111059", "VORSCHLAG")]


def test_phasenpunkt_respektiert_skip_keys():
    assert phasenpunkt_proposals_for_item(
        WASSERSTOFF, WASSERSTOFF_EN, "https://x", "", {"phase_point"}) == []


def test_merkmalscache_traegt_beide_wertgenauen_properties():
    claims = {
        "P1552": [{"mainsnak": {"datavalue": {"value": {"id": "Q184207"}}}}],
        "P873": [{"mainsnak": {"datavalue": {"value": {"id": "Q111059"}}}}],
    }
    wikidata._MERKMAL_CACHE["Q1"] = wikidata._merkmale_aus_claims(claims)
    assert wikidata.item_hat_wert("Q1", "P873", "Q111059")
    assert not wikidata.item_hat_wert("Q1", "P873", "Q106410")
    assert wikidata.item_hat_wert("Q1", "P1552", "Q184207")


# ===========================================================================
# Tabellen
# ===========================================================================

def test_wikipedia_stufe_kennt_die_neuen_pids():
    neu = {"P2066", "P2116", "P873", "P2119", "P2807", "P1108", "P2260",
           "P14936", "P14937", "P14938", "P5480", "P5674", "P232", "P2566"}
    assert neu <= STUFEN_PIDS["wikipedia"]


def test_p922_ist_bekannt_aber_offen():
    """P922 'magnetische Ordnung' steht als offene Frage in
    proposals/review-needed.md. Bis zur Entscheidung liefert KEINE Stufe
    P922 - die Magnetismus-Stufe bleibt bei P1552."""
    assert PROPERTY_MAP["magnetic_ordering"]["pid"] == "P922"
    assert all("P922" not in pids for pids in STUFEN_PIDS.values())
    assert PROPERTY_MAP["magnetism"]["pid"] == "P1552"
    assert "P1552" in STUFEN_PIDS["wikipedia"]
