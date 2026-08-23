"""NIST Chemistry WebBook: Bildungsenthalpie (P3078) und Standardentropie
(P3071), belegt mit der Originalarbeit. Alles netzwerkfrei."""
import pytest

from materialswiki import cli, wikidata
from materialswiki.quellen import nist
from materialswiki.cli import nist_proposals_for_item, nist_tabellenzeilen, nist_wert


def seite(zeilen, formel="Cu"):
    """Minimales WebBook-HTML mit Datentabelle und JSON-LD-Formel."""
    tr = "".join(
        "<tr>" + "".join(f"<td>{z}</td>" for z in zeile) + "</tr>"
        for zeile in zeilen
    )
    return (f'<script>{{"molecularFormula" : "{formel}"}}</script>'
            f'<table><tr><th>Quantity</th><th>Value</th><th>Units</th>'
            f'<th>Method</th><th>Reference</th></tr>{tr}</table>')


JANAF = "Chase, 1998"
CODATA = "Cox, Wagman, et al., 1984"


@pytest.fixture
def kupfer():
    return {"qid": "Q753", "label": "Kupfer", "ambiguous": False}


@pytest.fixture(autouse=True)
def kein_bestand(monkeypatch):
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: False)
    nist._NIST_UNBEKANNTE_QUELLEN.clear()


def antwortet(monkeypatch, nach_mask):
    """nach_mask: {"1": Gasphase, "2": kondensiert} - abgerufen wird beides
    in EINER Antwort (Mask=3, siehe nist_thermodaten)."""
    def fake(cas, mask):
        assert mask == "3", "Gas- und Kondensatseite kommen in einem Abruf"
        return seite(nach_mask.get("1", []) + nach_mask.get("2", []))
    monkeypatch.setattr(nist, "nist_fetch", fake)


# ===========================================================================
# Zahlen lesen
# ===========================================================================

@pytest.mark.parametrize("roh, erwartet", [
    ("-241.826 ± 0.040", (-241.826, 0.040)),
    ("33.15", (33.15, None)),
    ("-1675.7 &plusmn; 1.3", (-1675.7, 1.3)),
    ("1357.95 to 1400", None),      # Bereich: keine Zahl
    ("N/A", None),
])
def test_wert_und_streuung(roh, erwartet):
    assert nist_wert(roh) == erwartet


def test_tabellenzeilen_ueberspringen_die_kopfzeile():
    html = seite([["ΔfH°solid", "-1675.7", "kJ/mol", "Review", CODATA]])
    assert nist_tabellenzeilen(html) == [
        ("ΔfH°solid", "-1675.7", "kJ/mol", "Review", CODATA)]


# ===========================================================================
# Vorschlaege
# ===========================================================================

def test_groesse_zustand_und_beleg(monkeypatch, kupfer):
    """Der Aggregatzustand ist Pflichtqualifikator beider Properties - ohne
    ihn ist die Zahl bedeutungslos."""
    antwortet(monkeypatch, {"2": [
        ["S°solid,1 bar", "33.15 ± 0.08", "J/mol*K", "Review", CODATA]]})
    zeilen = nist_proposals_for_item(kupfer, "7440-50-8", "Cu")

    assert len(zeilen) == 1
    z = zeilen[0]
    assert z["_pid"] == "P3071"
    assert z["value"] == pytest.approx(33.15)
    assert z["unit_qid"] == "Q20966455"          # J/(mol*K)
    assert z["_qualifiers"] == [("P515", "Q11438", "fest")]
    assert z["status"] == "VORSCHLAG"


def test_beleg_ist_die_originalarbeit_nicht_das_webbook(monkeypatch, kupfer):
    """NIST-Standardreferenzdaten sind urheberrechtlich geschuetzt; zitiert
    wird die Arbeit, der das WebBook den Wert zuschreibt."""
    antwortet(monkeypatch, {"2": [
        ["ΔfH°solid", "-1675.7 ± 1.3", "kJ/mol", "Review", CODATA]]})
    z = nist_proposals_for_item(kupfer, "7440-50-8", "Cu")[0]

    assert z["ref_isbn"] == "0-89116-758-7"
    assert "CODATA Key Values" in z["ref_note"]
    assert z["ref_doi"] == ""
    # Die Fundstelle bleibt nachvollziehbar, ist aber nicht der Beleg
    assert "WebBook" in z["ref_note"]


