"""Aufbau des QuickStatements-Entwurfs - netzwerkfrei."""
import pytest

from materialswiki.cli import Reference, write_quickstatements_draft


def zeile(status, **rest):
    basis = {
        "status": status,
        "source": "MP",
        "qid": "Q42",
        "label": "Testitem",
        "property": "P2054 (Dichte)",
        "_pid": "P2054",
        "value": 4230.0,
        "value_label": "",
        "datatype": "quantity",
        "unit_qid": "Q844211",
        "_ref": Reference(doi="10.1000/test", note="MP entry_id abc"),
    }
    basis.update(rest)
    return basis


@pytest.fixture
def entwurf(tmp_path):
    def schreiben(rows):
        pfad = tmp_path / "entwurf.txt"
        write_quickstatements_draft(rows, str(pfad))
        return pfad.read_text(encoding="utf-8")
    return schreiben


def abschnitte(text):
    """Text in (vor Abschnitt 2) und (ab Abschnitt 2) zerlegen."""
    marke = text.index("# ABSCHNITT 2:")
    return text[:marke], text[marke:]


# --- der eigentliche Zweck ------------------------------------------------

def test_vorschlag_wird_zu_einer_ausfuehrbaren_zeile(entwurf):
    text = entwurf([zeile("VORSCHLAG")])
    assert 'Q42\tP2054\t4230.0U844211\tS356\t"10.1000/test"' in text


def test_nur_vorschlaege_sind_ausfuehrbar(entwurf):
    """Die Sicherheitseigenschaft: ausserhalb von Abschnitt 1 beginnt JEDE
    Zeile mit '#'. Die Datei kann damit komplett kopiert werden, ohne dass
    aus einer geprueften oder offenen Zeile eine Aussage wird."""
    text = entwurf([
        zeile("VORSCHLAG"),
        zeile("BEREITS_VORHANDEN", qid="Q43"),
        zeile("MANUELLE_KLAERUNG_NOETIG (mehrdeutige Formel)", qid="",
              formula="O2Ti", kandidaten="Q1 (A); Q2 (B)", entry_id="e1",
              ref_doi="10.1000/x", _ref=None),
    ])
    _, ab_zwei = abschnitte(text)
    for z in ab_zwei.splitlines():
        assert z == "" or z.startswith("#"), f"ausfuehrbare Zeile: {z!r}"


def test_geprueftes_und_offenes_bleiben_sichtbar(entwurf):
    """Abgetrennt heisst nicht weggeworfen - beides muss auffindbar sein."""
    text = entwurf([
        zeile("BEREITS_VORHANDEN", qid="Q43"),
        zeile("MANUELLE_KLAERUNG_NOETIG (mehrdeutige Formel)", qid="",
              formula="O2Ti", kandidaten="Q193521 (Titan(IV)-oxid); Q320603 (Rutil)",
              entry_id="e1", ref_doi="10.1000/x", _ref=None),
    ])
    assert "Q43" in text                      # geprueft, nicht verschwunden
    assert "Q193521 (Titan(IV)-oxid)" in text  # Kandidat steht da
    assert "Q320603 (Rutil)" in text
    assert "10.1000/x" in text                 # DOI bleibt rueckverfolgbar


def test_kopfzeile_zaehlt_alle_drei_status(entwurf):
    text = entwurf([
        zeile("VORSCHLAG"), zeile("VORSCHLAG", _pid="P2101"),
        zeile("BEREITS_VORHANDEN"),
        zeile("MANUELLE_KLAERUNG_NOETIG (mehrdeutige Formel)", kandidaten="Q1 (A)",
              _ref=None),
    ])
    kopf = text[:text.index("# ABSCHNITT 1:")]
    assert "EINSPIELBAR ..........    2" in kopf
    assert "BEREITS VORHANDEN ....    1" in kopf
    assert "MANUELLE KLAERUNG ....    1" in kopf


def test_leere_abschnitte_werden_ausgewiesen(entwurf):
    """Ein fehlender Abschnitt darf nicht wie ein vergessener aussehen."""
    text = entwurf([zeile("VORSCHLAG")])
    _, ab_zwei = abschnitte(text)
    assert ab_zwei.count("# (keine)") == 2


def test_klaerung_ohne_kandidaten_nennt_item_und_rohwert(entwurf):
    """Zweite Auspraegung: Item steht fest, nur der Wert passt nicht."""
    text = entwurf([zeile(
        "MANUELLE_KLAERUNG_NOETIG (Wert 'amorph' nicht in value_map fuer P556)",
        property="P556 (Kristallsystem)", value="amorph", _ref=None,
    )])
    assert "Q42 Testitem" in text
    assert "amorph" in text
