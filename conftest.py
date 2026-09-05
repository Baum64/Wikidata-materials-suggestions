# Its presence makes pytest treat this directory as the rootdir and add it to
# sys.path, so `import wikikg` works from tests/ without an editable install.

import pytest


@pytest.fixture(autouse=True)
def kein_netz(monkeypatch):
    """Sperrt den einzigen HTTP-Einstiegspunkt von materialswiki.

    Die Tests laufen offline - ohne diese Sperre reicht EIN neuer Aufruf tief
    im Code, damit die Suite still ins Netz geht. Genau das ist zweimal
    passiert: erst mit der COD-Stufe, dann mit der Siedepunkt-Abfrage, die
    ueber fetch_item_pids drei bestehende Tests von 0,1 s auf 5 s zog.

    Tests, die HTTP brauchen, setzen request_with_retry selbst per
    monkeypatch - eine spaetere Zuweisung gewinnt gegen diese hier.
    """
    from materialswiki import ableitungen, cli, netz, wikidata

    def gesperrt(method, url, *a, **kw):
        raise AssertionError(
            f"Test versucht einen Netzzugriff: {method} {url}\n"
            f"Entweder die aufrufende Funktion mocken oder, wenn der Zugriff "
            f"gewollt ist, request_with_retry im Test selbst ersetzen."
        )

    # Eine Sperre genuegt, weil alle Module ueber das MODUL aufrufen
    # (netz.request_with_retry) statt ueber eine eigene Namensbindung.
    monkeypatch.setattr(netz, "request_with_retry", gesperrt)

    # Neutraler Default fuer die Siedepunkt-Abfrage: "nicht ermittelbar".
    # Sie haengt an fetch_item_pids und damit am Netz, wird aber inzwischen
    # aus jeder Vorschlagszeile heraus aufgerufen. None heisst "nichts
    # behaupten, nichts unterdruecken" - genau das Verhalten, das die
    # bestehenden Tests erwarten. Tests zum Gas-Verhalten setzen es selbst.
    monkeypatch.setattr(wikidata, "siedepunkt_kelvin", lambda qid: None)

    # Aus demselben Grund der Aussagenbestand: er wird seit der Beschleunigung
    # chargenweise vorgeladen und haengt damit am Netz. "Nichts geladen"
    # bedeutet leerer Bestand - also wird keine Stufe uebersprungen, genau das
    # Verhalten, das die bestehenden Tests erwarten. Tests zum Ueberspringen
    # fuellen _CLAIM_CACHE selbst.
    monkeypatch.setattr(wikidata, "claims_vorladen", lambda qids: None)

    # Caches leeren, damit sich Tests nicht ueber Ergebnisse frueherer
    # Tests beeinflussen.
    wikidata._CLAIM_CACHE.clear()
    wikidata._SIEDEPUNKT_CACHE.clear()
    wikidata._MERKMAL_CACHE.clear()
    wikidata._UEBERSPRUNGEN.clear()
    ableitungen._METAKLASSE_CACHE.clear()
    ableitungen._P527_CACHE.clear()
    ableitungen._P527_WERTE.clear()
    wikidata._ITEM_RAUMGRUPPE_CACHE.clear()
    # Die Elementtabelle haengt am Netz und wird modulweit zwischengespeichert
    # - ohne Zuruecksetzen erbte ein Test die Tabelle des vorigen.
    wikidata._ELEMENT_QID_CACHE = None
    wikidata._SPACE_GROUP_CACHE = None
