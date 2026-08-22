"""Chemische Metaklasse (P31) fuer Legierungen, nach
[[Wikidata:WikiProject Chemistry/Guidelines/Basic metaclasses and relations]].
Alles netzwerkfrei."""
import pytest

from materialswiki import cli
from materialswiki.cli import (
    CHEMIE_METAKLASSEN,
    GEMISCH_METAKLASSE,
    metaklasse_proposals_for_item,
)


@pytest.fixture
def bronze():
    return {"qid": "Q34095", "label": "Bronze", "ambiguous": False,
            "title_de": "Bronze", "title_en": "Bronze"}


def setze_lage(qid, p31, legierung=True):
    cli._METAKLASSE_CACHE[qid] = {"p31": list(p31), "legierung": legierung}


# ===========================================================================
# Der Regelfall: Legierung ohne Metaklasse
# ===========================================================================

def test_legierung_ohne_metaklasse_bekommt_die_des_gemischs(bronze):
    """Eine Legierung ist per Definition ein Gemisch (Q37756: 'mixture or
    metallic solid solution'); die Guideline sieht dafuer eine eigene
    Metaklasse vor."""
    setze_lage("Q34095", ["Q214609"])   # nur "Material", keine Metaklasse
    zeilen = metaklasse_proposals_for_item(bronze, auch_mit_p31=True)

    assert len(zeilen) == 1
    assert zeilen[0]["status"] == "VORSCHLAG"
    assert zeilen[0]["_pid"] == "P31"
    assert zeilen[0]["value"] == GEMISCH_METAKLASSE     # Q119892838
    assert zeilen[0]["source"] == "Metaklasse"


def test_item_ganz_ohne_p31_bekommt_sie_auch(bronze):
    setze_lage("Q34095", [])
    assert metaklasse_proposals_for_item(bronze)[0]["status"] == "VORSCHLAG"


def test_bestehendes_p31_bleibt_standardmaessig_unangetastet(bronze):
    """Wo schon eine Einordnung steht ("P31 = Legierung"), waere die
    Metaklasse eine ZWEITE P31-Aussage daneben. Die Guideline will sie, aber
    das ist eine Massenaenderung - sie braucht den ausdruecklichen Schalter."""
    setze_lage("Q34095", ["Q37756"])
    assert metaklasse_proposals_for_item(bronze) == []
    assert metaklasse_proposals_for_item(
        bronze, auch_mit_p31=True)[0]["status"] == "VORSCHLAG"


def test_aussage_geht_ohne_beleg_raus_aber_mit_verweis(bronze):
    """Es gibt keine Messung zu belegen - die Metaklasse folgt aus der
    Klassenzugehoerigkeit. Die Guideline steht trotzdem in der Notiz."""
    setze_lage("Q34095", [])
    zeile = metaklasse_proposals_for_item(bronze)[0]

    assert zeile["_ohne_beleg"] is True
    assert zeile["ref_url"] == ""
    assert "Gemisch" in zeile["ref_note"]
    assert "WikiProject Chemistry" in zeile["ref_note"]


def test_entwurfszeile_ist_ein_blankes_qid(bronze, tmp_path):
    setze_lage("Q34095", [])
    zeilen = metaklasse_proposals_for_item(bronze)
    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    aussagen = [z for z in pfad.read_text(encoding="utf-8").splitlines()
                if z.startswith("Q34095")]

    assert aussagen == [f"Q34095\tP31\t{GEMISCH_METAKLASSE}"]


# ===========================================================================
# Wo nichts vorgeschlagen wird
# ===========================================================================

def test_bestehende_gemisch_metaklasse_wird_nicht_wiederholt(bronze):
    setze_lage("Q34095", [GEMISCH_METAKLASSE])
    zeilen = metaklasse_proposals_for_item(bronze)

    assert [z["status"] for z in zeilen] == ["BEREITS_VORHANDEN"]


def test_andere_chemie_metaklasse_wird_zur_klaerung_ausgewiesen(bronze):
    """Messing traegt Q113145171 'definierte chemische Substanz' - fuer ein
    Gemisch die falsche. Die Guideline laesst nur EINE zu, die bestehende
    muesste also weichen. Loeschen tut dieses Werkzeug nicht."""
    setze_lage("Q34095", ["Q113145171"])
    zeilen = metaklasse_proposals_for_item(bronze)

    assert len(zeilen) == 1
    assert zeilen[0]["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert "Q113145171" in zeilen[0]["status"]
    assert zeilen[0]["value"] == ""     # nichts Einspielbares


def test_nichtlegierung_bekommt_keine_gemisch_metaklasse(bronze):
    """'Platinmetalle' und 'metals of antiquity' haengen nur ueber Q11426
    (Metalle) unter der Legierung - sie sind Aufzaehlungen, keine Werkstoffe."""
    setze_lage("Q34095", [], legierung=False)
    assert metaklasse_proposals_for_item(bronze) == []


def test_mineralarten_bleiben_aussen_vor(bronze):
    """Gediegene Metalle und Amalgame sind als Mineralart modelliert. Ob dort
    zusaetzlich eine Chemie-Metaklasse hingehoert, entscheidet das
    Mineralprojekt."""
    setze_lage("Q34095", ["Q12089225"])
    assert metaklasse_proposals_for_item(bronze) == []


def test_belegte_property_wird_uebersprungen(bronze):
    setze_lage("Q34095", [])
    assert metaklasse_proposals_for_item(bronze, skip_pids={"P31"}) == []


# ===========================================================================
# Auswertung der SPARQL-Antwort
# ===========================================================================

def _antwort(bindings):
    class Resp:
        @staticmethod
        def json():
            return {"results": {"bindings": bindings}}
    return Resp()


def test_p31_werte_werden_je_item_gesammelt(monkeypatch):
    monkeypatch.setattr(cli, "get_with_retry", lambda url, params: _antwort([
        {"i": {"value": "http://www.wikidata.org/entity/Q34095"},
         "klasse": {"value": "http://www.wikidata.org/entity/Q214609"}},
        {"i": {"value": "http://www.wikidata.org/entity/Q34095"},
         "klasse": {"value": "http://www.wikidata.org/entity/Q214609"}},
        {"i": {"value": "http://www.wikidata.org/entity/Q39782"},
         "klasse": {"value": "http://www.wikidata.org/entity/Q113145171"}},
    ]))
    monkeypatch.setattr(cli, "legierungs_qids", lambda qids: {"Q34095"})

    lage = cli.fetch_metaklassen(["Q34095", "Q39782", "Q1"])
    assert lage["Q34095"] == {"p31": ["Q214609"], "legierung": True}
    assert lage["Q39782"] == {"p31": ["Q113145171"], "legierung": False}
    assert lage["Q1"] == {"p31": [], "legierung": False}


def test_die_guideline_kennt_genau_eine_metaklasse_fuer_gemische():
    """Q119896085 ist die Polymer-Untermetaklasse und fuer Legierungen nicht
    gemeint - erzeugt wird deshalb nur Q119892838."""
    assert GEMISCH_METAKLASSE == "Q119892838"
    assert "Q119896085" in CHEMIE_METAKLASSEN     # bekannt, aber nie erzeugt
