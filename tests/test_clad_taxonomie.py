"""Clad-/Plattierwerkstoffe als eigene Verbundwerkstoffklasse, nach
.claude/rules/ontology-verbundwerkstoffe.md.

Netzwerkfrei: pruefe_clad_taxonomie rechnet nur auf dem P279-Graphen, den
P31-Werten und den Bezeichnungen, die der Lauf ohnehin geholt hat.
"""
import importlib.util
import os

import networkx as nx
import pytest

_PFAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "Material class structure", "ClassCheck.py")
_spec = importlib.util.spec_from_file_location("classcheck_clad", _PFAD)
vg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vg)

CCA = "Q112310011"   # Copper clad aluminium (48% Copper, 52% Aluminium)
CCS = "Q3815254"     # Copper-clad steel (P279 -> Stahl)
STAHL = "Q11427"
MATERIAL = vg.MATERIAL_QID
COMPOSITE = vg.COMPOSITE_MATERIAL_QID


def kandidat(qid, label):
    return {qid: {"label_de": "", "label_en": label,
                  "desc_de": "", "desc_en": ""}}


def graph_mit(*kanten):
    g = nx.DiGraph()
    g.add_nodes_from([COMPOSITE, MATERIAL, STAHL])
    g.add_edges_from(kanten)
    return g


def lauf(kandidaten, graph, p31_werte=None):
    labels = {STAHL: "Stahl", MATERIAL: "material", COMPOSITE: "composite material"}
    return vg.pruefe_clad_taxonomie(kandidaten, graph, p31_werte or {}, labels)


# ---------------------------------------------------------------------------
# Der Regelfall
# ---------------------------------------------------------------------------

def test_clad_unter_material_wird_unter_composite_material_gehaengt():
    treffer = lauf(kandidat(CCA, "Copper clad aluminium"),
                   graph_mit((CCA, MATERIAL)))
    haupt = [b for b in treffer if b["befund"] == "clad-taxonomie"]
    assert len(haupt) == 1
    qs = haupt[0]["quickstatements"].splitlines()
    assert f"-{CCA}\tP279\t{MATERIAL}" in qs
    assert f"{CCA}\tP279\t{COMPOSITE}" in qs


def test_clad_als_art_von_stahl_wird_umgehaengt():
    """"Copper-clad steel" P279 -> Stahl ist der Kernfall: kein "eine Art
    Stahl", sondern ein eigener Verbundwerkstoff."""
    treffer = lauf(kandidat(CCS, "Copper-clad steel"),
                   graph_mit((CCS, STAHL)))
    qs = treffer[0]["quickstatements"].splitlines()
    assert f"-{CCS}\tP279\t{STAHL}" in qs
    assert f"{CCS}\tP279\t{COMPOSITE}" in qs


def test_p31_wird_auf_p279_umgestellt():
    treffer = lauf(kandidat(CCA, "Copper clad aluminium"),
                   graph_mit(), p31_werte={CCA: [MATERIAL]})
    haupt = treffer[0]
    assert f"-{CCA}\tP31\t{MATERIAL}" in haupt["quickstatements"]
    assert haupt["eigenschaft"] == "P31 -> P279"
    assert "Klasse (P279)" in haupt["begruendung"]


def test_fehlende_zwischenklasse_wird_als_meldung_gemeldet():
    treffer = lauf(kandidat(CCA, "Copper clad aluminium"),
                   graph_mit((CCA, MATERIAL)))
    meldung = [b for b in treffer if b["befund"] == "clad-klasse-fehlt"]
    assert len(meldung) == 1
    assert meldung[0]["quickstatements"] == ""
    assert "clad-klasse-fehlt" in vg.REVIEW_NEEDED_ARTEN


# ---------------------------------------------------------------------------
# Wo nichts entworfen wird
# ---------------------------------------------------------------------------

def test_kein_clad_marker_kein_befund():
    assert lauf(kandidat("Q34095", "Bronze"), graph_mit()) == []


def test_schon_unter_composite_material_eingehaengt():
    treffer = lauf(kandidat(CCA, "Copper clad aluminium"),
                   graph_mit((CCA, COMPOSITE)))
    assert treffer == []


def test_bestehende_bimetal_kante_bleibt_stehen():
    """P279 -> bimetal (Q746634) ist bereits eine richtige Verbund-Oberklasse
    und wird nicht entfernt."""
    treffer = lauf(kandidat(CCA, "Copper clad aluminium"),
                   graph_mit((CCA, "Q746634"), (CCA, MATERIAL)))
    qs = treffer[0]["quickstatements"]
    assert "Q746634" not in qs
    assert f"-{CCA}\tP279\t{MATERIAL}" in qs


# ---------------------------------------------------------------------------
# Staffelung
# ---------------------------------------------------------------------------

def test_entwurf_steht_in_stufe_drei_meldung_in_stufe_vier():
    stufe = {nummer: arten for nummer, _, arten, *_ in vg.STUFEN}
    assert "clad-taxonomie" in stufe[3]
    assert "clad-klasse-fehlt" in stufe[4]
