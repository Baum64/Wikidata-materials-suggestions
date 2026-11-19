"""Lesender Zugriff auf Wikidata: SPARQL (Query-Service) und Action-API.

SPARQL nur dort, wo es ohne nicht geht (A2, E1-Pruefung): der Query-Service
ist das Nadeloehr (Timeouts, zeitweise 1 Anfrage/Minute). Eintraege,
Constraints und Suche laufen ueber die Action-API.

Kein Massen-Scan ueber alle P1709/P2888-Aussagen: Einstieg ist immer die
MediaWiki-Linksuche (exturlusage) oder eine konkrete Liste von IDs.
"""
from __future__ import annotations

import sys
import time
from typing import Iterable

from .cache import Cache
from .config import WikidataConfig
from .http import HttpClient

class WikidataApiError(RuntimeError):
    def __init__(self, code: str, info: str):
        super().__init__(f"Wikidata-API {code}: {info}")
        self.code = code


ONE_OF_CONSTRAINT = "Q21510859"
PROPERTY_CONSTRAINT = "P2302"
ITEM_OF_CONSTRAINT = "P2305"


def query_a2(link_search: str, properties: Iterable[str]) -> str:
    """Abfrage A2 aus docs/konzept_bfo_wikidata_mapping.md ("Bestandsaufnahme
    der vorhandenen PMD-Links").

    Unveraendert bis auf drei Punkte: Linksuche und Properties kommen aus der
    Konfiguration (Profil, abbildungs_properties - damit auch P3950), und
    ?st steht im SELECT, damit jede Zeile einer Aussage zuzuordnen ist.
    """
    values = " ".join(f'(p:{p} ps:{p} "{p}")' for p in properties)
    return f"""SELECT ?item ?itemLabel ?prop ?uri ?st ?art ?artLabel WHERE {{
  SERVICE wikibase:mwapi {{
    bd:serviceParam wikibase:api "Generator" ;
                    wikibase:endpoint "www.wikidata.org" ;
                    mwapi:generator "exturlusage" ;
                    mwapi:geuquery "{link_search}" ;
                    mwapi:geuprotocol "https" ;
                    mwapi:geunamespace "0|120" ;
                    mwapi:geulimit "max" .
    ?item wikibase:apiOutputItem mwapi:title .
  }}
  VALUES (?p ?ps ?prop) {{ {values} }}
  ?item ?p ?st . ?st ?ps ?uri .
  FILTER(CONTAINS(STR(?uri), "{link_search}"))
  OPTIONAL {{ ?st pq:P4390 ?art . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}}
ORDER BY ?prop ?itemLabel"""


def query_direct_subclasses(parents: Iterable[str]) -> str:
    """Schritt 1 der E1-Pruefung: direkte P279-Unterklassen der Kandidaten."""
    values = " ".join(f"wd:{q}" for q in parents)
    return f"""SELECT ?parent ?child ?childLabel WHERE {{
  VALUES ?parent {{ {values} }}
  ?child wdt:P279 ?parent .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
}}"""




def _simplify(binding: dict) -> dict[str, str]:
    return {k: v["value"] for k, v in binding.items()}


def entity_id(uri_or_title: str) -> str:
    """'http://www.wikidata.org/entity/Q42' / 'Property:P31' -> 'Q42' / 'P31'."""
    tail = uri_or_title.rsplit("/", 1)[-1]
    return tail.split(":", 1)[-1]


