"""Summenformel (P274) aus 'besteht aus' (P527) - der umgekehrte Weg fuer
Legierungen. Alles netzwerkfrei."""
import re

import pytest

from materialswiki import cli
from materialswiki.cli import (
    hill_reihenfolge,
    legierungsformel,
    legierungsformel_proposals_for_item,
)


# Format-Constraint von P274 (Q21502404), am 2026-08-18 aus der Property
# ausgelesen. Was hier durchfaellt, wuerde in Wikidata als Verstoss angezeigt.
P274_FORMAT = re.compile(
    r"([αβγδφωλμπ]-)?([([]*[A-Z☐][ub]?[a-z]?[₁₂₃₄₅₆₇₈₉₀.ₓ]*"
    r"(\)?[¹²³⁴⁵⁶⁷⁸⁹⁰]*[⁺⁻]?)?[\])|,₁₂₃₄₅₆₇₈₉₀ₓ]*(·\(?[-0-9.]*n?\)?)?)+"
)


# ===========================================================================
# Formelbau: Hill-Reihenfolge, Mittelpunkt fuer unbestimmte Verhaeltnisse
# ===========================================================================

@pytest.mark.parametrize("symbole, erwartet", [
    # Ohne Kohlenstoff faellt Hill mit der alphabetischen Reihenfolge zusammen
    (["Sn", "Cu"], ["Cu", "Sn"]),
    (["Zn", "Pb", "Ni", "Cu"], ["Cu", "Ni", "Pb", "Zn"]),
    # Kohlenstoff zuerst, dann Wasserstoff, dann alphabetisch
    (["Fe", "C"], ["C", "Fe"]),
    (["Fe", "C", "Cr", "H"], ["C", "H", "Cr", "Fe"]),
])
def test_hill_reihenfolge(symbole, erwartet):
    assert hill_reihenfolge(symbole) == erwartet


def test_unbestimmtes_verhaeltnis_bekommt_mittelpunkt():
    """Der Regelfall bei Legierungen: die Bestandteile stehen fest, ihr
    Verhaeltnis nicht. 'CuSn' wuerde Gleichteiligkeit behaupten."""
    assert legierungsformel({"Cu": None, "Sn": None}) == "Cu·Sn"
    assert legierungsformel({"Fe": None, "C": None}) == "C·Fe"


def test_teilweise_bekannte_anzahl_reicht_nicht():
    """Eine einzige fehlende Anzahl macht die ganze Formel unbestimmt."""
    assert legierungsformel({"Cu": 3, "Sn": None}) == "Cu·Sn"


def test_vollstaendige_anzahl_ergibt_echte_summenformel():
    """Stehen alle Anzahlen (P1114) da, ist das Verhaeltnis bekannt - dann
    tiefgestellte Ziffern statt Mittelpunkt, wie ueberall in Wikidata."""
    assert legierungsformel({"Cu": 3, "Au": 1}) == "AuCu₃"


def test_ein_einziges_element_ergibt_keine_formel():
    """Items mit genau einem Bestandteil sind Legierungs-KLASSEN
    ('Nickelbasislegierung'); 'Ni' waere die Formel des Elements."""
    assert legierungsformel({"Ni": None}) is None
    assert legierungsformel({}) is None


@pytest.mark.parametrize("bestandteile", [
    {"Cu": None, "Sn": None},
    {"Fe": None, "C": None},
    {"Cu": None, "Ni": None, "Pb": None, "Zn": None},
    {"Cu": 3, "Au": 1},
])
def test_erzeugte_formel_erfuellt_den_p274_constraint(bestandteile):
    formel = legierungsformel(bestandteile)
    assert P274_FORMAT.fullmatch(formel), formel


# ===========================================================================
# Vorschlagszeilen
# ===========================================================================

@pytest.fixture
def bronze():
    return {"qid": "Q34095", "label": "Bronze", "ambiguous": False,
            "title_de": "Bronze", "title_en": "Bronze"}


@pytest.fixture
def kein_p274(monkeypatch):
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: False)


def setze_bestandteile(qid, teile, fremd=False, legierung=True):
    cli._BESTANDTEIL_CACHE[qid] = {"teile": teile, "fremd": fremd,
                                   "legierung": legierung}


def test_vorschlag_aus_den_bestandteilen(kein_p274, bronze):
    setze_bestandteile("Q34095", {"Sn": None, "Cu": None})
    zeilen = legierungsformel_proposals_for_item(bronze)

    assert len(zeilen) == 1
    assert zeilen[0]["status"] == "VORSCHLAG"
    assert zeilen[0]["_pid"] == "P274"
    assert zeilen[0]["value"] == "Cu·Sn"
    assert zeilen[0]["source"] == "P527"
    assert zeilen[0]["datatype"] == "string"


def test_abgeleitete_aussage_geht_ohne_beleg_raus(kein_p274, bronze):
    """Wie bei P527 aus der Formel: die Quelle ist das Item selbst, ein
    'importiert aus Wikidata' waere zirkulaer. Nachpruefbar bleibt es."""
    setze_bestandteile("Q34095", {"Sn": None, "Cu": None})
    zeile = legierungsformel_proposals_for_item(bronze)[0]

    assert zeile["_ohne_beleg"] is True
    assert zeile["ref_doi"] == ""
    assert zeile["ref_url"] == ""
    assert "P527" in zeile["ref_note"]
    assert "Cu, Sn" in zeile["ref_note"]
    assert "unbestimmt" in zeile["ref_note"]


