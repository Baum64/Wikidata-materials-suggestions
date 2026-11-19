"""Pakete 1/2: Pilot-Auswahl und Kandidaten-Regeln - netzfrei."""
from dataclasses import replace
from pathlib import Path

import pytest

from pmdmap.assessment import (
    BEHALTEN, NEU_P1628, NEU_P1709, OFFEN, VERWERFEN, assess_candidate, assess_property,
)
from pmdmap.candidates import label_match, pilot_materials, pilot_properties, resolve_label, score_item
from pmdmap.config import load_config
from pmdmap.ontology import load_ontology_file

from test_pmdmap_assessment import CO, TTL

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"

EXTRA = """
:PMD_0000852 a owl:Class ; rdfs:label "metal"@en .
:PMD_0000661 a owl:Class ; rdfs:subClassOf :PMD_0000000 ; rdfs:label "glass"@en ;
    <https://w3id.org/pmd/co/PMD_0000060> true .
:PMD_0050101 a owl:Class ; rdfs:subClassOf :PMD_0000661 ; rdfs:label "silicate glass"@en .
:PMD_0050106 a owl:Class ; rdfs:subClassOf :PMD_0050101 ; rdfs:label "borosilicate glass"@en .
:PMD_0010002 a owl:Class ; rdfs:subClassOf :PMD_0000852 ; rdfs:label "cast iron"@en .
:PMD_0000577 a owl:Class ; rdfs:subClassOf obo:BFO_0000027 ; rdfs:label "composite"@en .
obo:BFO_0000027 a owl:Class ; rdfs:label "object aggregate"@en ; rdfs:subClassOf obo:BFO_0000040 .
obo:BFO_0000040 a owl:Class ; rdfs:label "material entity"@en .
:PMD_0000773 a owl:Class ; rdfs:subClassOf :PMD_0020265 ; rdfs:label "hardness"@en , "Härte"@de .
"""


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    cfg = load_config(CONFIG)
    p = tmp_path_factory.mktemp("onto") / "mini.ttl"
    p.write_text(TTL + EXTRA, encoding="utf-8")
    onto = load_ontology_file(p, cfg.profile)
    snap = {"mappings": [{"entity": "Q1422588", "value": CO + "PMD_0050106", "prop": "P1709"}]}
    return cfg, onto, snap


def test_resolve_label(env):
    _, onto, _ = env
    assert resolve_label(onto, "steel") == CO + "PMD_0020096"
    assert resolve_label(onto, "Mass-Density") == CO + "PMD_0000597"    # normalisiert
    assert resolve_label(onto, "density") == CO + "PMD_0000597"         # Synonym
    assert resolve_label(onto, "wood") is None
    assert resolve_label(onto, "magnetic property") is None            # nur veraltete Klasse


def test_pilot_werkstoffe_pflicht_fehlend_und_auffuellen(env):
    cfg, onto, snap = env
    cfg = replace(cfg, pilot_materials={
        "pflicht": ["steel", "wood", "composite"], "zusatz": [], "max_klassen": 5,
        "wurzeln": [CO + "PMD_0000000", CO + "PMD_0000852"],
        "profil_annotation": CO + "PMD_0000060", "ausschliessen": [],
    })
    pilots, missing = pilot_materials(cfg, onto, snap)
    labels = [p.label for p in pilots]
    assert missing == ["wood"]
    assert labels[:2] == ["steel", "composite"]          # Pflicht zuerst, auch ohne material-Wurzel
    assert labels[2] == "glass"                          # Minimalprofil vor Unterklassen-Zahl
    assert "borosilicate glass" not in labels            # schon verlinkt (Paket 0)
    assert len(pilots) == 5


def test_pilot_eigenschaften_mit_hinweis_und_verlinkt(env):
    cfg, onto, snap = env
    cfg = replace(cfg, pilot_properties=({"label": "hardness", "hinweis": "Skalen"}, {"label": "wood"}))
    pilots, missing = pilot_properties(cfg, onto, snap)
    assert [p.label for p in pilots] == ["hardness"] and pilots[0].hint == "Skalen"
    assert missing == ["wood"]


def kandidat(qid="Q11427", label_en="steel", klasse=True, werkstoff=True, element=False, links=(), rang_hits=1):
    s = {"label_en": label_en, "label_de": "", "aliases_en": [], "aliases_de": []}
    return s, {"qid": qid, "hits": [f"Labelsuche en „x“ #{rang_hits}"], "is_class": klasse,
               "is_material": werkstoff, "is_element": element, "sitelinks": 50, "onto_links": list(links)}


def bewerte(env, iri, s, c, rank=1, paket="1", hint="", manual=None):
    cfg, onto, _ = env
    c["label_match"] = label_match(s, onto.get(iri))
    c["score"] = score_item(c, paket)
    pilot = {"paket": paket, "label": onto.label_of(iri), "iri": iri, "hint": hint}
    return assess_candidate(cfg, onto, pilot, c, rank, lambda n: {"close match": "Q39893184"}.get(n, ""), manual)


def test_bester_kandidat_mit_label_wird_p1709(env):
    a = bewerte(env, CO + "PMD_0020096", *kandidat())
    assert a.vorschlag == NEU_P1709 and not a.grenzfall


