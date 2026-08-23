"""Umstellung bestehender Aussagen P527 -> P2670. Alles netzwerkfrei."""
import pytest

from materialswiki import ableitungen, cli, netz, wikidata
from materialswiki.cli import umstellung_proposals_for_item


@pytest.fixture(autouse=True)
def elementtabelle(monkeypatch):
    monkeypatch.setattr(wikidata, "element_qids", lambda: {
        "H": {"qid": "Q556", "label": "Wasserstoff", "name_en": "hydrogen",
              "title_de": "Wasserstoff"},
        "O": {"qid": "Q629", "label": "Sauerstoff", "name_en": "oxygen",
              "title_de": "Sauerstoff"},
    })
    monkeypatch.setattr(wikidata, "item_has_statement", lambda qid, pid: False)
    # Der Stoffnachweis laeuft ueber Formel oder Legierungseinordnung; die
    # Tests uebergeben die Formel, die Klassenlage bleibt leer.
    ableitungen._METAKLASSE_CACHE["Q283"] = {"p31": [], "legierung": False}


@pytest.fixture
def wasser():
    return {"qid": "Q283", "label": "Wasser", "ambiguous": False,
            "title_de": "Wasser", "title_en": "Water"}


def setze_p527(qid, eintraege):
    """eintraege: {Element-QID: (anzahl, beleg, andere, schon_p2670)}"""
    ableitungen._P527_CACHE[qid] = {
        e: {"anzahl": a, "beleg": b, "andere": c, "schon_p2670": d,
            "p527": True}
        for e, (a, b, c, d) in eintraege.items()
    }


def test_alte_aussage_wird_umgehaengt_und_entfernt(wasser):
    """Zwei Zeilen je Aussage: die neue P2670 und die Loeschzeile fuer die
    alte. Nur eine von beiden einzuspielen hinterliesse Dublette oder Luecke."""
    setze_p527("Q283", {"Q556": ("2", False, False, False)})
    zeilen = umstellung_proposals_for_item(wasser, "H₂O")

    assert [z["_pid"] for z in zeilen] == ["P2670", "P527"]
    neu, weg = zeilen
    assert neu["value"] == "Q556"
    assert neu["_qualifiers"] == [("P1114", "2", "Anzahl 2")]
    assert neu.get("_entfernen") is False
    assert weg["_entfernen"] is True
    assert weg["value"] == "Q556"
    assert "ENTFERNEN" in weg["property"]
    assert all(z["status"] == "VORSCHLAG" for z in zeilen)


def test_loeschzeile_traegt_im_entwurf_ein_minus(wasser, tmp_path):
    setze_p527("Q283", {"Q629": ("1", False, False, False)})
    zeilen = umstellung_proposals_for_item(wasser, "H₂O")

    pfad = tmp_path / "entwurf.txt"
    cli.write_quickstatements_draft(zeilen, str(pfad))
    text = pfad.read_text(encoding="utf-8")
    aussagen = [z for z in text.splitlines()
                if z.startswith("Q283") or z.startswith("-Q283")]

    assert aussagen == ["Q283\tP2670\tQ629\tP1114\t1", "-Q283\tP527\tQ629"]
    # Der Kopf des einspielbaren Abschnitts muss vor dem Loeschen warnen
    assert "ENTFERNEN eine bestehende Aussage" in text


def test_ohne_anzahl_kein_qualifikator(wasser):
    setze_p527("Q283", {"Q556": (None, False, False, False)})
    neu = umstellung_proposals_for_item(wasser, "H₂O")[0]

    assert neu["_qualifiers"] == []


