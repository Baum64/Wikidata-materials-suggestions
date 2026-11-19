"""Pakete 1 und 2: Kandidaten fuer fehlende Abbildungen suchen - nur Vorschlaege.

Paket 1 (Pilot-Werkstoffe): je Ontologieklasse die besten Wikidata-Eintraege.
Paket 2 (Pilot-Eigenschaften, E7): je Qualitaetsklasse der Begriffs-Eintrag
UND - fuer P1628 - die passende Wikidata-Eigenschaft.

Suche je Klasse mit Label (en, de) und Synonymen ueber
  - wbsearchentities (Label-/Alias-Praefix, type=item bzw. property)
  - Volltextsuche (list=search) mit "haswbstatement:P279", damit auch
    Klassen gefunden werden, deren Label nicht mit dem Suchwort beginnt.
Bewertet wird transparent (score_* unten); die Bewertung ist nur die
Reihenfolge, der Vorschlag kommt aus assessment.assess_candidate.
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field

from .assessment import normalize
from .config import Config
from .inventory import _entity_summary, _qnum, reaching
from .ontology import Ontology
from .wikidata import WikidataApiError, WikidataClient, claim_string, item_values


@dataclass
class PilotClass:
    paket: str
    label: str                    # wie in der Konfiguration
    iri: str | None               # None = fehlt in der Ontologie
    reason: str                   # warum im Pilot
    hint: str = ""
    linked: list[str] = field(default_factory=list)   # bereits abgebildete Eintraege (Paket 0)


# --- Auswahl der Pilot-Klassen ---------------------------------------------
def resolve_label(onto: Ontology, label: str) -> str | None:
    """Klasse mit genau diesem Label oder Synonym (en), nicht veraltet."""
    want = normalize(label)
    base = onto.profile.base_iri
    hits = [
        iri for iri, c in onto.classes.items()
        if iri.startswith(base) and not c.deprecated
        and want in {normalize(x) for x in [c.labels.get("en", ""), *c.synonyms.get("en", [])] if x}
    ]
    return sorted(hits)[0] if hits else None


def _linked(snap: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in snap["mappings"]:
        out.setdefault(m["value"], []).append(m["entity"])
    return out


def pilot_materials(cfg: Config, onto: Ontology, snap: dict) -> tuple[list[PilotClass], list[str]]:
    pm = cfg.pilot_materials
    linked = _linked(snap)
    limit = int(pm.get("max_klassen", 20))
    excluded = set(pm.get("ausschliessen", []))
    out: list[PilotClass] = []
    missing: list[str] = []
    seen: set[str] = set()

    def add(iri: str, label: str, reason: str) -> None:
        if iri in seen or iri in excluded or len(out) >= limit:
            return
        seen.add(iri)
        out.append(PilotClass("1", label, iri, reason, linked=linked.get(iri, [])))

    for label in pm.get("pflicht", []):
        iri = resolve_label(onto, label)
        if iri:
            add(iri, label, "Pflicht (Aufgabe)")
        else:
            missing.append(label)
    for iri in pm.get("zusatz", []):
        if onto.get(iri):
            add(iri, onto.label_of(iri), "Zusatz (config)")

    # Auffuellen: unverlinkt, unter den Wurzeln, Minimalprofil zuerst
    roots = set(pm.get("wurzeln", []))
    flag = pm.get("profil_annotation", "")
    children: dict[str, set[str]] = {}
    for k, c in onto.classes.items():
        for p in c.parents:
            children.setdefault(p, set()).add(k)

    def n_desc(k: str) -> int:
        seen_d, stack = set(), [k]
        while stack:
            for ch in children.get(stack.pop(), ()):
                if ch not in seen_d:
                    seen_d.add(ch)
                    stack.append(ch)
        return len(seen_d)

    pool = []
    for iri, c in onto.classes.items():
        if c.deprecated or iri in linked or iri in roots or not iri.startswith(onto.profile.base_iri):
            continue
        if not roots & set(onto.ancestors(iri)):
            continue
        pool.append((flag in c.flags, n_desc(iri), iri))
    for in_profile, nd, iri in sorted(pool, key=lambda t: (-t[0], -t[1], t[2])):
        add(iri, onto.label_of(iri), f"aufgefüllt: {'Minimalprofil, ' if in_profile else ''}{nd} Unterklassen")
    return out, missing


def pilot_properties(cfg: Config, onto: Ontology, snap: dict) -> tuple[list[PilotClass], list[str]]:
    linked = _linked(snap)
    out, missing = [], []
    for entry in cfg.pilot_properties:
        iri = resolve_label(onto, entry["label"])
        if not iri:
            missing.append(entry["label"])
            continue
        out.append(PilotClass("2", entry["label"], iri, "Pilot-Eigenschaft (Aufgabe)",
                              entry.get("hinweis", ""), linked.get(iri, [])))
    return out, missing


# --- Suche -------------------------------------------------------------------
def _queries(onto: Ontology, iri: str) -> list[tuple[str, str]]:
    c = onto.get(iri)
    qs: list[tuple[str, str]] = []
    for lang in ("en", "de"):
        for text in [c.labels.get(lang, ""), *c.synonyms.get(lang, [])]:
            text = text.strip()
            if text and (text, lang) not in qs:
                qs.append((text, lang))
    return qs


def search_items(wd: WikidataClient, queries: list[tuple[str, str]], limit: int,
                 entity_type: str = "item", warnings: list[str] | None = None) -> dict[str, list[str]]:
    """{ID: ['wbsearch en #1', 'volltext de #3', ...]} - woher ein Treffer kommt."""
    hits: dict[str, list[str]] = {}
    for text, lang in queries:
        res = wd.api({
            "action": "wbsearchentities", "search": text, "language": lang, "uselang": lang,
            "type": entity_type, "limit": limit,
        }).get("search", [])
        for rank, r in enumerate(res, 1):
            hits.setdefault(r["id"], []).append(f"Labelsuche {lang} „{text}“ #{rank}")
        if entity_type == "item":
            try:
                res = wd.api({
                    "action": "query", "list": "search", "srnamespace": 0, "srlimit": limit,
                    "srsearch": f'"{text}" haswbstatement:P279', "srprop": "",
                }).get("query", {}).get("search", [])
            except WikidataApiError as exc:
                # Volltext ist eine Ergaenzung - faellt sie aus, bleibt die
                # Labelsuche; der Ausfall steht im Bericht (warnings).
                if warnings is not None:
                    warnings.append(f"Volltextsuche „{text}“ ({lang}) ausgefallen: {exc.code}")
                res = []
            for rank, r in enumerate(res, 1):
                hits.setdefault(r["title"], []).append(f"Volltext {lang} „{text}“ #{rank}")
    return hits


# --- Bewertung (nur Reihenfolge) --------------------------------------------
def label_match(summary: dict, onto_cls) -> dict[str, str]:
    """{'en': 'label'|'alias', 'de': ...} fuer exakte (normalisierte) Treffer."""
    out = {}
    for lang in ("en", "de"):
        pmd = {normalize(x) for x in [onto_cls.labels.get(lang, ""), *onto_cls.synonyms.get(lang, [])] if x}
        if not pmd:
            continue
        if normalize(summary.get(f"label_{lang}", "")) in pmd:
            out[lang] = "label"
        elif {normalize(a) for a in summary.get(f"aliases_{lang}", [])} & pmd:
            out[lang] = "alias"
    return out


def score_item(c: dict, paket: str) -> float:
    s = 0.0
    lm = c["label_match"]
    s += {"label": 5, "alias": 3}.get(lm.get("en", ""), 0) + {"label": 4, "alias": 2}.get(lm.get("de", ""), 0)
    s += 1.0 / min(int(h.rsplit("#", 1)[1]) for h in c["hits"])           # bester Suchrang
    s += min(len(c["hits"]), 4) * 0.25                                   # in mehreren Suchen
    s += 1 if c["is_class"] else -2                                      # E6: keine Einzelsorten
    if paket == "1":
        s += 2 if c["is_material"] else -1
    if c["is_element"]:
        s -= 1
    s += min(c["sitelinks"], 100) / 100
    return round(s, 2)


def score_property(p: dict) -> float:
    s = 0.0
    if p["via_p1687"]:
        s += 3
    if p["p1629_hits"]:
        s += 3
    s += {"label": 2, "alias": 1}.get(p["label_match"].get("en", ""), 0)
    s += {"label": 1, "alias": 0.5}.get(p["label_match"].get("de", ""), 0)
    if p["datatype"] == "quantity":
        s += 1
    if p["hits"]:
        s += 1.0 / min(int(h.rsplit("#", 1)[1]) for h in p["hits"])
    return round(s, 2)


# --- Sammeln -----------------------------------------------------------------
def collect(cfg: Config, wd: WikidataClient, onto: Ontology, snap: dict, pakete: list[str]) -> dict:
    settings = cfg.candidate_settings
    limit = int(settings["suchtreffer"])
    needle = cfg.profile.link_search
    pilots: list[PilotClass] = []
    missing: dict[str, list[str]] = {}
    if "1" in pakete:
        p, m = pilot_materials(cfg, onto, snap)
        pilots += p
        missing["1"] = m
    if "2" in pakete:
        p, m = pilot_properties(cfg, onto, snap)
        pilots += p
        missing["2"] = m

    # 1. Suche
    extra = {str(k): [str(x) for x in v] for k, v in (settings.get("zusatz") or {}).items()}
    min_score = float(settings.get("min_score", float("-inf")))
    warnings: list[str] = []
    raw_hits: dict[str, dict[str, list[str]]] = {}
    for pc in pilots:
        if pc.linked:          # bereits abgebildet (Paket 0) - keine neuen Begriffs-Kandidaten
            raw_hits[pc.iri] = {}
            continue
        print(f"Suche Kandidaten: {pc.label}", file=sys.stderr)
        raw_hits[pc.iri] = search_items(wd, _queries(onto, pc.iri), limit, warnings=warnings)
        for eid in extra.get(pc.iri.rsplit("/", 1)[-1], []):
            if eid.startswith("Q"):
                raw_hits[pc.iri].setdefault(eid, []).append("Zusatz (config) #1")

    # 2. Details aller Kandidaten (+ bereits verlinkte, fuer P1687)
    ids = {q for h in raw_hits.values() for q in h if q.startswith("Q")}
    ids |= {q for pc in pilots for q in pc.linked}
    ents = wd.get_entities(sorted(ids, key=_qnum)) if ids else {}
    summaries = {q: _entity_summary(e) for q, e in ents.items()}

    # Werkstoff? (P279-Kette nach oben, wie bei E1)
    root = cfg.wikidata.material_root
    nodes = wd.p279_closure(set(summaries), max_depth=12) if summaries else {}
    materials = reaching(nodes, root)

    def onto_links(q: str) -> list[str]:
        return [
            f"{pid}:{v}" for pid in cfg.wikidata.mapping_properties
            for st in ents.get(q, {}).get("claims", {}).get(pid, [])
            if (v := claim_string(st)) and needle in v
        ]

    result: dict[str, dict] = {}
    for pc in pilots:
        cls = onto.get(pc.iri)
        cands = []
        for q, hits in raw_hits[pc.iri].items():
            if q not in summaries:
                continue
            s = summaries[q]
            c = {
                "qid": q, "hits": hits, "label_match": label_match(s, cls),
                "is_class": bool(s["p279"]), "is_material": q in materials,
                "is_element": cfg.wikidata.element_class in s["p31"],
                "sitelinks": s["sitelinks"], "onto_links": onto_links(q),
            }
            c["score"] = score_item(c, pc.paket)
            if c["score"] >= min_score or "Zusatz (config) #1" in hits:
                cands.append(c)
        cands.sort(key=lambda c: (-c["score"], _qnum(c["qid"])))
        result[pc.iri] = {"pilot": asdict(pc), "candidates": cands[: int(settings["je_klasse"])],
                          "candidates_total": len(cands), "properties": []}

    # 3. Paket 2: Wikidata-Eigenschaften fuer P1628
    prop_pilots = [pc for pc in pilots if pc.paket == "2"]
    if prop_pilots:
        per_pilot: dict[str, dict[str, dict]] = {}
        for pc in prop_pilots:
            cls = onto.get(pc.iri)
            basis = pc.linked or [c["qid"] for c in result[pc.iri]["candidates"]]
            found: dict[str, dict] = {}
            for q in basis:
                for pid in summaries.get(q, {}).get("p1687", []):
                    found.setdefault(pid, {"via_p1687": [], "hits": []})["via_p1687"].append(q)
            for pid, hits in search_items(wd, [(t, l) for t, l in _queries(onto, pc.iri) if l == "en"],
                                          limit, entity_type="property").items():
                found.setdefault(pid, {"via_p1687": [], "hits": []})["hits"] = hits
            for eid in extra.get(pc.iri.rsplit("/", 1)[-1], []):
                if eid.startswith("P"):
                    found.setdefault(eid, {"via_p1687": [], "hits": []})["hits"].append("Zusatz (config) #1")
            per_pilot[pc.iri] = found
        pids = sorted({p for f in per_pilot.values() for p in f})
        pents = wd.get_entities(pids, props="labels|descriptions|aliases|claims|datatype") if pids else {}
        for pc in prop_pilots:
            cls = onto.get(pc.iri)
            basis = set(pc.linked or [c["qid"] for c in result[pc.iri]["candidates"]])
            props = []
            for pid, f in per_pilot[pc.iri].items():
                e = pents.get(pid)
                if not e:
                    continue
                s = _entity_summary(e)
                p1629 = item_values(e, "P1629")
                p = {
                    "pid": pid, "summary": s, "datatype": e.get("datatype", ""),
                    "via_p1687": f["via_p1687"], "hits": f["hits"],
                    "p1629": p1629, "p1629_hits": sorted(set(p1629) & basis),
                    "label_match": label_match(s, cls),
                    "p1628": [claim_string(st) for st in e.get("claims", {}).get("P1628", []) if claim_string(st)],
                }
                p["score"] = score_property(p)
                props.append(p)
            props.sort(key=lambda p: (-p["score"], _qnum(p["pid"])))
            result[pc.iri]["properties"] = props[: int(settings["je_eigenschaft"])]
        summaries.update({pid: _entity_summary(e) for pid, e in pents.items()})

    # Labels fuer P31/P279-Anzeige
    target_ids = {t for s in summaries.values() for k in ("p31", "p279") for t in s[k]}
    labels = wd.labels(sorted(target_ids, key=_qnum)) if target_ids else {}
    labels.update(snap.get("labels", {}))

    return {
        "profile": cfg.profile.key,
        "retrieved": time.strftime("%Y-%m-%d"),
        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M"),
        "pakete": pakete,
        "missing": missing,
        "classes": result,
        "entities": summaries,
        "labels": labels,
        "warnings": warnings,
        "hit_sources": dict(Counter(h.split(" ", 1)[0] for r in raw_hits.values() for hs in r.values() for h in hs)),
    }
