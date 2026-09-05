"""Magnetische Ordnung (P1552 -> Ferro-/Para-/Diamagnetismus ...) aus dem
Feld 'Magnetismus' der {{Infobox Chemisches Element}}. Alles netzwerkfrei.

Das Feld steht als Wikilink oder blankes Wort, meist gefolgt von der
Suszeptibilitaet oder der Curie-Temperatur in Klammern und einem <ref>.
Nennt es mehrere Ordnungen (Chrom), wird nichts vorgeschlagen.
"""
import pytest

from materialswiki import infobox, wikidata
from materialswiki.cli import (
    PROPERTY_MAP, parse_de_magnetismus, quickstatements_value,
    wikipedia_de_values, write_quickstatements_draft,
)


@pytest.fixture
def eisen():
    return {"qid": "Q677", "label": "Eisen", "ambiguous": False,
            "title_de": "Eisen", "title_en": "Iron"}


@pytest.fixture(autouse=True)
def bestand(monkeypatch):
    monkeypatch.setattr(wikidata, "ist_bei_raumtemperatur_gas", lambda qid: False)
    monkeypatch.setattr(wikidata, "item_hat_merkmal", lambda qid, ziel: False)


# ---------------------------------------------------------------------------
# Was das Feld wirklich schreibt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("roh, erwartet", [
    ("[[Ferromagnetismus|ferromagnetisch]]", "ferromagnetisch"),   # Eisen, Cobalt
    ("ferromagnetisch", "ferromagnetisch"),                        # Nickel
    ("[[Paramagnetismus|paramagnetisch]] ([[Magnetische Suszeptibilität|"
     "''χ<sub>m</sub>'']] = 2,1 · 10<sup>−5</sup>)<ref>Weast</ref>",
     "paramagnetisch"),                                            # Aluminium
    ("[[Diamagnetismus|diamagnetisch]] (''χ<sub>m</sub>'' = −9,6 · "
     "10<sup>−6</sup>)<ref name='x' />", "diamagnetisch"),         # Kupfer
    ("[[Ferromagnetismus|ferromagnetisch]] ([[Curie-Temperatur|Curie-Temp.]] "
     "292,5 K)<ref name='CRC' />", "ferromagnetisch"),             # Gadolinium
    # mehrere Ordnungen -> nichts
    ("[[Antiferromagnetismus|antiferromagnetisch]],<br />"
     "[[Paramagnetismus|paramagnetisch]]", None),                  # Chrom
    ("antiferromagnetisch, paramagnetisch", None),                 # ohne <br />
    ("", None),
    ("<!-- folgt -->", None),
])
def test_feld_lesen(roh, erwartet):
    assert parse_de_magnetismus(roh) == erwartet


def test_antiferro_allein_wird_erkannt():
    """"antiferromagnetisch" enthaelt das Teilwort "ferromagnet" - trotzdem
    darf es nicht als mehrdeutig gelten."""
    assert parse_de_magnetismus(
        "[[Antiferromagnetismus|antiferromagnetisch]]") == "antiferromagnetisch"


def test_feldkarte_setzt_den_schluessel():
    werte = wikipedia_de_values({"Magnetismus": "ferromagnetisch"})
    assert werte["magnetism"][0] == "ferromagnetisch"


# ---------------------------------------------------------------------------
# Die fertige Zeile
# ---------------------------------------------------------------------------

def zeilen_zu(roh, item, monkeypatch):
    monkeypatch.setattr(
        infobox, "fetch_de_wikipedia_infobox",
        lambda titel: ({"Magnetismus": roh},
                       "https://de.wikipedia.org/w/index.php?title=Eisen&oldid=1",
                       ""),
    )
    return infobox.wikipedia_de_proposals_for_item(item, item["title_de"], set())


def test_ferromagnetisch_wird_zu_p1552_q184207(eisen, monkeypatch):
    zeile = zeilen_zu("[[Ferromagnetismus|ferromagnetisch]]", eisen, monkeypatch)[0]

    assert zeile["status"] == "VORSCHLAG"
    assert zeile["_pid"] == "P1552"
    assert zeile["value"] == "Q184207"
    assert zeile["value_label"] == "Ferromagnetismus"
    assert quickstatements_value(zeile) == "Q184207"   # blankes QID, keine Einheit


@pytest.mark.parametrize("roh, qid", [
    ("paramagnetisch", "Q188479"),
    ("[[Diamagnetismus|diamagnetisch]]", "Q201048"),
    ("[[Antiferromagnetismus|antiferromagnetisch]]", "Q575224"),
])
def test_weitere_ordnungen(eisen, monkeypatch, roh, qid):
    zeile = zeilen_zu(roh, eisen, monkeypatch)[0]
    assert zeile["value"] == qid


def test_mehrdeutiges_feld_ergibt_keine_zeile(eisen, monkeypatch):
    assert zeilen_zu("antiferromagnetisch,<br />paramagnetisch",
                     eisen, monkeypatch) == []


def test_gleiches_merkmal_schon_am_item(eisen, monkeypatch):
    """Eisen (Q677) und Nickel tragen 'P1552 -> Q184207' bereits."""
    monkeypatch.setattr(wikidata, "item_hat_merkmal",
                        lambda qid, ziel: ziel == "Q184207")
    zeile = zeilen_zu("ferromagnetisch", eisen, monkeypatch)[0]
    assert zeile["status"] == "BEREITS_VORHANDEN"


def test_anderes_p1552_am_item_unterdrueckt_nicht(eisen, monkeypatch):
    """Sauerstoff traegt drei P1552-Werte, keiner davon die magnetische
    Ordnung - die Zeile muss trotzdem als VORSCHLAG kommen."""
    monkeypatch.setattr(wikidata, "item_hat_merkmal",
                        lambda qid, ziel: ziel in {"Q11567495", "Q30100868"})
    zeile = zeilen_zu("paramagnetisch", eisen, monkeypatch)[0]
    assert zeile["status"] == "VORSCHLAG"
    assert zeile["value"] == "Q188479"


def test_entwurfszeile_ist_import_beleg(eisen, monkeypatch, tmp_path):
    zeilen = zeilen_zu("[[Ferromagnetismus|ferromagnetisch]]", eisen, monkeypatch)
    pfad = tmp_path / "entwurf.txt"
    write_quickstatements_draft(zeilen, str(pfad))
    aussage = [z for z in pfad.read_text(encoding="utf-8").splitlines()
               if z.startswith("Q677")][0]

    felder = aussage.split("\t")
    assert felder[:3] == ["Q677", "P1552", "Q184207"]
    assert "S143" in felder and "Q48183" in felder     # Import aus de.wikipedia


def test_property_ist_p1552_itemwertig():
    assert PROPERTY_MAP["magnetism"]["pid"] == "P1552"
    assert PROPERTY_MAP["magnetism"]["datatype"] == "item"