def test_kein_werkstoff_oder_keine_klasse_bleibt_offen(env):
    a = bewerte(env, CO + "PMD_0020096", *kandidat(werkstoff=False))
    assert a.vorschlag == OFFEN and "nicht-unter-material" in a.codes
    b = bewerte(env, CO + "PMD_0020096", *kandidat(klasse=False))
    assert b.vorschlag == OFFEN and b.grenzfall and "keine-klasse" in b.codes   # Instanz vs. Klasse


def test_schon_p1709_auf_andere_klasse(env):
    a = bewerte(env, CO + "PMD_0020096", *kandidat(links=["P1709:" + CO + "PMD_0000100"]))
    assert a.vorschlag == OFFEN and a.grenzfall and "hat-schon-abbildung" in a.codes


def test_pmd_composite_ist_kein_werkstoff(env):
    s, c = kandidat(qid="Q181790", label_en="composite")
    a = bewerte(env, CO + "PMD_0000577", s, c)
    assert a.vorschlag == OFFEN and "pmd-kein-werkstoff" in a.codes


def test_schwache_kandidaten_verwerfen(env):
    a = bewerte(env, CO + "PMD_0020096", *kandidat(qid="Q5", label_en="stainless steel"), rank=2)
    assert a.vorschlag == VERWERFEN
    b = bewerte(env, CO + "PMD_0020096", *kandidat(qid="Q6", label_en="Steel"), rank=2)
    assert b.vorschlag == OFFEN                        # zweiter exakter Treffer


def test_einschaetzung_setzt_p2888(env):
    manual = {"vorschlag": "neu: P2888+P4390", "p4390": "close match", "begruendung": "PMD enger"}
    a = bewerte(env, CO + "PMD_0020096", *kandidat(), manual=manual)
    assert a.vorschlag == "neu: P2888+P4390" and a.vorschlag_p4390 == "Q39893184"
    assert "Einschätzung: PMD enger" in a.begruendung


def eigenschaft(pid="P2054", datatype="quantity", via=("Q29539",), p1629=(), lm=None, p1628=()):
    return {"pid": pid, "datatype": datatype, "via_p1687": list(via), "hits": [], "p1629_hits": list(p1629),
            "label_match": lm or {}, "p1628": list(p1628), "score": 5}


def test_eigenschaft_ueber_p1687_wird_p1628(env):
    cfg, _, _ = env
    pilot = {"paket": "2", "label": "mass density", "iri": CO + "PMD_0000597", "hint": ""}
    a = assess_property(cfg, pilot, eigenschaft(), 1, lambda n: "")
    assert a.vorschlag == NEU_P1628 and "via-p1687" in a.codes


def test_eigenschaft_vorhanden_und_falscher_datentyp(env):
    cfg, _, _ = env
    pilot = {"paket": "2", "label": "mass density", "iri": CO + "PMD_0000597", "hint": "Hinweis X"}
    a = assess_property(cfg, pilot, eigenschaft(p1628=[CO + "PMD_0000597"]), 1, lambda n: "")
    assert a.vorschlag == BEHALTEN
    b = assess_property(cfg, pilot, eigenschaft(datatype="wikibase-item"), 1, lambda n: "")
    assert b.vorschlag == OFFEN and "datentyp" in b.codes and "Hinweis X" in b.begruendung
    c = assess_property(cfg, pilot, eigenschaft(via=()), 2, lambda n: "")
    assert c.vorschlag == VERWERFEN


def test_kandidaten_einschaetzungsdatei_gueltig():
    from pmdmap.assessment import VORSCHLAEGE_NEU, load_candidate_assessments
    cfg = load_config(CONFIG)
    data = load_candidate_assessments(cfg.profile.candidate_assessments_file)
    skos = {"exact match", "close match", "broad match", "narrow match", "related match"}
    for pmd, entries in data.items():
        assert pmd.startswith("PMD_") and pmd[4:].isdigit(), pmd
        for eid, e in entries.items():
            assert eid[0] in "QP" and eid[1:].isdigit(), eid
            assert set(e) <= {"vorschlag", "p4390", "grenzfall", "begruendung"}, eid
            assert e.get("vorschlag", OFFEN) in VORSCHLAEGE_NEU, eid
            assert e.get("p4390", "close match") in skos, eid
            assert e.get("begruendung"), f"{pmd}/{eid}: ohne Begründung"


def test_namensvetter_auf_rang_2_verwerfen(env):
    """Film/Spiel mit gleichem Label: keine Klasse -> verwerfen, kein Grenzfall."""
    a = bewerte(env, CO + "PMD_0020096", *kandidat(qid="Q7", label_en="steel", klasse=False), rank=2)
    assert a.vorschlag == VERWERFEN and not a.grenzfall
    b = bewerte(env, CO + "PMD_0020096", *kandidat(qid="Q8", label_en="steel", werkstoff=False), rank=3)
    assert b.vorschlag == VERWERFEN


def test_einschaetzung_hebt_grenzfall_auf(env):
    s, c = kandidat(label_en="iron-carbon alloy")             # kein Labeltreffer -> offen + Grenzfall
    assert bewerte(env, CO + "PMD_0020096", s, dict(c)).grenzfall
    a = bewerte(env, CO + "PMD_0020096", s, dict(c), manual={"vorschlag": "neu: P1709", "begruendung": "gleich"})
    assert a.vorschlag == NEU_P1709 and not a.grenzfall
