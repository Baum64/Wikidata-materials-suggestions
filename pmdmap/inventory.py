"""Paket 0: Bestand der vorhandenen Ontologie-Links in Wikidata erheben.

Ablauf:
1. Linksuche (exturlusage) ueber alle Namensraeume - liefert die Zaehlung,
   die Special:LinkSearch zeigt (inkl. Projektseiten).
2. Abfrage A2 aus dem Konzept (SPARQL) - die "offizielle" Bestandszahl.
3. Alle Eintraege/Eigenschaften aus 1+2 per wbgetentities holen und die
   Abbildungs-Aussagen DIREKT aus den Claims lesen. Das deckt auch
   Properties ab, die A2 nicht kennt, und liefert Aussage-ID, Qualifier und
   Referenzen, die der Export spaeter braucht (Loeschzeilen!).
4. Abgleich 2 <-> 3, damit Luecken der A2-Abfrage sichtbar werden.
5. E1-Pruefung: neu angelegte Ontologie-/BFO-Eintraege als P279-Oberklasse
   von Werkstoff-Eintraegen.

Ergebnis ist ein JSON-Schnappschuss (cache/<profil>/bestand_<datum>.json),
aus dem "review" offline die Pruef-Tabelle baut.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from .config import Config
from .iri import IriScheme
from .ontology import Ontology
from .wikidata import (
    WikidataClient, aliases, claim_string, entity_id, item_values, query_a2,
    query_direct_subclasses, text,
)

SNAPSHOT_PREFIX = "bestand_"


def _qnum(qid: str) -> int:
    return int(qid[1:]) if qid[1:].isdigit() else 0


def _entity_summary(ent: dict) -> dict:
    return {
        "label_de": text(ent, "labels", "de"),
        "label_en": text(ent, "labels", "en"),
        "desc_de": text(ent, "descriptions", "de"),
        "desc_en": text(ent, "descriptions", "en"),
        "aliases_de": aliases(ent, "de"),
        "aliases_en": aliases(ent, "en"),
        "p31": item_values(ent, "P31"),
        "p279": item_values(ent, "P279"),
        "p1629": item_values(ent, "P1629"),   # Item fuer diese Eigenschaft (an Properties)
        "p1687": [                            # Wikidata-Eigenschaft zu diesem Item
            v["id"] for st in ent.get("claims", {}).get("P1687", [])
            if isinstance(v := st.get("mainsnak", {}).get("datavalue", {}).get("value"), dict)
            and "id" in v
        ],
        "sitelinks": len(ent.get("sitelinks", {})),
    }


def _mapping_statements(ent_id: str, ent: dict, needle: str) -> list[dict]:
    """Alle Aussagen eines Eintrags, deren Textwert in die Ontologie zeigt."""
    out = []
    for pid, statements in ent.get("claims", {}).items():
        for st in statements:
            value = claim_string(st)
            if not value or needle not in value:
                continue
            quals = st.get("qualifiers", {})
            out.append({
                "entity": ent_id,
                "prop": pid,
                "value": value,
                "statement_id": st.get("id", ""),
                "rank": st.get("rank", "normal"),
                "p4390": [
                    q["datavalue"]["value"]["id"] for q in quals.get("P4390", [])
                    if q.get("datavalue")
                ],
                "qualifiers": sorted(quals),
                "references": len(st.get("references", [])),
                "reference_props": sorted({
                    p for ref in st.get("references", []) for p in ref.get("snaks", {})
                }),
            })
    return out


def collect(cfg: Config, wd: WikidataClient, onto: Ontology) -> dict:
    prof = cfg.profile
    scheme = IriScheme.from_profile(prof)
    needle = prof.link_search

    # 1. Linksuche, alle Namensraeume
    print("Linksuche (exturlusage) ...", file=sys.stderr)
    usage = wd.exturlusage(needle, namespace="*")
    by_ns = Counter(str(u["ns"]) for u in usage)
    usage_entities = sorted({
        entity_id(u["title"]) for u in usage if u["ns"] in (0, 120)
    })

    # 2. A2
    print("Abfrage A2 (SPARQL) ...", file=sys.stderr)
    a2 = wd.sparql(query_a2(needle, cfg.wikidata.mapping_properties))
    a2_rows = [
        {
            "entity": entity_id(r["item"]), "prop": r["prop"], "value": r["uri"],
            "p4390": entity_id(r["art"]) if r.get("art") else "",
        }
        for r in a2
    ]

    # 3. Eintraege und Aussagen direkt
    ids = sorted({*usage_entities, *(r["entity"] for r in a2_rows)}, key=lambda x: (x[0], _qnum(x)))
    print(f"Hole {len(ids)} Eintraege/Eigenschaften (wbgetentities) ...", file=sys.stderr)
    ents = wd.get_entities(ids)
    statements = [s for eid in ids if eid in ents for s in _mapping_statements(eid, ents[eid], needle)]
    mapping_props = set(cfg.wikidata.mapping_properties)
    mappings = [s for s in statements if s["prop"] in mapping_props]
    other_links = [s for s in statements if s["prop"] not in mapping_props]

    # 4. Abgleich A2 <-> Claims
    a2_keys = {(r["entity"], r["prop"], r["value"]) for r in a2_rows}
    claim_keys = {(m["entity"], m["prop"], m["value"]) for m in mappings}
    not_in_a2 = sorted(claim_keys - a2_keys)
    not_in_claims = sorted(a2_keys - claim_keys)

    # Ontologie-Seite je Abbildung anreichern
    for m in mappings:
        cls = onto.get(m["value"])
        m["iri_ok"] = scheme.is_class_iri(m["value"])
        m["iri_problem"] = scheme.problem(m["value"])
        m["in_ontology"] = cls is not None
        m["category"] = onto.category(m["value"]) if cls else ""

    # E7: zugehoerige Wikidata-Eigenschaften (P1687) und ihre P1628-Werte
    linked_props = sorted({p for eid in ents for p in _entity_summary(ents[eid])["p1687"]})
    prop_ents = wd.get_entities(linked_props, props="labels|claims") if linked_props else {}
    property_p1628 = {
        pid: [claim_string(st) for st in ent.get("claims", {}).get("P1628", []) if claim_string(st)]
        for pid, ent in prop_ents.items()
    }

    # Erlaubte Abbildungsarten
    rel_pid = cfg.wikidata.mapping_relation_property
    allowed = wd.allowed_values(rel_pid)

    # 5. E1
    e1 = check_e1(
        cfg, wd, [m["entity"] for m in mappings],
        {m["entity"] for m in mappings if m["category"] == "werkstoff"},
    )

    summaries = {eid: _entity_summary(ent) for eid, ent in ents.items()}
    target_ids = {
        q for s in summaries.values() for k in ("p31", "p279") for q in s[k]
    } | set(allowed) | {q for m in mappings for q in m["p4390"]} | set(linked_props)
    target_ids |= {c["parent"] for c in e1["conflicts"]}
    labels = wd.labels(sorted(target_ids)) if target_ids else {}

    return {
        "profile": prof.key,
        "retrieved": time.strftime("%Y-%m-%d"),
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M"),
        "ontology": onto.meta.__dict__,
        "link_usage": {
            "query": needle,
            "total": len(usage),
            "by_namespace": dict(by_ns),
            "pages_ns4": sorted({u["title"] for u in usage if u["ns"] == 4}),
            "entities": usage_entities,
        },
        "a2_rows": a2_rows,
        "mappings": mappings,
        "other_links": other_links,
        "not_in_a2": [list(k) for k in not_in_a2],
        "not_in_claims": [list(k) for k in not_in_claims],
        "entities": summaries,
        "labels": labels,
        "property_p1628": property_p1628,
        "mapping_relation_allowed": allowed,
        "e1": e1,
    }


def check_e1(cfg: Config, wd: WikidataClient, mapped_entities: list[str],
             material_entities: set[str] = frozenset()) -> dict:
    """E1: Haengt ein Werkstoff-Eintrag per P279 an einem eigens angelegten
    Ontologie-Konstrukt (BFO, DOLCE, GSO, YAMATO ...)?

    Zwei Wege zu den Werkstoff-Eintraegen:
      a) die auf eine Werkstoffklasse der Ontologie abgebildeten Eintraege
         (material_entities) - von dort die P279-Kette nach oben;
      b) die direkten Unterklassen neu angelegter Eintraege mit PMD-/BFO-Link
         (SPARQL, billig) - falls dort Werkstoffe haengen, die (a) nicht kennt.
    Fuer alle so gefundenen Klassen wird die P279-Huelle nach oben ueber die
    Action-API geholt. Ein Werkstoff ist, was dort unter der Werkstoff-Wurzel
    haengt. Gemeldet wird jede Kante Werkstoff -> Konstrukt.

    Konstrukt = NEU angelegter Eintrag (ab e1.neu_ab_qid) mit eigener
    Abbildungs-Aussage (P1709/P2888/P3950 auf irgendeine Ontologie) oder mit
    einer Beschreibung nach e1.konstrukt_beschreibung ("DOLCE class" ...).
    Etablierte Klassen wie process (Q3249551) zaehlen nicht, auch wenn sie
    einen BFO-Link tragen. Entschieden wird hier nichts (-> review-needed.md).
    """
    new = lambda q: q.startswith("Q") and _qnum(q) >= cfg.e1_new_from_qid  # noqa: E731
    root = cfg.wikidata.material_root

    # (b) Kandidaten mit Link und deren direkte Unterklassen
    candidates: dict[str, str] = {}
    established: dict[str, int] = {}
    for q in mapped_entities:
        if new(q):
            candidates.setdefault(q, f"{cfg.profile.short_name}-Link")
    for search, protocol in cfg.e1_extra_link_searches:
        found = {entity_id(u["title"]) for u in wd.exturlusage(search, namespace="0", protocol=protocol)}
        established[search] = sum(1 for q in found if not new(q))
        for q in sorted(found, key=_qnum):
            if new(q):
                candidates.setdefault(q, f"Link auf {search}")
    children: set[str] = set()
    ids = sorted(candidates, key=_qnum)
    if ids:
        print(f"E1-Pruefung: Unterklassen von {len(ids)} Kandidaten (SPARQL) ...", file=sys.stderr)
        for i in range(0, len(ids), 150):
            for r in wd.sparql(query_direct_subclasses(ids[i:i + 150])):
                children.add(entity_id(r["child"]))

    # P279-Huelle nach oben fuer (a) und (b)
    seeds = set(material_entities) | children | {root}
    print(f"E1-Pruefung: P279-Kette von {len(seeds)} Klassen nach oben (API) ...", file=sys.stderr)
    nodes = wd.p279_closure(seeds)
    materials = reaching(nodes, root) | set(material_entities)

    pattern = re.compile(cfg.e1_construct_description) if cfg.e1_construct_description else None

    def construct(q: str) -> str | None:
        if not new(q):
            return None
        n = nodes.get(q, {})
        if n.get("mapping_links"):
            return f"neu angelegt, {n['mapping_links']} Abbildung(en) auf Fremdontologien"
        if pattern and pattern.search(n.get("desc_en", "")):
            return f"neu angelegt, Beschreibung „{n['desc_en']}“"
        if q in candidates:
            return f"neu angelegt, {candidates[q]}"
        return None

    conflicts = []
    for child in sorted(materials, key=_qnum):
        for parent in nodes.get(child, {}).get("p279", []):
            why = construct(parent)
            if why:
                conflicts.append({
                    "parent": parent,
                    "parent_label": nodes.get(parent, {}).get("label", ""),
                    "parent_desc": nodes.get(parent, {}).get("desc_en", ""),
                    "child": child,
                    "child_label": nodes.get(child, {}).get("label", ""),
                    "why_candidate": why,
                })
    return {
        "candidates": candidates,
        "established_skipped": established,
        "children_total": len(children),
        "closure_size": len(nodes),
        "materials_checked": len(materials),
        "conflicts": conflicts,
    }


def reaching(nodes: dict[str, dict], root: str) -> set[str]:
    """Alle Knoten der Huelle, die ueber P279 bei root ankommen (inkl. root).
    Fixpunkt statt Rekursion - zyklensicher."""
    reach = {root}
    changed = True
    while changed:
        changed = False
        for q, n in nodes.items():
            if q not in reach and any(p in reach for p in n.get("p279", [])):
                reach.add(q)
                changed = True
    return reach


# --- Schnappschuss ---------------------------------------------------------
def snapshot_path(cfg: Config, date: str) -> Path:
    p = cfg.cache_dir / cfg.profile.key / f"{SNAPSHOT_PREFIX}{date}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def save_snapshot(cfg: Config, snap: dict) -> Path:
    p = snapshot_path(cfg, snap["retrieved"])
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def latest_snapshot(cfg: Config) -> Path | None:
    files = sorted((cfg.cache_dir / cfg.profile.key).glob(f"{SNAPSHOT_PREFIX}*.json"))
    return files[-1] if files else None


def load_snapshot(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
