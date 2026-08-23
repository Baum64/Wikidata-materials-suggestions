"""Chemische Metaklasse (P31) fuer Legierungen, nach
[[Wikidata:WikiProject Chemistry/Guidelines/Basic metaclasses and relations]].

Die Pruefung stand bis 2026-08-23 in materialswiki und liegt jetzt in
"Material class structure/Vorschläge generieren.py". Alles netzwerkfrei: die
Pruefung selbst rechnet nur auf dem Graphen und den P31-Kanten, die der Lauf
ohnehin geholt hat.
"""
import importlib.util
import os

import networkx as nx
import pytest

# "Material class structure/" ist kein Paket - das Modul kommt ueber den Pfad
# herein, wie in test_anwendung.py auch.
_PFAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "Material class structure", "Vorschläge generieren.py")
_spec = importlib.util.spec_from_file_location("vorschlaege_struktur", _PFAD)
vg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vg)

BRONZE = "Q34095"


@pytest.fixture
def items():
    return {BRONZE: {"qid": BRONZE, "label": "Bronze", "basis": "Copper"}}


def graph_mit(*kanten):
    """P279-Graph, Richtung Kind -> Elter."""
    g = nx.DiGraph()
    g.add_nodes_from([BRONZE, vg.LEGIERUNG_QID, vg.METALL_QID])
    g.add_edges_from(kanten)
    return g


def befunde(items, p31, graph=None, auch_mit_p31=False):
    graph = graph if graph is not None else graph_mit((BRONZE, vg.LEGIERUNG_QID))
    kanten = [(BRONZE, k) for k in p31]
    return vg.pruefe_metaklasse(
        items, vg.legierungs_items(graph, list(items), kanten), kanten,
        {BRONZE: "Bronze"}, auch_mit_p31)


# ===========================================================================
# Der Regelfall: Legierung ohne Metaklasse
# ===========================================================================

def test_legierung_ohne_metaklasse_bekommt_die_des_gemischs(items):
    """Eine Legierung ist per Definition ein Gemisch (Q37756: 'mixture or
    metallic solid solution'); die Guideline sieht dafuer eine eigene
    Metaklasse vor."""
    treffer = befunde(items, [])

    assert len(treffer) == 1
    assert treffer[0]["befund"] == "metaklasse"
    assert treffer[0]["quickstatements"] == f"{BRONZE}\tP31\t{vg.GEMISCH_METAKLASSE}"
    assert treffer[0]["ziel_qid"] == vg.GEMISCH_METAKLASSE   # Q119892838


def test_p31_zaehlt_als_einordnung_mit(items):
    """Ohne P279-Kante, aber 'ist ein/e Legierung' - auch das ist eine."""
    treffer = befunde(items, [vg.LEGIERUNG_QID], graph=graph_mit(),
                      auch_mit_p31=True)
    assert [b["befund"] for b in treffer] == ["metaklasse"]


def test_bestehendes_p31_bleibt_standardmaessig_unangetastet(items):
    """Wo schon eine Einordnung steht ("P31 = Legierung"), waere die
    Metaklasse eine ZWEITE P31-Aussage daneben. Die Guideline will sie, aber
    das ist eine Massenaenderung - sie braucht den ausdruecklichen Schalter."""
    assert befunde(items, [vg.LEGIERUNG_QID]) == []
    assert [b["befund"] for b in befunde(items, [vg.LEGIERUNG_QID],
                                         auch_mit_p31=True)] == ["metaklasse"]


def test_entwurf_traegt_die_warnung_vor_der_zweiten_aussage(items):
    treffer = befunde(items, [vg.LEGIERUNG_QID], auch_mit_p31=True)
    assert "ZWEITE" in treffer[0]["begruendung"]


# ===========================================================================
# Wo nichts entworfen wird
# ===========================================================================

def test_bestehende_gemisch_metaklasse_wird_nicht_wiederholt(items):
    assert befunde(items, [vg.GEMISCH_METAKLASSE]) == []
    assert befunde(items, [vg.GEMISCH_METAKLASSE], auch_mit_p31=True) == []


