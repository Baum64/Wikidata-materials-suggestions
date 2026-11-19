"""Ontologie laden (rdflib) und als einfachen Klassen-Index bereitstellen.

Ausgelesen je Klasse: IRI, rdfs:label (en/de), skos:altLabel als Synonyme,
Definition (skos:definition, ersatzweise IAO_0000115), benannte Oberklassen,
Veraltet-Markierung (owl:deprecated) samt Ersatz (IAO_0100001).
Version aus owl:versionIRI bzw. owl:versionInfo.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS

from .cache import Cache
from .config import OntologyProfile
from .http import HttpClient
from .iri import IriScheme

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
OBO = Namespace("http://purl.obolibrary.org/obo/")
IAO_DEFINITION = OBO["IAO_0000115"]
IAO_REPLACED_BY = OBO["IAO_0100001"]
DCT = Namespace("http://purl.org/dc/terms/")

LANGS = ("en", "de")
# Erhoehen, wenn sich der Aufbau des Index aendert - ein alter Index im Cache
# wird dann aus der gecachten Turtle-Datei neu gebaut (kein neuer Download).
INDEX_VERSION = 2


def _lang(lit: Literal) -> str:
    """'en-us' -> 'en'; ohne Sprachangabe gilt Englisch (PMDco-Praxis)."""
    return (lit.language or "en").split("-")[0].lower()


@dataclass
class OntologyClass:
    iri: str
    labels: dict[str, str] = field(default_factory=dict)
    synonyms: dict[str, list[str]] = field(default_factory=dict)
    definitions: dict[str, str] = field(default_factory=dict)
    parents: list[str] = field(default_factory=list)
    deprecated: bool = False
    replaced_by: str | None = None
    # Annotations-Properties mit Literalwert true (z. B. PMDco isInMinimalProfile)
    flags: list[str] = field(default_factory=list)

    def label(self, lang: str = "en") -> str:
        return self.labels.get(lang) or next(iter(self.labels.values()), self.iri.rsplit("/", 1)[-1])

    def definition(self, lang: str = "en") -> str:
        return self.definitions.get(lang) or next(iter(self.definitions.values()), "")


@dataclass
class OntologyMeta:
    profile: str
    version: str
    version_iri: str
    created: str
    source_url: str
    retrieved: str           # ISO-Datum des Abrufs (fuer S813)
    sha256: str = ""
    github_latest: str = ""  # neueste Release laut GitHub (nur Abgleich)


class Ontology:
    def __init__(self, meta: OntologyMeta, classes: dict[str, OntologyClass], profile: OntologyProfile):
        self.meta = meta
        self.classes = classes
        self.profile = profile
        self._anc: dict[str, list[str]] = {}

    # --- Abfragen ---------------------------------------------------------
    def get(self, iri: str) -> OntologyClass | None:
        return self.classes.get(iri)

    def ancestors(self, iri: str) -> list[str]:
        """Alle benannten Oberklassen (transitiv), naechste zuerst."""
        if iri in self._anc:
            return self._anc[iri]
        out: list[str] = []
        queue = list(self.classes[iri].parents) if iri in self.classes else []
        while queue:
            p = queue.pop(0)
            if p in out or p == iri:
                continue
            out.append(p)
            if p in self.classes:
                queue.extend(self.classes[p].parents)
        self._anc[iri] = out
        return out

    def category(self, iri: str) -> str:
        """Begriffsart nach den Ankerklassen des Profils (erste gewinnt)."""
        chain = {iri, *self.ancestors(iri)}
        for anchor in self.profile.categories:
            if anchor.anchor in chain:
                return anchor.kind
        return "sonstige"

    def label_of(self, iri: str, lang: str = "en") -> str:
        c = self.classes.get(iri)
        return c.label(lang) if c else iri.rsplit("/", 1)[-1]

    # --- Serialisierung (Cache) ------------------------------------------
    def to_json(self) -> dict:
        return {
            "index_version": INDEX_VERSION,
            "meta": asdict(self.meta),
            "classes": {k: asdict(v) for k, v in self.classes.items()},
        }

    @classmethod
    def from_json(cls, data: dict, profile: OntologyProfile) -> "Ontology":
        return cls(
            OntologyMeta(**data["meta"]),
            {k: OntologyClass(**v) for k, v in data["classes"].items()},
            profile,
        )


# --- Aufbau aus RDF ------------------------------------------------------
def _named_parents(g: Graph, c: URIRef) -> list[str]:
    """rdfs:subClassOf auf benannte Klassen plus die benannten Glieder einer
    owl:equivalentClass-Schnittmenge (PMDco definiert so z. B. Werkstoffklassen)."""
    out: list[str] = []
    for o in g.objects(c, RDFS.subClassOf):
        if isinstance(o, URIRef):
            out.append(str(o))
    for eq in g.objects(c, OWL.equivalentClass):
        if isinstance(eq, BNode):
            for members in g.objects(eq, OWL.intersectionOf):
                for m in Collection(g, members):
                    if isinstance(m, URIRef):
                        out.append(str(m))
    return list(dict.fromkeys(out))


def build_index(g: Graph, scheme: IriScheme) -> dict[str, OntologyClass]:
    """Alle owl:Class-IRIs indizieren - auch fremde (BFO, IAO), damit die
    Oberklassen-Kette bis zu den Ankerklassen reicht."""
    classes: dict[str, OntologyClass] = {}
    for c in set(g.subjects(RDF.type, OWL.Class)):
        if not isinstance(c, URIRef):
            continue
        oc = OntologyClass(iri=str(c))
        for lit in g.objects(c, RDFS.label):
            if isinstance(lit, Literal):
                oc.labels.setdefault(_lang(lit), str(lit).strip())
        for lit in g.objects(c, SKOS.altLabel):
            if isinstance(lit, Literal):
                oc.synonyms.setdefault(_lang(lit), []).append(str(lit).strip())
        for prop in (SKOS.definition, IAO_DEFINITION):
            for lit in g.objects(c, prop):
                if isinstance(lit, Literal):
                    oc.definitions.setdefault(_lang(lit), " ".join(str(lit).split()))
        oc.parents = _named_parents(g, c)
        dep = g.value(c, OWL.deprecated)
        oc.deprecated = bool(dep is not None and str(dep).lower() == "true")
        rep = g.value(c, IAO_REPLACED_BY)
        oc.replaced_by = str(rep) if rep is not None else None
        oc.flags = sorted({
            str(p) for p, o in g.predicate_objects(c)
            if isinstance(o, Literal) and str(o).lower() == "true" and p != OWL.deprecated
        })
        classes[str(c)] = oc
    return classes


def _ontology_header(g: Graph, base_iri: str) -> tuple[str, str, str]:
    onto = URIRef(base_iri)
    if (onto, RDF.type, OWL.Ontology) not in g:
        onto = next(iter(g.subjects(RDF.type, OWL.Ontology)), onto)
    version_iri = str(g.value(onto, OWL.versionIRI) or "")
    version = str(g.value(onto, OWL.versionInfo) or "") or version_iri.rstrip("/").rsplit("/", 1)[-1]
    created = str(g.value(onto, DCT.created) or "")
    return version, version_iri, created


def _github_latest(http: HttpClient, repo: str | None) -> str:
    if not repo:
        return ""
    try:
        resp = http.request("GET", f"https://api.github.com/repos/{repo}/releases/latest")
        return resp.json().get("tag_name", "")
    except Exception as exc:  # nur Abgleich - darf den Lauf nicht abbrechen
        print(f"  GitHub-Abgleich fehlgeschlagen: {exc}", file=sys.stderr)
        return ""


def load_ontology(profile: OntologyProfile, http: HttpClient, cache: Cache) -> Ontology:
    """Ontologie aus dem Cache oder neu laden.

    Der Index (JSON) wird gecacht, weil das Parsen der Turtle-Datei einige
    Sekunden dauert; die Rohdatei bleibt daneben liegen (je Version), damit
    jeder Bericht auf eine konkrete Datei verweisen kann.
    """
    index_path = cache.path(profile.key, "ontology_index.json")
    if cache.is_fresh(index_path):
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if data.get("index_version") == INDEX_VERSION:
            return Ontology.from_json(data, profile)
        # alter Index: aus der gecachten Rohdatei derselben Version neu bauen
        meta = OntologyMeta(**data["meta"])
        raw_path = cache.path(profile.key, f"{profile.key}-{meta.version or 'unbekannt'}.ttl")
        if raw_path.exists():
            print(f"Baue Ontologie-Index neu (Version {INDEX_VERSION}) aus {raw_path.name}", file=sys.stderr)
            g = Graph()
            g.parse(str(raw_path), format="turtle")
            onto = Ontology(meta, build_index(g, IriScheme.from_profile(profile)), profile)
            index_path.write_text(json.dumps(onto.to_json(), ensure_ascii=False), encoding="utf-8")
            return onto

    scheme = IriScheme.from_profile(profile)
    last_error: Exception | None = None
    for url in profile.download_urls:
        try:
            print(f"Lade Ontologie {profile.short_name}: {url}", file=sys.stderr)
            resp = http.request("GET", url, headers={"Accept": "text/turtle"})
            g = Graph()
            g.parse(data=resp.content, format="turtle")
        except Exception as exc:
            last_error = exc
            print(f"  fehlgeschlagen: {exc}", file=sys.stderr)
            continue
        version, version_iri, created = _ontology_header(g, profile.base_iri)
        raw_path = cache.path(profile.key, f"{profile.key}-{version or 'unbekannt'}.ttl")
        raw_path.write_bytes(resp.content)
        meta = OntologyMeta(
            profile=profile.key,
            version=version,
            version_iri=version_iri,
            created=created,
            source_url=resp.url,
            retrieved=time.strftime("%Y-%m-%d"),
            sha256=hashlib.sha256(resp.content).hexdigest(),
            github_latest=_github_latest(http, profile.github_repo),
        )
        onto = Ontology(meta, build_index(g, scheme), profile)
        index_path.write_text(json.dumps(onto.to_json(), ensure_ascii=False), encoding="utf-8")
        return onto
    raise SystemExit(f"Ontologie {profile.short_name} nicht ladbar: {last_error}")


def load_ontology_file(path: str | Path, profile: OntologyProfile) -> Ontology:
    """Ontologie aus einer lokalen Datei (fuer Tests und Offline-Laeufe)."""
    g = Graph()
    g.parse(str(path), format="turtle")
    version, version_iri, created = _ontology_header(g, profile.base_iri)
    meta = OntologyMeta(profile.key, version, version_iri, created, str(path), time.strftime("%Y-%m-%d"))
    return Ontology(meta, build_index(g, IriScheme.from_profile(profile)), profile)