class WikidataClient:
    def __init__(self, cfg: WikidataConfig, http: HttpClient, cache: Cache):
        self.cfg = cfg
        self.http = http
        self.cache = cache

    # --- SPARQL -------------------------------------------------------------
    def sparql(self, query: str) -> list[dict[str, str]]:
        key = Cache.key("sparql", query)
        cached = self.cache.get_json("sparql", key)
        if cached is not None:
            return cached
        resp = self.http.request(
            "POST",
            self.cfg.sparql_url,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        rows = [_simplify(b) for b in resp.json()["results"]["bindings"]]
        self.cache.put_json("sparql", key, rows, request=query)
        return rows

    # --- Action-API ---------------------------------------------------------
    # API-Fehler, die mit HTTP 200 kommen, aber vorueberghend sind
    # (19.11.2026: "cirrussearch-too-busy-error" bei der Volltextsuche)
    TRANSIENT_ERRORS = ("cirrussearch-too-busy-error", "maxlag", "ratelimited", "readonly")

    def api(self, params: dict, attempts: int = 4) -> dict:
        params = {"format": "json", "formatversion": "2", **params}
        key = Cache.key("api", params)
        cached = self.cache.get_json("api", key)
        if cached is not None:
            return cached
        wait = 15.0
        for attempt in range(1, attempts + 1):
            resp = self.http.request("GET", self.cfg.api_url, params=params)
            data = resp.json()
            code = data.get("error", {}).get("code", "")
            if code in self.TRANSIENT_ERRORS and attempt < attempts:
                print(f"  API {code} - Versuch {attempt}/{attempts}, warte {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                wait *= 2
                continue
            if "error" in data:
                raise WikidataApiError(code, data["error"].get("info", ""))
            self.cache.put_json("api", key, data, request=params)
            return data
        raise WikidataApiError("unerreichbar", str(params))  # pragma: no cover

    def exturlusage(self, query: str, namespace: str = "*", protocol: str = "https") -> list[dict]:
        """Alle Seiten mit externem Link auf query (Praefix, ohne Protokoll)."""
        out: list[dict] = []
        cont: dict = {}
        while True:
            data = self.api({
                "action": "query", "list": "exturlusage", "euquery": query,
                "euprotocol": protocol, "eunamespace": namespace,
                "eulimit": "max", "euprop": "ids|title|url", **cont,
            })
            out.extend(data.get("query", {}).get("exturlusage", []))
            if "continue" not in data:
                return out
            cont = data["continue"]

    def get_entities(
        self,
        ids: Iterable[str],
        props: str = "labels|descriptions|aliases|claims|sitelinks",
        languages: str = "de|en",
    ) -> dict[str, dict]:
        """wbgetentities in Bloecken zu 50 (API-Grenze)."""
        ids = sorted(set(ids), key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
        out: dict[str, dict] = {}
        for i in range(0, len(ids), 50):
            data = self.api({
                "action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                "props": props, "languages": languages,
            })
            for eid, ent in data.get("entities", {}).items():
                if "missing" not in ent:
                    out[eid] = ent
        return out

    def labels(self, ids: Iterable[str]) -> dict[str, dict[str, str]]:
        ents = self.get_entities(ids, props="labels")
        return {
            eid: {lang: v["value"] for lang, v in ent.get("labels", {}).items()}
            for eid, ent in ents.items()
        }

    def allowed_values(self, pid: str) -> list[str]:
        """Erlaubte Werte einer Property laut one-of-Constraint (P2302/P2305)."""
        ent = self.get_entities([pid], props="claims")[pid]
        values: list[str] = []
        for st in ent.get("claims", {}).get(PROPERTY_CONSTRAINT, []):
            if st.get("rank") == "deprecated":
                continue
            if claim_item(st) != ONE_OF_CONSTRAINT:
                continue
            for q in st.get("qualifiers", {}).get(ITEM_OF_CONSTRAINT, []):
                v = q.get("datavalue", {}).get("value", {})
                if isinstance(v, dict) and "id" in v:
                    values.append(v["id"])
        return list(dict.fromkeys(values))

    def p279_closure(self, ids: Iterable[str], max_depth: int = 30) -> dict[str, dict]:
        """P279-Huelle nach oben: {qid: {p279, label, desc_en, mapping_links}}.

        Ueber die Action-API statt SPARQL ("?x wdt:P279+ wd:root"): der
        Query-Service lief damit am 19.11.2026 selbst fuer 99 Klassen in
        HTTP 504. Hier wird die Kette Ebene fuer Ebene verfolgt (50 Eintraege
        je Anfrage, gecacht). mapping_links zaehlt P1709/P2888/P3950-Aussagen
        - ein Hinweis auf einen eigens nachgebauten Ontologie-Eintrag."""
        nodes: dict[str, dict] = {}
        frontier = set(ids)
        for _ in range(max_depth):
            todo = sorted(q for q in frontier if q not in nodes)
            if not todo:
                break
            ents = self.get_entities(todo, props="labels|descriptions|claims", languages="de|en")
            frontier = set()
            for q in todo:
                ent = ents.get(q, {})
                nodes[q] = {
                    "p279": item_values(ent, "P279"),
                    "label": text(ent, "labels", "de") or text(ent, "labels", "en"),
                    "desc_en": text(ent, "descriptions", "en"),
                    "mapping_links": sum(len(ent.get("claims", {}).get(p, [])) for p in ("P1709", "P2888", "P3950")),
                }
                frontier.update(nodes[q]["p279"])
        return nodes

    def search(self, text: str, language: str, limit: int = 3) -> list[dict]:
        data = self.api({
            "action": "wbsearchentities", "search": text, "language": language,
            "uselang": language, "type": "item", "limit": limit,
        })
        return data.get("search", [])


# --- Hilfen fuer Aussagen (JSON der Action-API) -----------------------------
def claim_item(statement: dict) -> str | None:
    v = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
    return v.get("id") if isinstance(v, dict) else None


def claim_string(statement: dict) -> str | None:
    v = statement.get("mainsnak", {}).get("datavalue", {}).get("value")
    return v if isinstance(v, str) else None


def item_values(entity: dict, pid: str) -> list[str]:
    """Werte (QIDs) einer Item-Property, ohne veraltete Aussagen."""
    return [
        q for st in entity.get("claims", {}).get(pid, [])
        if st.get("rank") != "deprecated" and (q := claim_item(st))
    ]


def text(entity: dict, kind: str, lang: str) -> str:
    return entity.get(kind, {}).get(lang, {}).get("value", "")


def aliases(entity: dict, lang: str) -> list[str]:
    return [a["value"] for a in entity.get("aliases", {}).get(lang, [])]
