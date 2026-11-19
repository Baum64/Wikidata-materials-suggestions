"""Paket-0-Regeln an einer Mini-Ontologie - netzfrei."""
from pathlib import Path

import pytest

from pmdmap.assessment import BEHALTEN, OFFEN, P4390_ERGAENZEN, UMSTELLEN, Assessor
from pmdmap.config import load_config
from pmdmap.iri import IriScheme
from pmdmap.ontology import load_ontology_file

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"
CO = "https://w3id.org/pmd/co/"

TTL = """
@prefix : <https://w3id.org/pmd/co/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix obo: <http://purl.obolibrary.org/obo/> .

<https://w3id.org/pmd/co/> a owl:Ontology ; owl:versionIRI <https://w3id.org/pmd/co/3.1.2> .
:PMD_0000000 a owl:Class ; rdfs:label "material"@en .
:PMD_0020096 a owl:Class ; rdfs:subClassOf :PMD_0000000 ;
    rdfs:label "steel"@en , "Stahl"@de ; skos:definition "An iron alloy."@en .
:PMD_0000100 a owl:Class ; rdfs:subClassOf :PMD_0000000 ; rdfs:label "silicon"@en .
:PMD_0020265 a owl:Class ; rdfs:label "property"@en .
:PMD_0000597 a owl:Class ; rdfs:subClassOf :PMD_0020265 ; rdfs:label "mass density"@en ;
    skos:altLabel "density"@en .
:PMD_0000825 a owl:Class ; rdfs:label "DEPRECATED magnetic property"@en ; owl:deprecated true ;
    obo:IAO_0100001 :PMD_0000597 .
:PMD_0020202 a owl:Class ; rdfs:subClassOf obo:BFO_0000029 ; rdfs:label "crack"@en .
obo:BFO_0000029 a owl:Class ; rdfs:label "site"@en .
"""

ALLOWED = ["Q39893449", "Q39893184", "Q39893967", "Q39894595", "Q39894604"]
LABELS = {
    "Q39893449": {"en": "exact match"}, "Q39893184": {"en": "close match"},
    "Q39893967": {"en": "narrow match"}, "Q39894595": {"en": "broad match"},
    "Q39894604": {"en": "related match"}, "P2054": {"de": "Dichte", "en": "density"},
}


def ent(de="", en="", p31=(), p1687=(), **rest):
    return {"label_de": de, "label_en": en, "aliases_de": [], "aliases_en": [],
            "desc_de": "", "desc_en": "", "p31": list(p31), "p279": [], "p1629": [],
            "p1687": list(p1687), "sitelinks": 1, **rest}


def mapping(qid, iri, prop="P1709", p4390=(), onto=None, scheme=None):
    cls = onto.get(iri) if onto else None
    return {
        "entity": qid, "prop": prop, "value": iri, "statement_id": f"{qid}$x", "rank": "normal",
        "p4390": list(p4390), "qualifiers": [], "references": 0, "reference_props": [],
        "iri_ok": scheme.is_class_iri(iri), "iri_problem": scheme.problem(iri),
        "in_ontology": cls is not None, "category": onto.category(iri) if cls else "",
    }


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    cfg = load_config(CONFIG)
    p = tmp_path_factory.mktemp("onto") / "mini.ttl"
    p.write_text(TTL, encoding="utf-8")
    onto = load_ontology_file(p, cfg.profile)
    return cfg, onto, IriScheme.from_profile(cfg.profile)


def bewerte(setup, entities, mappings_spec, manual=None, p1628=None):
    cfg, onto, scheme = setup
    maps = [mapping(*m[:2], **m[2] if len(m) > 2 else {}, onto=onto, scheme=scheme) for m in mappings_spec]
    snap = {"entities": entities, "mappings": maps, "labels": LABELS,
            "mapping_relation_allowed": ALLOWED, "property_p1628": p1628 or {}}
    a = Assessor(cfg, onto, snap, manual or {})
    return [a.assess(m) for m in maps]


def test_ontologie_kategorien(setup):
    _, onto, _ = setup
    assert onto.category(CO + "PMD_0020096") == "werkstoff"
    assert onto.category(CO + "PMD_0000597") == "eigenschaft"
    assert onto.category(CO + "PMD_0020202") == "defekt/ort"
    assert onto.meta.version == "3.1.2"


def test_passendes_label_behalten(setup):
    (a,) = bewerte(setup, {"Q11427": ent("Stahl", "steel")}, [("Q11427", CO + "PMD_0020096")])
    assert a.vorschlag == BEHALTEN and not a.grenzfall
    assert a.vorschlag_p4390 == ""
    assert a.begruendung.startswith("Regel:")


def test_label_ueber_synonym(setup):
    (a,) = bewerte(setup, {"Q29539": ent("Dichte", "density")}, [("Q29539", CO + "PMD_0000597")])
    assert a.vorschlag == BEHALTEN


def test_abweichendes_label_ist_offen(setup):
    (a,) = bewerte(setup, {"Q1": ent("Werkzeug", "tool")}, [("Q1", CO + "PMD_0020096")])
    assert a.vorschlag == OFFEN and a.grenzfall
    assert "label-abweichung" in a.codes


