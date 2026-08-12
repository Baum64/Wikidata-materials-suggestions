"""Pure comparison logic: no network calls in this module, so it is fully
unit-testable offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .wikipedia_client import WikiLink


@dataclass
class LinkComparison:
    title: str
    qid: Optional[str]
    status: str  # "matched" | "missing" | "no_wikidata_item"
    via_properties: List[str] = field(default_factory=list)


def compare_links(
    wp_links: List[WikiLink],
    wd_outgoing_claims: Dict[str, List[str]],
) -> List[LinkComparison]:
    """Compare Wikipedia outgoing links against Wikidata outgoing item-claims.

    Parameters
    ----------
    wp_links: every outgoing article link of the source Wikipedia article,
        each with the QID of the linked article (or None).
    wd_outgoing_claims: {target_qid: [property_id, ...]} for the *source*
        article's Wikidata item -- i.e. what Wikidata already models as a
        direct relationship to another item.

    Returns
    -------
    One LinkComparison per Wikipedia link, classified as:
    - "matched": the linked article's QID is also a claim target in Wikidata.
    - "missing": Wikipedia links to it, but no Wikidata statement connects
      the two items -- a candidate for enrichment.
    - "no_wikidata_item": the linked article has no Wikidata item at all, so
      no comparison is possible.
    """
    results: List[LinkComparison] = []
    for link in wp_links:
        if link.qid is None:
            results.append(LinkComparison(link.title, None, "no_wikidata_item"))
            continue
        if link.qid in wd_outgoing_claims:
            results.append(
                LinkComparison(
                    link.title,
                    link.qid,
                    "matched",
                    via_properties=wd_outgoing_claims[link.qid],
                )
            )
        else:
            results.append(LinkComparison(link.title, link.qid, "missing"))
    return results


def summarize(results: List[LinkComparison]) -> Dict[str, int]:
    summary = {"matched": 0, "missing": 0, "no_wikidata_item": 0, "total": len(results)}
    for r in results:
        summary[r.status] += 1
    return summary


def missing_only(results: List[LinkComparison]) -> List[LinkComparison]:
    return [r for r in results if r.status == "missing"]
