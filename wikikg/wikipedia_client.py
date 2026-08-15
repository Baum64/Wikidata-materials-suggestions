"""Client for the Wikipedia (MediaWiki) API.

Responsible for:
- Resolving an article title to its Wikidata QID.
- Fetching all outgoing hyperlinks (namespace 0 = articles only) of a page,
  together with the Wikidata QID of each linked page (in a single batch of
  requests, using MediaWiki's `generator=links` + `prop=pageprops` combo so we
  don't need one API call per link).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

import os
import sys

# konfig.py liegt im Repo-Wurzelverzeichnis.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import konfig  # noqa: E402
import requests

# Kontaktadresse aus .env im Repo-Wurzelverzeichnis - siehe .env.beispiel.
USER_AGENT = (
    "WikiKnowledgeGraph/0.1 (https://github.com/Baum64/WikiKnowledgeGraph; "
    f'contact: {konfig.wert("CONTACT_EMAIL", "set-your-email-here")})'
)


@dataclass(frozen=True)
class WikiLink:
    """A single outgoing link from the source article to another article."""

    title: str
    qid: Optional[str]  # None if the linked article has no Wikidata item


class WikipediaClient:
    def __init__(self, lang: str = "de", session: Optional[requests.Session] = None):
        self.lang = lang
        self.api_url = f"https://{lang}.wikipedia.org/w/api.php"
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def resolve_qid(self, title: str) -> Optional[str]:
        """Return the Wikidata QID for a given Wikipedia article title, or None."""
        params = {
            "action": "query",
            "prop": "pageprops",
            "titles": title,
            "format": "json",
            "formatversion": "2",
        }
        data = self._get(params)
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            return None
        page = pages[0]
        if page.get("missing"):
            return None
        return page.get("pageprops", {}).get("wikibase_item")

    def get_outgoing_links(self, title: str) -> Iterator[WikiLink]:
        """Yield every outgoing article-namespace link of `title`, each already
        annotated with the target's Wikidata QID (if it has one).

        Uses `generator=links` so that the linked pages -- including their
        pageprops -- come back in the same response as the link list itself,
        avoiding a separate lookup per link.
        """
        params = {
            "action": "query",
            "generator": "links",
            "titles": title,
            "gplnamespace": "0",   # only links to main-namespace articles
            "gpllimit": "max",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
            "format": "json",
            "formatversion": "2",
        }
        while True:
            data = self._get(params)
            for page in data.get("query", {}).get("pages", []):
                if page.get("missing"):
                    continue
                qid = page.get("pageprops", {}).get("wikibase_item")
                yield WikiLink(title=page["title"], qid=qid)

            if "continue" in data:
                params.update(data["continue"])
            else:
                break

    def _get(self, params: dict) -> dict:
        resp = self.session.get(self.api_url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
