"""Beschleunigung: Drosselung je Gegenstelle, Aussagenbestand in Chargen,
Quellen ueberspringen. Alles netzwerkfrei."""
import time

import pytest

from materialswiki import cli, gruppen, netz, wikidata
# Die echte Funktion, an der Netzsperre der conftest vorbei: sie wird dort
# fuer alle uebrigen Tests durch eine Attrappe ersetzt.
from materialswiki.properties import STUFEN_PIDS
from materialswiki.wikidata import (
    claims_vorladen as echtes_vorladen,
    stufe_kann_nichts_beitragen,
)
from materialswiki.netz import request_with_retry as echtes_request


# ===========================================================================
# Drosselung je Gegenstelle
# ===========================================================================

def test_verschiedene_gegenstellen_warten_nicht_aufeinander(monkeypatch):
    """Sieben Server in einem Lauf: eine gemeinsame Uhr summierte deren
    Wartezeiten auf. Ruecksicht gilt jedem Server einzeln."""
    geschlafen = []
    monkeypatch.setattr(netz.time, "sleep", lambda s: geschlafen.append(s))
    monkeypatch.setattr(netz.requests, "request",
                        lambda *a, **kw: type("R", (), {"status_code": 200})())
    netz._LAST_REQUEST.clear()

    for url in ("https://query.wikidata.org/sparql",
                "https://www.crystallography.net/cod/result",
                "https://de.wikipedia.org/w/api.php"):
        echtes_request("GET", url)

    assert geschlafen == []          # drei Hosts, kein einziges Warten


def test_dieselbe_gegenstelle_wird_gedrosselt(monkeypatch):
    geschlafen = []
    monkeypatch.setattr(netz.time, "sleep", lambda s: geschlafen.append(s))
    monkeypatch.setattr(netz.requests, "request",
                        lambda *a, **kw: type("R", (), {"status_code": 200})())
    netz._LAST_REQUEST.clear()

    echtes_request("GET", "https://query.wikidata.org/sparql")
    echtes_request("GET", "https://query.wikidata.org/sparql?x=1")

    assert len(geschlafen) == 1 and 0 < geschlafen[0] <= netz.REQUEST_DELAY_SEC


# ===========================================================================
# Aussagenbestand in Chargen - und der Siedepunkt faellt dabei mit ab
# ===========================================================================

def antwort(entities):
    class Resp:
        @staticmethod
        def json():
            return {"entities": entities}
    return Resp()


def test_eine_anfrage_fuer_viele_items(monkeypatch):
    gerufen = []

    def fake(url, params):
        gerufen.append(params["ids"])
        return antwort({q: {"claims": {"P2054": [], "P31": []}}
                        for q in params["ids"].split("|")})

    monkeypatch.setattr(netz, "get_with_retry", fake)
    echtes_vorladen([f"Q{i}" for i in range(120)])

    # 120 Items, 50 je Anfrage -> drei Anfragen statt 120
    assert len(gerufen) == 3
    assert wikidata.fetch_item_pids("Q7") == {"P2054", "P31"}


def test_siedepunkt_kommt_aus_denselben_aussagen(monkeypatch):
    """Frueher eine eigene SPARQL-Abfrage JE ITEM - die Rohaussagen tragen
    Wert und Einheit laengst."""
    monkeypatch.setattr(netz, "get_with_retry", lambda url, params: antwort({
        "Q283": {"claims": {"P2102": [
            {"mainsnak": {"datavalue": {"value": {
                "amount": "+100", "unit":
                    "http://www.wikidata.org/entity/Q25267"}}}},   # 100 °C
            {"mainsnak": {"datavalue": {"value": {
                "amount": "+373.15", "unit":
                    "http://www.wikidata.org/entity/Q11579"}}}},   # 373,15 K
        ]}}}))
    echtes_vorladen(["Q283"])

    assert wikidata._SIEDEPUNKT_CACHE["Q283"] == pytest.approx(373.15)


def test_ohne_siedepunkt_bleibt_es_bei_none(monkeypatch):
    monkeypatch.setattr(netz, "get_with_retry", lambda url, params: antwort(
        {"Q1": {"claims": {"P31": []}}}))
    echtes_vorladen(["Q1"])

    assert wikidata._SIEDEPUNKT_CACHE["Q1"] is None
    assert wikidata.fetch_item_pids("Q1") == {"P31"}