def test_entwurf_setzt_die_formel_in_anfuehrungszeichen(kein_p274, bronze,
                                                        tmp_path):
    """P274 ist datatype string - ohne Anfuehrungszeichen liest
    QuickStatements 'Cu·Sn' nicht als Zeichenkette."""
    setze_bestandteile("Q34095", {"Sn": None, "Cu": None})
    zeilen = legierungsformel_proposals_for_item(bronze)

    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    aussagen = [z for z in pfad.read_text(encoding="utf-8").splitlines()
                if z.startswith("Q34095")]

    assert aussagen == ['Q34095\tP274\t"Cu·Sn"']


def test_nichtelement_als_bestandteil_verhindert_die_formel(kein_p274, bronze):
    """Rostfreier Stahl 'besteht aus' Stahl und Chrom. Eine Elementformel
    daraus liesse den Stahl stillschweigend unter den Tisch fallen."""
    setze_bestandteile("Q34095", {"Cr": None}, fremd=True)
    assert legierungsformel_proposals_for_item(bronze) == []


def test_ohne_legierungseinordnung_kein_vorschlag(kein_p274, bronze):
    """'Platinmetalle' oder 'metals of antiquity' haengen nur ueber Q11426
    (Metall) unter der Legierung; ihr P527 ist eine Aufzaehlung."""
    setze_bestandteile("Q34095", {"Ir": None, "Os": None}, legierung=False)
    assert legierungsformel_proposals_for_item(bronze) == []


def test_bestehende_formel_wird_nicht_ergaenzt(monkeypatch, bronze):
    monkeypatch.setattr(cli, "item_has_statement", lambda qid, pid: True)
    setze_bestandteile("Q34095", {"Sn": None, "Cu": None})
    zeilen = legierungsformel_proposals_for_item(bronze)

    assert [z["status"] for z in zeilen] == ["BEREITS_VORHANDEN"]


def test_belegte_property_wird_uebersprungen(kein_p274, bronze):
    setze_bestandteile("Q34095", {"Sn": None, "Cu": None})
    assert legierungsformel_proposals_for_item(
        bronze, skip_pids={"P274"}) == []


# ===========================================================================
# Auswertung der SPARQL-Antwort
# ===========================================================================

def _antwort(bindings):
    class Resp:
        @staticmethod
        def json():
            return {"results": {"bindings": bindings}}
    return Resp()


def _teil(qid, teil, anzahl=None):
    b = {"i": {"value": f"http://www.wikidata.org/entity/{qid}"},
         "teil": {"value": f"http://www.wikidata.org/entity/{teil}"}}
    if anzahl is not None:
        b["anzahl"] = {"value": anzahl}
    return b


@pytest.fixture
def elementtabelle(monkeypatch):
    monkeypatch.setattr(cli, "element_qids", lambda: {
        "Cu": {"qid": "Q753", "label": "Kupfer", "name_en": "copper",
               "title_de": "Kupfer"},
        "Sn": {"qid": "Q1096", "label": "Zinn", "name_en": "tin",
               "title_de": "Zinn"},
    })


def test_bestandteile_werden_zu_symbolen_aufgeloest(monkeypatch,
                                                    elementtabelle):
    monkeypatch.setattr(cli, "get_with_retry", lambda url, params: _antwort([
        _teil("Q34095", "Q753"), _teil("Q34095", "Q1096"),
    ]))
    monkeypatch.setattr(cli, "legierungs_qids", lambda qids: set(qids))

    info = cli.fetch_bestandteile(["Q34095"])["Q34095"]
    assert info == {"teile": {"Cu": None, "Sn": None}, "fremd": False,
                    "legierung": True}


def test_bestandteil_ohne_elementitem_wird_als_fremd_gemerkt(monkeypatch,
                                                             elementtabelle):
    monkeypatch.setattr(cli, "get_with_retry", lambda url, params: _antwort([
        _teil("Q172587", "Q753"), _teil("Q172587", "Q11427"),  # Stahl
    ]))
    monkeypatch.setattr(cli, "legierungs_qids", lambda qids: set(qids))

    assert cli.fetch_bestandteile(["Q172587"])["Q172587"]["fremd"] is True


def test_widerspruechliche_anzahl_gilt_als_unbestimmt(monkeypatch,
                                                      elementtabelle):
    """Zwei Aussagen zu demselben Element mit verschiedener Anzahl: dann
    steht die Anzahl gerade nicht fest."""
    monkeypatch.setattr(cli, "get_with_retry", lambda url, params: _antwort([
        _teil("Q34095", "Q753", "3"), _teil("Q34095", "Q753", "4"),
        _teil("Q34095", "Q1096", "1"),
    ]))
    monkeypatch.setattr(cli, "legierungs_qids", lambda qids: set(qids))

    teile = cli.fetch_bestandteile(["Q34095"])["Q34095"]["teile"]
    assert teile == {"Cu": None, "Sn": 1}


def test_legierungs_qids_spart_den_knoten_metall_aus(monkeypatch):
    """Stahl kommt ueber Ferrolegierung an die Legierung heran und zaehlt,
    obwohl es AUCH ein Metall ist. 'Platinmetalle' kommt nur ueber Q11426
    dorthin und zaehlt nicht."""
    kanten = [
        ("Q11427", "Q1002571"),      # Stahl -> Ferrolegierung
        ("Q1002571", "Q37756"),      # Ferrolegierung -> Legierung
        ("Q11427", "Q11426"),        # Stahl -> Metall
        ("Q223995", "Q11426"),       # Platinmetalle -> Metall
        ("Q11426", "Q37756"),        # Metall -> Legierung (der Umweg)
    ]
    monkeypatch.setattr(cli, "get_with_retry", lambda url, params: _antwort([
        {"von": {"value": f"http://www.wikidata.org/entity/{v}"},
         "nach": {"value": f"http://www.wikidata.org/entity/{n}"}}
        for v, n in kanten
    ]))

    assert cli.legierungs_qids(["Q11427", "Q223995"]) == {"Q11427"}
