"""Funktionale Gruppen aus der Summenformel: P527 statt einzelner Elemente.

Ein Mineral ist kein Haufen Atome - in Gips sitzt ein Sulfation, kein loser
Schwefel. Diese Datei prueft beides: den reinen Parser (gruppen_aus_formel,
ohne jedes Wikidata-Wissen) und die Zeilen, die daraus werden. Alles
netzwerkfrei.
"""
import pytest

from materialswiki import ableitungen, cli, wikidata
from materialswiki.ableitungen import GRUPPEN_QIDS, formel_proposals_for_item
from materialswiki.formeln import GRUPPEN_SIGNATUREN, gruppen_aus_formel


# ---------------------------------------------------------------------------
# Der Parser
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formel,gruppen,rest", [
    # Gips: ein Sulfation und zwei Molekuele Kristallwasser, uebrig Calcium.
    ("CaSO₄·2H₂O", {"SO4": 1, "H2O": 2}, "Ca"),
    # Geklammert wie ungeklammert, mit und ohne Faktor.
    ("Mg(OH)₂", {"OH": 2}, "Mg"),
    ("FeO(OH)", {"OH": 1}, "FeO"),
    ("Ca₅(PO₄)₃(OH)", {"PO4": 3, "OH": 1}, "Ca5"),
    ("Cu₂(OH)₂CO₃", {"OH": 2, "CO3": 1}, "Cu2"),
    ("Mg₂SiO₄", {"SiO4": 1}, "Mg2"),
    # Kaolinit: die Hydroxide raus, das Schichtsilicat bleibt Element fuer
    # Element - Si₂O₅ ist keine Gruppe der Tabelle.
    ("Al₂Si₂O₅(OH)₄", {"OH": 4}, "Al2Si2O5"),
    # Variable Wassermenge: die Gruppe ist sicher, ihre Anzahl nicht.
    ("MgCO₃·nH₂O", {"CO3": 1, "H2O": None}, "Mg"),
])
def test_groesste_gruppe_wird_erkannt(formel, gruppen, rest):
    assert gruppen_aus_formel(formel) == (gruppen, rest)


@pytest.mark.parametrize("formel", [
    "Al₂SiO₅",   # SiO₅ ist keine Gruppe - SiO₄ herauszulesen hiesse raten
    "KAlSi₃O₈",  # dito Si₃O₈
    "Fe₂O₃",
    "NaCl",
    "K₂Cr₂O₇",   # Dichromat steht nicht in der Tabelle
])
def test_ohne_passende_gruppe_bleibt_die_formel_unangetastet(formel):
    """Lieber die Elementableitung als eine falsche Baugruppe. Die Formel
    kommt unveraendert zurueck, die Elementstufe rechnet damit weiter."""
    assert gruppen_aus_formel(formel) == ({}, formel)


def test_die_formel_ist_die_gruppe():
    """"Wasser besteht aus einem Wasser" sagt nichts."""
    assert gruppen_aus_formel("H₂O") == ({}, "H₂O")


def test_uranyl_nur_wo_die_formel_es_klammert():
    """(UO₂) in Carnotit ist eine Ansage. Das nackte UO₂ von Uraninit ist
    dagegen ein Oxid des vierwertigen Urans und gerade kein Uranylion."""
    gruppen, rest = gruppen_aus_formel("K₂(UO₂)₂(VO₄)₂·3H₂O")
    assert gruppen == {"UO2": 2, "VO4": 2, "H2O": 3}
    assert rest == "K2"

    assert gruppen_aus_formel("UO₂") == ({}, "UO₂")


def test_kommagruppe_ist_keine_gruppe():
    """(OH,F) ist eine Mischreihe: entweder Hydroxid oder Fluorid. Was davon,
    haengt am Glied der Reihe - also nichts behaupten."""
    formel = "Al₁₃Si₅O₂₀(OH,F)₁₈Cl"
    assert gruppen_aus_formel(formel) == ({}, formel)


def test_jede_gruppe_hat_ein_item():
    """Sonst stuerzt die Zeilenstufe beim seltenen Mineral ab, das die Gruppe
    zum ersten Mal bringt."""
    assert {name for name, _ in GRUPPEN_SIGNATUREN} == set(GRUPPEN_QIDS)


# ---------------------------------------------------------------------------
# Die Zeilen, die daraus werden
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def elementtabelle(monkeypatch):
    monkeypatch.setattr(wikidata, "_ELEMENT_QID_CACHE", {
        "H": {"qid": "Q556", "label": "Wasserstoff", "name_en": "hydrogen",
              "title_de": "Wasserstoff"},
        "O": {"qid": "Q629", "label": "Sauerstoff", "name_en": "oxygen",
              "title_de": "Sauerstoff"},
        "S": {"qid": "Q682", "label": "Schwefel", "name_en": "sulfur",
              "title_de": "Schwefel"},
        "Ca": {"qid": "Q706", "label": "Calcium", "name_en": "calcium",
               "title_de": "Calcium"},
    })
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: False)