# ===========================================================================
# Quellen ueberspringen, die nichts mehr beitragen koennen
# ===========================================================================

def test_stufe_wird_uebersprungen_wenn_alles_dasteht():
    wikidata._CLAIM_CACHE["Q1"] = set(STUFEN_PIDS["nist"])
    assert stufe_kann_nichts_beitragen("Q1", "nist") is True


def test_eine_fehlende_property_genuegt_fuer_den_abruf():
    """Halb gefuellt heisst: die Quelle kann noch etwas beitragen."""
    wikidata._CLAIM_CACHE["Q2"] = {"P3078"}          # P3071 fehlt
    assert stufe_kann_nichts_beitragen("Q2", "nist") is False


@pytest.mark.parametrize("stufe, erwartet", [
    ("cod", {"P9824", "P690", "P556", "P589"}),
    ("nist", {"P3078", "P3071"}),
])
def test_stufen_kennen_ihre_properties(stufe, erwartet):
    assert set(STUFEN_PIDS[stufe]) == erwartet


def test_mp_stufe_deckt_die_feldkarte_ab():
    """Kaeme eine Groesse in MP_FIELD_MAP dazu, ohne hier aufzutauchen,
    wuerde die Stufe zu frueh uebersprungen."""
    aus_karte = {cli.PROPERTY_MAP[k]["pid"]
                 for k, _ in cli.MP_FIELD_MAP.values() if k in cli.PROPERTY_MAP}
    assert aus_karte == set(STUFEN_PIDS["mp"])


# ===========================================================================
# Ueberschneidende Gruppen: was einen eigenen Aufruf hat, laeuft nicht doppelt
# ===========================================================================

def _item(qid):
    return {"qid": qid, "label": qid, "formula": "", "title_de": "",
            "title_en": ""}


@pytest.fixture
def zwei_gruppen(monkeypatch):
    monkeypatch.setitem(gruppen.WERKSTOFFGRUPPEN, "testgruppe", {
        "pattern": "?i wdt:P31 wd:Q1 .", "beschreibung": "Test",
        "ausschluss": ("oxide",),
    })
    monkeypatch.setattr(gruppen, "fetch_group_items",
                        lambda pattern: [_item(f"Q{i}") for i in range(1, 6)])
    monkeypatch.setattr(gruppen, "gruppen_qids", lambda g: {"Q2", "Q4"})


def test_items_der_anderen_gruppe_fallen_weg(zwei_gruppen):
    """Sie laufen im eigenen Aufruf mit - zweimal dasselbe vorzuschlagen
    hilft niemandem."""
    items = gruppen.items_der_gruppe("testgruppe")
    assert [e["qid"] for e in items] == ["Q1", "Q3", "Q5"]


def test_limit_zaehlt_die_wirklich_bearbeiteten(zwei_gruppen):
    """Der Ausschluss greift VOR --limit: 2 heisst zwei bearbeitete Items,
    nicht zwei minus die ausgeschlossenen."""
    assert len(gruppen.items_der_gruppe("testgruppe", 2)) == 2


def test_mit_ueberschneidungen_bleibt_alles(zwei_gruppen):
    items = gruppen.items_der_gruppe("testgruppe", ausschluss=False)
    assert [e["qid"] for e in items] == ["Q1", "Q2", "Q3", "Q4", "Q5"]


def test_ausgefallene_abfrage_schliesst_nichts_aus(monkeypatch, zwei_gruppen):
    """Lieber doppelt bearbeitet als still um Items gebracht."""
    def platzt(gruppe):
        raise RuntimeError("Endpunkt weg")
    monkeypatch.setattr(gruppen, "gruppen_qids", platzt)

    assert len(gruppen.items_der_gruppe("testgruppe")) == 5


def test_minerale_lassen_die_oxide_aus():
    """Die konfigurierte Regel selbst - sonst faellt eine geloeschte Zeile
    in WERKSTOFFGRUPPEN nicht auf."""
    assert gruppen.WERKSTOFFGRUPPEN["minerale"]["ausschluss"] == ("oxide",)
    assert "ausschluss" not in gruppen.WERKSTOFFGRUPPEN["oxide"]