def test_codata_schlaegt_janaf_bei_einigkeit(monkeypatch, kupfer):
    antwortet(monkeypatch, {"1": [
        ["ΔfH°gas", "337.4 ± 1.2", "kJ/mol", "Review", CODATA],
        ["ΔfH°gas", "337.60", "kJ/mol", "Review", JANAF]]})
    z = nist_proposals_for_item(kupfer, "7440-50-8", "Cu")[0]

    assert z["value"] == pytest.approx(337.4)
    assert "CODATA" in z["ref_note"]


def test_uneinige_quellen_gehen_zur_klaerung(monkeypatch, kupfer):
    """Welche Messreihe die bessere ist, entscheidet das Werkzeug nicht."""
    antwortet(monkeypatch, {"1": [
        ["ΔfH°gas", "337.4", "kJ/mol", "Review", CODATA],
        ["ΔfH°gas", "402.0", "kJ/mol", "Review", JANAF]]})
    z = nist_proposals_for_item(kupfer, "7440-50-8", "Cu")[0]

    assert z["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert "337.4" in z["status"] and "402" in z["status"]


def test_unbekannte_quelle_wird_uebergangen_und_gezaehlt(monkeypatch, kupfer):
    """Ohne zitierbare Originalarbeit kein Vorschlag - aber auch kein
    stilles Verschwinden."""
    antwortet(monkeypatch, {"2": [
        ["ΔfH°solid", "-1675.7", "kJ/mol", "Review", "Anonymous, 1988"]]})

    assert nist_proposals_for_item(kupfer, "7440-50-8", "Cu") == []
    assert nist._NIST_UNBEKANNTE_QUELLEN["Anonymous, 1988"] == 1


def test_fremde_einheit_wird_nicht_umgerechnet(monkeypatch, kupfer):
    antwortet(monkeypatch, {"2": [
        ["ΔfH°solid", "-400.5", "kcal/mol", "Review", CODATA]]})
    assert nist_proposals_for_item(kupfer, "7440-50-8", "Cu") == []


def test_unplausibler_wert_wird_nicht_vorgeschlagen(monkeypatch, kupfer):
    antwortet(monkeypatch, {"2": [
        ["S°solid", "-5.0", "J/mol*K", "Review", CODATA]]})   # dritter Hauptsatz
    assert nist_proposals_for_item(kupfer, "7440-50-8", "Cu") == []


def test_andere_summenformel_heisst_anderer_stoff(monkeypatch, kupfer):
    """Eine CAS-Nummer kann am falschen Item stehen; die Zusammensetzung
    luegt nicht."""
    monkeypatch.setattr(nist, "nist_fetch", lambda cas, mask: seite(
        [["ΔfH°solid", "-1675.7", "kJ/mol", "Review", CODATA]], formel="Al2O3"))
    assert nist_proposals_for_item(kupfer, "7440-50-8", "Cu") == []


def test_ohne_cas_keine_abfrage(monkeypatch, kupfer):
    def platzt(cas, mask):
        raise AssertionError("ohne CAS darf nichts abgerufen werden")
    monkeypatch.setattr(nist, "nist_fetch", platzt)
    assert nist_proposals_for_item(kupfer, "") == []


def test_belegte_property_wird_uebersprungen(monkeypatch, kupfer):
    antwortet(monkeypatch, {"2": [
        ["S°solid", "33.15", "J/mol*K", "Review", CODATA]]})
    assert nist_proposals_for_item(kupfer, "7440-50-8", "Cu",
                                   skip_pids={"P3071"}) == []


def test_entwurfszeile_traegt_einheit_zustand_und_isbn(monkeypatch, kupfer,
                                                       tmp_path):
    antwortet(monkeypatch, {"2": [
        ["ΔfH°solid", "-1675.7 ± 1.3", "kJ/mol", "Review", CODATA]]})
    zeilen = nist_proposals_for_item(kupfer, "7440-50-8", "Cu")

    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    aussage = [z for z in pfad.read_text(encoding="utf-8").splitlines()
               if z.startswith("Q753")][0]
    felder = aussage.split("\t")

    assert felder[:5] == ["Q753", "P3078", "-1675.7U752197", "P515", "Q11438"]
    assert felder[5] == "S957"                    # ISBN-10 als Beleg