def test_element_statt_werkstoff(setup):
    (a,) = bewerte(setup, {"Q670": ent("Silicium", "silicon", p31=["Q11344"])}, [("Q670", CO + "PMD_0000100")])
    assert a.vorschlag == UMSTELLEN and a.grenzfall
    assert {"element-statt-werkstoff", "verdachtsfall"} <= set(a.codes)
    assert "kein Fall 1–4" in a.begruendung


def test_p2888_ohne_p4390(setup):
    (a,) = bewerte(setup, {"Q5": ent("Stahl", "steel")}, [("Q5", CO + "PMD_0020096", {"prop": "P2888"})])
    assert a.vorschlag == P4390_ERGAENZEN
    assert "p4390-fehlt" in a.codes


def test_p3950_wird_narrow_match(setup):
    (a,) = bewerte(setup, {"Q5": ent("Stahl", "steel")}, [("Q5", CO + "PMD_0020096", {"prop": "P3950"})])
    assert a.vorschlag == UMSTELLEN and a.grenzfall
    assert a.vorschlag_p4390 == "Q39893967"     # aus dem Constraint, nicht hart codiert


def test_veraltete_und_unbekannte_iri(setup):
    a, b = bewerte(setup, {"Q1": ent("x", "x"), "Q2": ent("y", "y")},
                   [("Q1", CO + "PMD_0000825"), ("Q2", CO + "PMD_0123456")])
    assert a.vorschlag == OFFEN and "iri-veraltet" in a.codes and "PMD_0000597" in a.begruendung
    assert b.vorschlag == OFFEN and "iri-unbekannt" in b.codes


def test_mehrfachbelegung(setup):
    a, b = bewerte(setup, {"Q1": ent("Stahl", "steel"), "Q2": ent("Stahl", "steel")},
                   [("Q1", CO + "PMD_0020096"), ("Q2", CO + "PMD_0020096")])
    assert a.vorschlag == b.vorschlag == OFFEN
    assert "iri-mehrfach" in a.codes


def test_e7_p1628_kandidat(setup):
    (a,) = bewerte(setup, {"Q29539": ent("Dichte", "density", p1687=["P2054"])},
                   [("Q29539", CO + "PMD_0000597")], p1628={"P2054": []})
    assert "e7-p1628-fehlt" in a.codes and "P2054" in a.begruendung
    (b,) = bewerte(setup, {"Q29539": ent("Dichte", "density", p1687=["P2054"])},
                   [("Q29539", CO + "PMD_0000597")], p1628={"P2054": [CO + "PMD_0000597"]})
    assert "e7-p1628-vorhanden" in b.codes


def test_einschaetzung_ueberschreibt_vorschlag_nicht_befunde(setup):
    manual = {"Q1": {"vorschlag": UMSTELLEN, "p4390": "broad match", "begruendung": "PMD weiter gefasst"}}
    (a,) = bewerte(setup, {"Q1": ent("Werkzeug", "tool")}, [("Q1", CO + "PMD_0020096")], manual)
    assert a.vorschlag == UMSTELLEN
    assert a.vorschlag_p4390 == "Q39894595"
    assert "label-abweichung" in a.codes
    assert "Regel:" in a.begruendung and "Einschätzung: PMD weiter gefasst" in a.begruendung


def test_einschaetzung_mit_unbekanntem_vorschlag(setup):
    with pytest.raises(ValueError):
        bewerte(setup, {"Q1": ent("Stahl", "steel")}, [("Q1", CO + "PMD_0020096")], {"Q1": {"vorschlag": "ja"}})


def test_kein_werkstoff_nur_hinweis(setup):
    (a,) = bewerte(setup, {"Q3073047": ent("Riss", "crack")}, [("Q3073047", CO + "PMD_0020202")])
    assert a.vorschlag == BEHALTEN
    assert "kein-werkstoff" in a.codes


@pytest.mark.parametrize("a, b", [
    ("vacancy (crystal)", "vacancy"),
    ("auto-ignition temperature", "autoignition temperature"),
    ("Cross-linking", "crosslinking"),
    ("curing (polymers)", "curing"),
])
def test_label_normalisierung(a, b):
    from pmdmap.assessment import normalize
    assert normalize(a) == normalize(b)


def test_einschaetzungsdatei_gueltig():
    """Tippfehler in der YAML-Datei sollen hier auffallen, nicht erst im Lauf."""
    from pmdmap.assessment import VORSCHLAEGE, load_assessments
    cfg = load_config(CONFIG)
    data = load_assessments(cfg.profile.assessments_file)
    assert data, "Einschätzungsdatei leer oder nicht gefunden"
    skos = {"exact match", "close match", "broad match", "narrow match", "related match"}
    for qid, e in data.items():
        assert qid[0] == "Q" and qid[1:].isdigit(), qid
        assert set(e) <= {"vorschlag", "p4390", "grenzfall", "iri", "begruendung"}, qid
        assert e.get("vorschlag", BEHALTEN) in VORSCHLAEGE, qid
        assert e.get("p4390", "close match") in skos, qid
        assert e.get("begruendung"), f"{qid}: Einschätzung ohne Begründung"