def test_andere_chemie_metaklasse_wird_gemeldet_nicht_ersetzt(items):
    """Messing traegt Q113145171 'definierte chemische Substanz' - fuer ein
    Gemisch die falsche. Die Guideline laesst nur EINE zu, die bestehende
    muesste also weichen. Loeschen tut dieses Werkzeug nicht."""
    treffer = befunde(items, ["Q113145171"])

    assert len(treffer) == 1
    assert treffer[0]["befund"] == "metaklasse-konflikt"
    assert "Q113145171" in treffer[0]["begruendung"]
    assert treffer[0]["quickstatements"] == ""     # nichts Einspielbares


def test_konflikt_wird_auch_mit_dem_schalter_nicht_zum_entwurf(items):
    treffer = befunde(items, ["Q113145171"], auch_mit_p31=True)
    assert [b["befund"] for b in treffer] == ["metaklasse-konflikt"]


def test_mineralarten_bleiben_aussen_vor(items):
    """Gediegene Metalle und Amalgame sind als Mineralart modelliert. Ob dort
    zusaetzlich eine Chemie-Metaklasse hingehoert, entscheidet das
    Mineralprojekt."""
    assert befunde(items, [vg.MINERALART_QID], auch_mit_p31=True) == []


def test_nichtlegierung_bekommt_keine_gemisch_metaklasse(items):
    """Ein Item ohne jeden Pfad zur Legierung."""
    assert befunde(items, [], graph=graph_mit()) == []


# ===========================================================================
# Die schiefe Kante Metall -> Legierung
# ===========================================================================

def test_der_weg_ueber_metalle_zaehlt_nicht(items):
    """'Platinmetalle' und 'metals of antiquity' haengen NUR ueber Q11426
    (Metalle) unter der Legierung - sie sind Aufzaehlungen, keine
    Werkstoffe."""
    graph = graph_mit((BRONZE, vg.METALL_QID),
                      (vg.METALL_QID, vg.LEGIERUNG_QID))
    assert befunde(items, [], graph=graph) == []


def test_zweiter_weg_neben_dem_metallweg_zaehlt_sehr_wohl(items):
    """Stahl hat einen Metall-Weg, kommt aber ausserdem ueber Ferrolegierung
    an die Legierung heran und ist selbstverstaendlich eine."""
    graph = graph_mit((BRONZE, vg.METALL_QID),
                      (vg.METALL_QID, vg.LEGIERUNG_QID),
                      (BRONZE, "Q1002713"),
                      ("Q1002713", vg.LEGIERUNG_QID))
    assert [b["befund"] for b in befunde(items, [], graph=graph)] == ["metaklasse"]


def test_metalle_selbst_bekommt_nichts():
    """Q11426 ist der Ausgangspunkt des Modellierungsfehlers und haengt nur
    ueber die defekte Kante unter der Legierung."""
    graph = graph_mit((vg.METALL_QID, vg.LEGIERUNG_QID))
    items = {vg.METALL_QID: {"qid": vg.METALL_QID, "label": "Metall"}}
    assert vg.legierungs_items(graph, list(items), []) == set()


# ===========================================================================
# Die Guideline
# ===========================================================================

def test_die_guideline_kennt_genau_eine_metaklasse_fuer_gemische():
    """Q119896085 ist die Polymer-Untermetaklasse und fuer Legierungen nicht
    gemeint - entworfen wird deshalb nur Q119892838."""
    assert vg.GEMISCH_METAKLASSE == "Q119892838"
    assert "Q119896085" in vg.CHEMIE_METAKLASSEN     # bekannt, aber nie erzeugt


def test_die_pruefung_steht_in_stufe_zwei():
    """Aus dem Graphen abgeleitet, aber mit einer fachlichen Entscheidung
    davor - nicht mechanisch sicher wie Stufe 1."""
    stufe = {nummer: arten for nummer, _, arten, _, _ in vg.STUFEN}
    assert "metaklasse" in stufe[2]
    assert "metaklasse-konflikt" in stufe[2]
