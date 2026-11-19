"""Pruef-Tabelle: Schreiben und Rueckimport - netzfrei."""
from pathlib import Path

import pytest

from pmdmap.config import load_config
from pmdmap.iri import IriScheme
from pmdmap.review import COLUMNS, read_review, write_review

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"
ALLOWED = {
    "exact match": "Q39893449",
    "close match": "Q39893184",
    "narrow match": "Q39893967",
    "broad match": "Q39894595",
    "related match": "Q39894604",
}


def zeile(**rest):
    basis = {c: "" for c in COLUMNS}
    basis.update({
        "paket": "0",
        "qid": "Q11427",
        "wd_label_de": "Stahl",
        "pmd_iri": "https://w3id.org/pmd/co/PMD_0020096",
        "pmd_definition": "Steel is an alloy; contains \"iron\"; and\nnewline",
        "aktuell": "P1709",
        "aktuell_referenzen": "0",
        "abgerufen": "2026-11-19",
    })
    basis.update(rest)
    return basis


@pytest.fixture
def scheme():
    return IriScheme.from_profile(load_config(CONFIG).profile)


@pytest.fixture
def lesen(tmp_path, scheme):
    def _lesen(rows):
        p, _ = write_review(rows, tmp_path / "review.csv")
        return read_review(p, scheme, ALLOWED)
    return _lesen


def test_format_semikolon_utf8(tmp_path):
    p, _ = write_review([zeile(wd_label_de="Größe; Maß")], tmp_path / "r.csv")
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")               # BOM fuer Excel
    kopf = raw.decode("utf-8-sig").splitlines()[0]
    assert kopf.split(";") == COLUMNS
    assert "Größe; Maß" in raw.decode("utf-8-sig")


def test_rueckimport_unveraendert(lesen):
    original = zeile(entscheidung="P1709", bemerkung="ok; passt")
    rf = lesen([original])
    assert not rf.errors
    (d,) = rf.decisions
    assert d.row == original              # Semikolon, Anfuehrungszeichen, Zeilenumbruch
    assert d.decision == "P1709" and d.p4390 == ""
    assert d.line == 2


@pytest.mark.parametrize("eingabe, erwartet", [
    ("P1709", "P1709"), (" p2888 ", "P2888"), ("Entfernen", "entfernen"),
    ("überspringen", "überspringen"), ("ueberspringen", "überspringen"), ("", ""),
])
def test_entscheidungen_tolerant(lesen, eingabe, erwartet):
    p4390 = "close match" if erwartet == "P2888" else ""
    rf = lesen([zeile(entscheidung=eingabe, entscheidung_p4390=p4390)])
    assert not rf.errors, rf.errors
    assert rf.decisions[0].decision == erwartet


def test_leere_entscheidung_ist_offen(lesen):
    rf = lesen([zeile(), zeile(qid="Q5", entscheidung="P1709")])
    assert [d.row["qid"] for d in rf.open] == ["Q11427"]


@pytest.mark.parametrize("p4390, qid", [
    ("close match", "Q39893184"),
    ("Close Match", "Q39893184"),
    ("Q39893967", "Q39893967"),
    ("broad match (Q39894595)", "Q39894595"),   # Format der Spalte vorschlag_p4390
])
def test_p4390_als_label_oder_qid(lesen, p4390, qid):
    rf = lesen([zeile(entscheidung="P2888", entscheidung_p4390=p4390)])
    assert not rf.errors
    assert rf.decisions[0].p4390 == qid


