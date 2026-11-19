"""Retry/Drosselung des pmdmap-Netzzugangs - netzfrei (_send ersetzt)."""
import pytest
import requests

from pmdmap import http
from pmdmap.config import NetConfig


def antwort(status, headers=None):
    r = requests.Response()
    r.status_code = status
    r.headers.update(headers or {})
    r.url = "https://query.wikidata.org/sparql"
    return r


@pytest.fixture
def client(monkeypatch):
    schlaf = []
    monkeypatch.setattr(http.time, "sleep", schlaf.append)
    net = NetConfig("pmdmap-test", {"default": 0}, attempts=4, wait_429_s=61, timeout_s=5)
    return http.HttpClient(net), schlaf


def test_429_mit_retry_after(monkeypatch, client):
    c, schlaf = client
    folge = iter([antwort(429, {"Retry-After": "7"}), antwort(200)])
    monkeypatch.setattr(http, "_send", lambda *a, **k: next(folge))
    assert c.request("GET", "https://query.wikidata.org/sparql").status_code == 200
    assert 7.0 in schlaf


def test_429_ohne_header_wartet_konfiguriert(monkeypatch, client):
    c, schlaf = client
    folge = iter([antwort(429), antwort(200)])
    monkeypatch.setattr(http, "_send", lambda *a, **k: next(folge))
    c.request("GET", "https://query.wikidata.org/sparql")
    assert 61 in schlaf


def test_4xx_sofort_fehler(monkeypatch, client):
    c, _ = client
    aufrufe = []
    monkeypatch.setattr(http, "_send", lambda *a, **k: aufrufe.append(1) or antwort(404))
    with pytest.raises(requests.HTTPError):
        c.request("GET", "https://www.wikidata.org/w/api.php")
    assert len(aufrufe) == 1


def test_5xx_bis_zum_letzten_versuch(monkeypatch, client):
    c, _ = client
    aufrufe = []
    monkeypatch.setattr(http, "_send", lambda *a, **k: aufrufe.append(1) or antwort(502))
    with pytest.raises(requests.HTTPError):
        c.request("GET", "https://www.wikidata.org/w/api.php")
    assert len(aufrufe) == 4


def test_user_agent_gesetzt(client):
    c, _ = client
    assert c.session.headers["User-Agent"] == "pmdmap-test"


def test_p279_huelle_und_erreichbarkeit_zyklensicher(tmp_path):
    """P279-Kette nach oben, mit Zyklus und Sackgasse - ohne Netz."""
    from pmdmap.cache import Cache
    from pmdmap.inventory import reaching
    from pmdmap.wikidata import WikidataClient

    graph = {"Q1": ["Q2"], "Q2": ["Q3"], "Q3": ["Q214609"], "Q4": ["Q5"], "Q5": ["Q4"], "Q6": [],
             "Q214609": ["Q141158787"], "Q141158787": []}

    class Fake(WikidataClient):
        def get_entities(self, ids, props="", languages=""):
            return {q: {"claims": {"P279": [
                {"mainsnak": {"datavalue": {"value": {"id": p}}}, "rank": "normal"} for p in graph.get(q, [])
            ]}} for q in ids}

    nodes = Fake(None, None, Cache(tmp_path, 1)).p279_closure(["Q1", "Q4", "Q6"])
    assert set(nodes) == set(graph)                    # bis ueber die Wurzel hinaus
    assert reaching(nodes, "Q214609") == {"Q1", "Q2", "Q3", "Q214609"}


def test_api_wiederholt_voruebergehende_fehler(tmp_path, monkeypatch):
    """HTTP 200 mit {"error": too-busy} wird wiederholt, nicht gecacht."""
    from pmdmap import wikidata
    from pmdmap.cache import Cache
    from pmdmap.config import WikidataConfig

    monkeypatch.setattr(wikidata.time, "sleep", lambda s: None)
    antworten = iter([{"error": {"code": "cirrussearch-too-busy-error", "info": "busy"}}, {"query": {"search": []}}])

    class R:
        def __init__(self, d): self.d = d
        def json(self): return self.d

    class H:
        def request(self, *a, **k): return R(next(antworten))

    cfg = WikidataConfig("s", "a", (), "P4390", "Q11344", "Q214609")
    wd = wikidata.WikidataClient(cfg, H(), Cache(tmp_path, 1))
    assert wd.api({"action": "query"}) == {"query": {"search": []}}


def test_api_dauerhafter_fehler(tmp_path):
    from pmdmap import wikidata
    from pmdmap.cache import Cache
    from pmdmap.config import WikidataConfig

    class H:
        def request(self, *a, **k):
            class R:
                def json(self): return {"error": {"code": "badvalue", "info": "x"}}
            return R()

    wd = wikidata.WikidataClient(WikidataConfig("s", "a", (), "P4390", "Q11344", "Q214609"), H(), Cache(tmp_path, 1))
    with pytest.raises(wikidata.WikidataApiError) as e:
        wd.api({"action": "query"})
    assert e.value.code == "badvalue"