@pytest.mark.parametrize("beleg, andere, erwartet", [
    (True, False, "Beleg"),
    (False, True, "weitere Qualifikatoren"),
    (True, True, "Beleg und weitere Qualifikatoren"),
])
def test_was_quickstatements_nicht_mitnehmen_kann_geht_zur_klaerung(
        wasser, beleg, andere, erwartet):
    """QuickStatements kann Belege und Qualifikatoren einer bestehenden
    Aussage nicht umhaengen - umstellen hiesse hier, sie zu verlieren."""
    setze_p527("Q283", {"Q556": ("2", beleg, andere, False)})
    zeilen = umstellung_proposals_for_item(wasser, "H₂O")

    assert len(zeilen) == 1
    assert zeilen[0]["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
    assert erwartet in zeilen[0]["status"]
    assert zeilen[0].get("_entfernen") is False   # nichts wird geloescht


def test_schon_umgestelltes_wird_nur_noch_aufgeraeumt(wasser):
    """Traegt das Item beide Aussagen, fehlt nur noch das Wegraeumen der
    alten - die neue waere eine Dublette."""
    setze_p527("Q283", {"Q556": ("2", False, False, True)})
    zeilen = umstellung_proposals_for_item(wasser, "H₂O")

    assert [z["_pid"] for z in zeilen] == ["P527"]
    assert zeilen[0]["_entfernen"] is True


def test_ohne_elementaussage_keine_zeile(wasser):
    setze_p527("Q283", {})
    assert umstellung_proposals_for_item(wasser, "H₂O") == []


def test_sammelbegriffe_werden_nicht_umgestellt(wasser):
    """'Alkalimetalle' fuehrt seine MITGLIEDER mit P527 - Caesium, Lithium.
    Dort ist P527 richtig, und "enthaelt Teile der Klasse Caesium" waere es
    nicht. Ohne Summenformel und ohne Legierungseinordnung: Finger weg."""
    setze_p527("Q283", {"Q556": ("2", False, False, False)})
    assert umstellung_proposals_for_item(wasser) == []


def test_legierung_ohne_formel_wird_umgestellt(wasser):
    """Stahl hat keine Summenformel, ist aber ein Stoff."""
    setze_p527("Q283", {"Q556": (None, False, False, False)})
    ableitungen._METAKLASSE_CACHE["Q283"] = {"p31": [], "legierung": True}
    assert [z["_pid"] for z in umstellung_proposals_for_item(wasser)] == [
        "P2670", "P527"]


def test_belegte_property_wird_uebersprungen(wasser):
    setze_p527("Q283", {"Q556": ("2", False, False, False)})
    assert umstellung_proposals_for_item(wasser, skip_pids={"P2670"}) == []


def test_formelstufe_doppelt_nicht_was_die_umstellung_liefert(monkeypatch,
                                                              wasser):
    """Sonst stuende dieselbe P2670-Aussage zweimal im Entwurf."""
    setze_p527("Q283", {"Q556": ("2", False, False, False)})
    zeilen = cli.formel_proposals_for_item(wasser, "H₂O")

    assert [z["value"] for z in zeilen] == ["Q629"]   # nur Sauerstoff


# ===========================================================================
# Auswertung der SPARQL-Antwort
# ===========================================================================

def _antwort(bindings):
    class Resp:
        @staticmethod
        def json():
            return {"results": {"bindings": bindings}}
    return Resp()


def _b(qid, wert, **extra):
    b = {"i": {"value": f"http://www.wikidata.org/entity/{qid}"},
         "e": {"value": f"http://www.wikidata.org/entity/{wert}"}}
    b.update({k: {"value": v} for k, v in extra.items()})
    return b


def test_nur_elementwerte_zaehlen(monkeypatch):
    """Ein P527 auf eine Verbindung (Quarz -> Siliciumdioxid) ist eine andere
    Aussage und bleibt unberuehrt."""
    monkeypatch.setattr(netz, "get_with_retry", lambda url, params: _antwort([
        _b("Q283", "Q556", anzahl="2"),
        _b("Q283", "Q11662"),          # Siliciumdioxid: kein Element
    ]))
    lage = ableitungen.fetch_p527_elemente(["Q283"])["Q283"]

    assert list(lage) == ["Q556"]
    assert lage["Q556"]["anzahl"] == "2"


def test_beleg_und_fremdqualifikator_werden_gemerkt(monkeypatch):
    monkeypatch.setattr(netz, "get_with_retry", lambda url, params: _antwort([
        _b("Q283", "Q556", beleg="x"),
        _b("Q283", "Q629", anderer="http://www.wikidata.org/prop/qualifier/P518"),
    ]))
    lage = ableitungen.fetch_p527_elemente(["Q283"])["Q283"]

    assert lage["Q556"]["beleg"] is True
    assert lage["Q629"]["andere"] is True


def test_bestehendes_p2670_wird_erkannt(monkeypatch):
    monkeypatch.setattr(netz, "get_with_retry", lambda url, params: _antwort([
        _b("Q283", "Q556", anzahl="2"),
        _b("Q283", "Q556", p2670="true"),
    ]))
    assert ableitungen.fetch_p527_elemente(["Q283"])["Q283"]["Q556"]["schon_p2670"]
