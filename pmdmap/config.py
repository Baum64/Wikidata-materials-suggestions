"""config.yaml lesen.

Alles, was sich zwischen PMDco und einer spaeteren zweiten Ontologie (MWO)
unterscheidet, steckt im OntologyProfile. Der restliche Code kennt keine
PMD-spezifischen Konstanten.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CategoryAnchor:
    anchor: str
    kind: str


@dataclass(frozen=True)
class OntologyProfile:
    key: str
    name: str
    short_name: str
    source_qid: str
    base_iri: str
    iri_pattern: str
    link_search: str
    download_urls: tuple[str, ...]
    github_repo: str | None
    categories: tuple[CategoryAnchor, ...]
    assessments_file: Path | None
    candidate_assessments_file: Path | None = None


@dataclass(frozen=True)
class NetConfig:
    user_agent: str
    throttle_s: dict[str, float]
    attempts: int
    wait_429_s: float
    timeout_s: float


@dataclass(frozen=True)
class WikidataConfig:
    sparql_url: str
    api_url: str
    mapping_properties: tuple[str, ...]
    mapping_relation_property: str
    element_class: str
    material_root: str


@dataclass(frozen=True)
class Config:
    root: Path
    profile: OntologyProfile
    output_dir: Path
    review_needed: Path
    cache_dir: Path
    cache_max_age_days: float
    net: NetConfig
    wikidata: WikidataConfig
    suspects: dict[str, str] = field(default_factory=dict)
    e1_new_from_qid: int = 0
    # (Suchbegriff ohne Protokoll, Protokoll)
    e1_extra_link_searches: tuple[tuple[str, str], ...] = ()
    e1_construct_description: str = ""
    # Pakete 1/2 - roh aus config.yaml, ausgewertet in candidates.py
    pilot_materials: dict = field(default_factory=dict)
    pilot_properties: tuple = ()
    candidate_settings: dict = field(default_factory=dict)


def _profile(key: str, raw: dict, root: Path) -> OntologyProfile:
    assessments = raw.get("einschaetzungen")
    cand_assessments = raw.get("einschaetzungen_kandidaten")
    return OntologyProfile(
        key=key,
        name=raw["name"],
        short_name=raw.get("kurzname", key),
        source_qid=raw["quelle_qid"],
        base_iri=raw["basis_iri"],
        iri_pattern=raw["iri_muster"],
        link_search=raw["linksuche"],
        download_urls=tuple(raw["download"]),
        github_repo=raw.get("github_repo"),
        categories=tuple(
            CategoryAnchor(c["anker"], c["art"]) for c in raw.get("kategorien", [])
        ),
        assessments_file=(root / assessments) if assessments else None,
        candidate_assessments_file=(root / cand_assessments) if cand_assessments else None,
    )


def load_config(path: str | Path = "config.yaml", ontology: str | None = None) -> Config:
    """config.yaml lesen; relative Pfade gelten relativ zur Datei."""
    path = Path(path).resolve()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = path.parent

    key = ontology or raw["ontologie"]
    profiles = raw["ontologien"]
    if key not in profiles:
        raise SystemExit(
            f"Ontologie '{key}' fehlt in {path.name}; vorhanden: {', '.join(profiles)}"
        )

    net = raw["netz"]
    user_agent = net["user_agent"]
    # Kontakt nur aus der Umgebung - so steht er weder im Repo noch geht er
    # ungefragt hinaus.
    contact = os.environ.get("PMDMAP_KONTAKT", "").strip()
    if contact:
        user_agent = f"{user_agent} ({contact})"

    wd = raw["wikidata"]
    e1 = raw.get("e1", {})
    return Config(
        root=root,
        profile=_profile(key, profiles[key], root),
        output_dir=root / raw["ausgabe_verzeichnis"],
        review_needed=root / raw["review_needed"],
        cache_dir=root / raw["cache_verzeichnis"],
        cache_max_age_days=float(raw.get("cache_gueltig_tage", 7)),
        net=NetConfig(
            user_agent=user_agent,
            throttle_s={k: float(v) for k, v in net.get("drosselung_s", {}).items()},
            attempts=int(net.get("versuche", 6)),
            wait_429_s=float(net.get("wartezeit_429_s", 61)),
            timeout_s=float(net.get("timeout_s", 120)),
        ),
        wikidata=WikidataConfig(
            sparql_url=wd["sparql"],
            api_url=wd["api"],
            mapping_properties=tuple(wd["abbildungs_properties"]),
            mapping_relation_property=wd["abbildungsart_property"],
            element_class=wd["element_klasse"],
            material_root=wd["werkstoff_wurzel"],
        ),
        suspects={str(k): str(v) for k, v in (raw.get("verdachtsfaelle") or {}).items()},
        e1_new_from_qid=int(e1.get("neu_ab_qid", 0)),
        e1_construct_description=str(e1.get("konstrukt_beschreibung", "")),
        e1_extra_link_searches=tuple(
            (s["suche"], s.get("protokoll", "https")) for s in e1.get("linksuche_zusatz", [])
        ),
        pilot_materials=dict(raw.get("pilot_werkstoffe") or {}),
        pilot_properties=tuple(
            p if isinstance(p, dict) else {"label": p} for p in (raw.get("pilot_eigenschaften") or [])
        ),
        candidate_settings={"je_klasse": 3, "je_eigenschaft": 2, "suchtreffer": 7, **(raw.get("kandidaten") or {})},
    )