@pytest.mark.parametrize("rest, fehler", [
    ({"entscheidung": "vielleicht"}, "unbekannt"),
    ({"entscheidung": "P2888"}, "braucht entscheidung_p4390"),
    ({"entscheidung": "P2888", "entscheidung_p4390": "fuzzy match"}, "unbekannt"),
    ({"entscheidung": "P2888", "entscheidung_p4390": "Q1"}, "nicht erlaubt"),
    ({"entscheidung": "P1709", "entscheidung_p4390": "exact match"}, "P1709 ohne P4390"),
    ({"entscheidung": "P1709", "pmd_iri": "http://w3id.org/pmd/co/PMD_0020096"}, "keine Klassen-IRI"),
    ({"entscheidung": "P1709", "qid": "Stahl"}, "keine Wikidata-ID"),
])
def test_fehler_mit_zeilennummer(lesen, rest, fehler):
    rf = lesen([zeile(qid="Q1", entscheidung="überspringen"), zeile(**rest)])
    assert len(rf.errors) == 1
    assert rf.errors[0].startswith("Zeile 3")
    assert fehler in rf.errors[0]
    assert len(rf.decisions) == 1           # fehlerhafte Zeile wird nicht uebernommen


def test_p4390_bei_entfernen_nur_warnung(lesen):
    rf = lesen([zeile(entscheidung="entfernen", entscheidung_p4390="close match")])
    assert not rf.errors and rf.warnings
    assert rf.decisions[0].p4390 == ""


def test_fehlende_spalten(tmp_path):
    p = tmp_path / "kaputt.csv"
    p.write_text("qid;entscheidung\nQ1;P1709\n", encoding="utf-8")
    rf = read_review(p)
    assert rf.errors and "Spalten fehlen" in rf.errors[0]


# --- Pakete 1/2: P1628 und Zusammenfuehren ---------------------------------
def test_p1628_nur_an_eigenschaften(lesen):
    rf = lesen([zeile(qid="P2054", entscheidung="P1628"), zeile(qid="Q29539", entscheidung="P1628")])
    assert [d.row["qid"] for d in rf.decisions] == ["P2054"]
    assert "P1628 gehört an eine Wikidata-Eigenschaft" in rf.errors[0]


def test_p1709_nicht_an_eigenschaften(lesen):
    rf = lesen([zeile(qid="P2054", entscheidung="P1709")])
    assert "P1709 gehört an einen Eintrag" in rf.errors[0]


def test_offene_zeile_ohne_qid_kein_fehler(lesen):
    rf = lesen([zeile(qid="", pmd_iri="")])
    assert not rf.errors and len(rf.open) == 1


def test_merge_behaelt_handarbeit_und_andere_pakete(tmp_path):
    p = tmp_path / "review.csv"
    write_review([zeile(paket="0", qid="Q1", entscheidung="P1709", bemerkung="geprüft"),
                  zeile(paket="1", qid="Q2", pmd_iri="https://w3id.org/pmd/co/PMD_0000661", entscheidung="P2888",
                        entscheidung_p4390="close match")], p)
    # Paket 1 neu erzeugt: Q2 wieder dabei (ohne Handspalten), Q3 neu
    neu = [zeile(paket="1", qid="Q2", pmd_iri="https://w3id.org/pmd/co/PMD_0000661", begruendung="neu"),
           zeile(paket="1", qid="Q3", pmd_iri="https://w3id.org/pmd/co/PMD_0000661")]
    _, notes = write_review(neu, p, {"1"})
    rf = read_review(p, None, ALLOWED)
    rows = {(d.row["paket"], d.row["qid"]): d for d in rf.decisions}
    assert rows[("0", "Q1")].decision == "P1709" and rows[("0", "Q1")].row["bemerkung"] == "geprüft"
    assert rows[("1", "Q2")].decision == "P2888" and rows[("1", "Q2")].p4390 == "Q39893184"
    assert rows[("1", "Q2")].row["begruendung"] == "neu"          # Belegspalten aktualisiert
    assert ("1", "Q3") in rows and not notes


def test_merge_verwirft_keine_entschiedene_zeile(tmp_path):
    p = tmp_path / "review.csv"
    write_review([zeile(paket="1", qid="Q9", entscheidung="P1709")], p)
    _, notes = write_review([zeile(paket="1", qid="Q8")], p, {"1"})
    rf = read_review(p, None, ALLOWED)
    assert {d.row["qid"] for d in rf.decisions} == {"Q8", "Q9"}
    assert notes and "Q9" in notes[0]