@pytest.fixture
def gips():
    # Leere Zwischenspeicher: das Item traegt keine Altaussage. Ohne die
    # Eintraege ginge die Stufe ins Netz.
    ableitungen._P527_CACHE["Q1516"] = {}
    ableitungen._P527_WERTE["Q1516"] = set()
    return {"qid": "Q1516", "label": "Gips", "ambiguous": False,
            "title_de": "Gips", "title_en": "Gypsum"}


def test_gruppe_als_p527_element_nur_fuer_den_rest(gips):
    zeilen = formel_proposals_for_item(gips, "CaSO₄·2H₂O")
    nach_wert = {z["value"]: z for z in zeilen}

    # P527 "besteht aus" fuer die Gruppen: hier ist die Aussage mereologisch
    # richtig, ein Sulfation IST ein Stueck Materie.
    assert nach_wert["Q172290"]["_pid"] == "P527"
    assert nach_wert["Q172290"]["_qualifiers"] == [("P1114", "1", "Anzahl 1")]
    assert nach_wert["Q283"]["_pid"] == "P527"
    assert nach_wert["Q283"]["_qualifiers"] == [("P1114", "2", "Anzahl 2")]

    # Calcium steckt in keiner Gruppe und bleibt bei P2670 - das Element-Item
    # ist die Klasse seiner Atome.
    assert nach_wert["Q706"]["_pid"] == "P2670"

    # Und was in einer Gruppe gebunden ist, wird nicht noch einmal einzeln
    # behauptet: kein Schwefel, kein Sauerstoff, kein Wasserstoff.
    assert set(nach_wert) == {"Q172290", "Q283", "Q706"}
    assert all(z["status"] == "VORSCHLAG" for z in zeilen)
    assert all(z["source"] == "Formel" for z in zeilen)


def test_herkunft_steht_in_der_notiz(gips):
    """Die Gruppenzeile geht wie die Elementzeile ohne S-Beleg raus - es gibt
    keine externe Quelle. Nachpruefbar bleibt sie ueber die Formel."""
    zeile = [z for z in formel_proposals_for_item(gips, "CaSO₄·2H₂O")
             if z["value"] == "Q172290"][0]

    assert zeile["_ohne_beleg"] is True
    assert zeile["ref_doi"] == "" and zeile["ref_url"] == ""
    assert "SO4" in zeile["ref_note"] and "CaSO₄·2H₂O" in zeile["ref_note"]


def test_bestehende_gruppenaussage_wird_nicht_wiederholt(gips):
    """Wertgenau, nicht nur 'traegt das Item irgendein P527': die
    Elementaussagen, die die Umstellung abraeumt, sind ja auch P527."""
    ableitungen._P527_WERTE["Q1516"] = {"Q172290", "Q629"}
    zeilen = {z["value"]: z for z in formel_proposals_for_item(
        gips, "CaSO₄·2H₂O")}

    assert zeilen["Q172290"]["status"] == "BEREITS_VORHANDEN"
    # Das Sauerstoff-P527 ist eine Altaussage der Umstellung und sagt ueber
    # das Wasser nichts.
    assert zeilen["Q283"]["status"] == "VORSCHLAG"


def test_belegte_property_wird_uebersprungen(gips):
    """--formel liefert zwei Properties; ist eine davon schon von einer
    frueheren Stufe belegt, faellt nur sie weg."""
    nur_elemente = formel_proposals_for_item(gips, "CaSO₄·2H₂O",
                                             skip_pids={"P527"})
    assert [z["value"] for z in nur_elemente] == ["Q706"]

    nur_gruppen = formel_proposals_for_item(gips, "CaSO₄·2H₂O",
                                            skip_pids={"P2670"})
    assert {z["value"] for z in nur_gruppen} == {"Q172290", "Q283"}


def test_entwurf_traegt_gruppe_und_rest(gips, tmp_path):
    """Die Probe aufs Exempel: so landet es in QuickStatements."""
    zeilen = formel_proposals_for_item(gips, "CaSO₄·2H₂O")
    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    aussagen = [z for z in pfad.read_text(encoding="utf-8").splitlines()
                if z.startswith("Q1516")]

    assert aussagen == [
        "Q1516\tP527\tQ283\tP1114\t2",
        "Q1516\tP527\tQ172290\tP1114\t1",
        "Q1516\tP2670\tQ706\tP1114\t1",
    ]
