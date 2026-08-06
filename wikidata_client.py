"""Client for the Wikidata (wbgetentities) API.

Responsible for fetching the outgoing "item -> item" statements of a Wikidata
entity, i.e. every claim whose value is itself another Wikidata item
(P31 "instance of", P279 "subclass of", P527 "has part", etc.), and for
resolving property IDs (P123) to human-readable labels.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

import requests

from .wikipedia_client import USER_AGENT

WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


class WikidataClient:
    def __init__(self, lang: str = "de", session: Optional[requests.Session] = None):
        self.lang = lang
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get_outgoing_item_claims(self, qid: str) -> Dict[str, List[str]]:
        """Return {target_qid: [property_id, ...]} for every direct claim of
        `qid` whose value is another Wikidata item.

        A target can (rarely) be reached via more than one property, hence the
        list of property ids per target.
        """
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "props": "claims",
            "format": "json",
            "formatversion": "2",
        }
        data = self._get(params)
        entity = data.get("entities", {}).get(qid, {})
        claims = entity.get("claims", {})

        targets: Dict[str, List[str]] = defaultdict(list)
        for prop_id, statements in claims.items():
            for statement in statements:
                mainsnak = statement.get("mainsnak", {})
                if mainsnak.get("datatype") != "wikibase-item":
                    continue
                datavalue = mainsnak.get("datavalue")
                if not datavalue:
                    continue  # e.g. "unknown value" snaks
                target_qid = datavalue.get("value", {}).get("id")
                if target_qid:
                    targets[target_qid].append(prop_id)
        return dict(targets)

    def get_property_labels(self, prop_ids: List[str]) -> Dict[str, str]:
        """Batch-resolve property ids (e.g. P31) to labels in self.lang,
        falling back to English, falling back to the id itself.
        """
        labels: Dict[str, str] = {}
        for i in range(0, len(prop_ids), 50):  # API allows up to 50 ids/request
            batch = prop_ids[i : i + 50]
            params = {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "labels",
                "languages": f"{self.lang}|en",
                "format": "json",
                "formatversion": "2",
            }
            data = self._get(params)
            for pid, entity in data.get("entities", {}).items():
                entity_labels = entity.get("labels", {})
                label = entity_labels.get(self.lang) or entity_labels.get("en")
                labels[pid] = label["value"] if label else pid
        return labels

    def _get(self, params: dict) -> dict:
        resp = self.session.get(WIKIDATA_API_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
