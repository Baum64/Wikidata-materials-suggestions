"""
Wikidata-Klassenhierarchie 'material' (Q214609) analysieren und visualisieren
================================================================================

Wichtiger struktureller Befund vorab (aus den Constraint-Definitionen von
Property:P186 "made from material" abgeleitet):

  Wikidata modelliert "material" (Q214609) NICHT als gemeinsame Oberklasse
  fuer alle Werkstoffe. Stattdessen erlaubt P186 mehrere GLEICHRANGIGE
  Werttypen nebeneinander:
    material (Q214609), alloy (Q37756), chemical compound (Q11173),
    chemical element (Q11344), substance (Q10683158), building material
    (Q206615), food (Q2095), physical object (Q223557) ...

  D.h.: eine Legierung (z. B. Edelstahl) oder eine chemische Verbindung
  (z. B. Siliciumcarbid) muss in der Wikidata-Ontologie NICHT zwingend
  einen P279*-Pfad (subclass of) bis zu Q214609 besitzen, um "korrekt"
  eingeordnet zu sein - sie haengt stattdessen an einer parallelen
  Klassenhierarchie (alloy/chemical compound/...).

  Dieses Skript prueft genau das empirisch fuer eine Liste von Werkstoffen
  und macht sichtbar, welche Werkstoffe tatsaechlich unter Q214609 haengen
  und welche ueber einen parallelen Zweig laufen (was NICHT automatisch ein
  Fehler ist, aber fuer deine Zwecke ueberraschend sein kann).

Ausgabe
-------
  - werkstoff_check.csv          : Tabelle je geprueftem Werkstoff
  - werkstoff_graph.png          : Graph mit den geprueften Werkstoffen und
                                    ihrer tatsaechlichen Anbindung (rot = kein
                                    Pfad zu Q214609, gruen = Pfad vorhanden)
  - trace_<gruppe>_<achse>.png   : Pfade der Gruppen aus TRACE_GROUPS hinauf zu
                                    den Achsen aus TRACE_ROOTS
  - szenario_*.png / .csv        : nur mit --szenario. Drei feste Ausschnitte
                                    (periodensystem, legierungen, minerale) -
                                    siehe Abschnitt 5.
  - subclass_tree_material.png   : nur mit --tree. Der volle Baum umfasst rund
                                    936.000 Klassen; der zeichenbare Ausschnitt
                                    daraus ist willkuerlich und beantwortet die
                                    eigentliche Frage nicht - deshalb Opt-in.

Nutzung
-------
  python "Material class structure/visualisierung.py"
  # oder mit eigener Liste:
  python "Material class structure/visualisierung.py" --materials Stahl Titan Beton Diamant PVC
  # oder eines der drei Szenarien:
  python "Material class structure/visualisierung.py" --szenario periodensystem
  python "Material class structure/visualisierung.py" --szenario legierungen minerale
  python "Material class structure/visualisierung.py" --szenario alle
"""

import argparse
import csv
import os
import sys
import textwrap
from typing import Optional

# Repo-Wurzel (materialswiki) UND dieser Ordner (wikidata_graph) in den Pfad -
# das Skript wird von ueberall gestartet und ueber den Pfad importiert.
_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HIER, os.path.dirname(_HIER)]

import networkx as nx
import matplotlib.pyplot as plt

# Die Wikidata-Zugriffsschicht teilt sich dieses Skript mit
# ClassCheck.py daneben - HTTP-Retry, SPARQL-POST, ASK.
from wikidata_graph import (  # noqa: E402
    WIKIDATA_API, ask, request_with_retry, sparql_json as sparql_query,
)

ROOT_QID = "Q214609"  # material
ROOT_LABEL = "material"

DEFAULT_MATERIALS = [
    "Stahl", "Edelstahl", "Titan", "Aluminium", "Beton", "Glas",
    "Diamant", "Polyethylen", "PVC", "Siliciumcarbid", "Holz", "Kupfer",
    # zweite Gruppe: bewusst so gewaehlt, dass moeglichst viele der
    # parallelen P186-Werttypen abgedeckt sind - Legierungen (Messing,
    # Bronze, Gusseisen), Elemente (Magnesium, Graphit als Modifikation),
    # Verbindungen (Wolframcarbid), Polymere (Polyamid, Epoxidharz,
    # Naturkautschuk) und ein Sammelbegriff (Keramik).
    "Messing", "Bronze", "Gusseisen", "Keramik", "Graphit", "Magnesium",
    "Wolframcarbid", "Polyamid", "Epoxidharz", "Naturkautschuk",
]

# Die trace_*.png-Graphen entstanden urspruenglich aus Hand-Aufrufen von
# --trace/--trace-out; die QID-Listen dazu waren nirgends festgehalten, also
# veralteten die Bilder still, sobald jemand nur den Standardlauf startete.
# Beides steht jetzt hier und wird vom Standardlauf mit erzeugt.
#
# Bewusst QIDs statt Labels: die Labelsuche loest z. B. "Stahl" auf Q1236029
# (Familienname) auf statt auf den Werkstoff Q11427.
TRACE_GROUPS = {
    "werkstoffe": [
        "Q11427",   # Stahl
        "Q172587",  # rostfreier Stahl
        "Q39782",   # Messing
        "Q34095",   # Bronze
        "Q483269",  # Gusseisen
        "Q22657",   # Beton
        "Q11469",   # Glas
        "Q45621",   # Keramik
        "Q412356",  # Siliciumcarbid
        "Q146368",  # Polyvinylchlorid
        "Q287",     # Holz
        "Q5283",    # Diamant
    ],
    "elemente": [
        "Q677",     # Eisen
        "Q753",     # Kupfer
        "Q663",     # Aluminium
        "Q716",     # Titan
        "Q660",     # Magnesium
        "Q623",     # Kohlenstoff
        "Q670",     # Silicium
        "Q744",     # Nickel
        "Q725",     # Chrom
        "Q743",     # Wolfram
    ],
}

# Die beiden konkurrierenden Achsen aus dem Kopf-Docstring: derselbe Werkstoff
# wird einmal gegen die Werkstoff- und einmal gegen die Stoffhierarchie
# geprueft. Erst der Vergleich zeigt, ob ein fehlender Pfad ein Modellierungs-
# loch ist oder nur der andere Zweig.
TRACE_ROOTS = {
    "material": ROOT_QID,  # Q214609
    "chemie": "Q79529",    # chemischer Stoff
}


# ---------------------------------------------------------------------------
# 1) Subclass-Baum unter Q214609 abrufen
# ---------------------------------------------------------------------------

def fetch_subclass_tree(root_qid: str, depth: int = 1, max_nodes: int = 500,
                        batch_size: int = 50) -> list:
    """Liefert (child_qid, child_label, parent_qid, parent_label)-Tupel
    fuer die Subklassen von root_qid bis zur Tiefe `depth`.

    Ein einziges P279*-Query ueber den ganzen Baum laeuft hier zwingend in
    das 60s-Limit des Query-Service (HTTP 502/504): unter Q214609 haengen
    rund 936.000 Klassen. Ein LIMIT liefert davon nur einen willkuerlichen
    Ausschnitt, und zeichenbar ist so ein Baum ohnehin nicht.

    Stattdessen wird ebenenweise (BFS) nur nach DIREKTEN Subklassen gefragt,
    Eltern gebuendelt per VALUES. Jede Einzelabfrage bleibt damit im
    Sekundenbereich. `depth` und `max_nodes` begrenzen den Ausschnitt
    bewusst - ab Tiefe 2 ist der Baum also absichtlich unvollstaendig.

    `max_nodes` wirkt erst nach einem abgeschlossenen Batch, die Grenze wird
    also um bis zu eine Batch-Ausbeute ueberschritten.
    """
    labels = {root_qid: ROOT_LABEL}
    seen = {root_qid}
    frontier = [root_qid]
    edges = []
    truncated = False

    for level in range(1, depth + 1):
        next_frontier = []
        for start in range(0, len(frontier), batch_size):
            batch = frontier[start:start + batch_size]
            values = " ".join(f"wd:{qid}" for qid in batch)
            sparql = f"""
            SELECT ?item ?itemLabel ?parent WHERE {{
              VALUES ?parent {{ {values} }}
              ?item wdt:P279 ?parent .
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
            }}
            """
            for b in sparql_query(sparql).get("results", {}).get("bindings", []):
                child = b["item"]["value"].rsplit("/", 1)[-1]
                parent = b["parent"]["value"].rsplit("/", 1)[-1]
                labels.setdefault(child, b.get("itemLabel", {}).get("value", child))
                edges.append((child, labels[child], parent, labels.get(parent, parent)))
                if child not in seen:
                    seen.add(child)
                    next_frontier.append(child)
            if len(seen) >= max_nodes:
                truncated = True
                break
        print(f"  Ebene {level}: {len(next_frontier)} neue Klassen "
              f"({len(seen)} gesamt)", file=sys.stderr)
        if truncated or not next_frontier:
            break
        frontier = next_frontier

    if truncated:
        print(f"  ABGESCHNITTEN bei max_nodes={max_nodes} - der Baum unter "
              f"{root_qid} ist deutlich groesser.", file=sys.stderr)
    return edges


# ---------------------------------------------------------------------------
# 1b) Aufwaertssuche: wie haengt ein konkretes Item an der Wurzel?
# ---------------------------------------------------------------------------

def fetch_parents(qids: list, prop: str, batch_size: int = 50) -> tuple:
    """Direkte Oberklassen (prop = P279) bzw. Klassen (prop = P31) fuer eine
    QID-Menge, gebuendelt per VALUES. Liefert ({kind: [eltern]}, {qid: label})."""
    parents, labels = {}, {}
    for start in range(0, len(qids), batch_size):
        values = " ".join(f"wd:{qid}" for qid in qids[start:start + batch_size])
        sparql = f"""
        SELECT ?c ?p ?pLabel WHERE {{
          VALUES ?c {{ {values} }}
          ?c wdt:{prop} ?p .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
        }}
        """
        for b in sparql_query(sparql).get("results", {}).get("bindings", []):
            child = b["c"]["value"].rsplit("/", 1)[-1]
            parent = b["p"]["value"].rsplit("/", 1)[-1]
            labels[parent] = b.get("pLabel", {}).get("value", parent)
            parents.setdefault(child, []).append(parent)
    return parents, labels


def fetch_labels(qids: list) -> dict:
    values = " ".join(f"wd:{qid}" for qid in qids)
    sparql = f"""
    SELECT ?c ?cLabel WHERE {{
      VALUES ?c {{ {values} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    return {
        b["c"]["value"].rsplit("/", 1)[-1]: b.get("cLabel", {}).get("value", "?")
        for b in sparql_query(sparql).get("results", {}).get("bindings", [])
    }


def trace_to_root(qid: str, root_qid: str = ROOT_QID, max_depth: int = 8,
                  slack: int = 1, max_paths: int = 20, max_nodes: int = 400) -> tuple:
    """Pfade von qid hinauf zu root_qid, sortiert nach Laenge.

    Der erste Hop folgt P31 UND P279, danach nur noch P279 - genau die
    Semantik, die auch path_via_subclass/path_via_instance_of pruefen. Ein
    blosses ASK sagt nur ob, nicht wie; hier interessiert der Zweig.

    Gesammelt werden nicht nur die kuerzesten Pfade, sondern alle bis zur
    Laenge (kuerzester + `slack`). Grund: Wikidata ist ein DAG, und die
    interessanten Parallelzweige sind oft gerade NICHT die kuerzesten - Stahl
    erreicht Material ueber P31/Legierung in 3 Schritten, ueber die reine
    Subclass-Kette P279/Ferrolegierung aber erst in 4.

    Liefert (pfade, labels); ein Pfad ist eine Liste von (qid, prop)-Paaren,
    wobei prop die Kante zum jeweils VORHERIGEN Element beschreibt.
    """
    labels = {}
    edges_up = {}  # kind -> [(elternteil, prop)]
    dist = {qid: 0}
    frontier = [qid]
    root_depth = None

    for depth in range(max_depth):
        # Ebene 0 deckt den haeufigen Fall ab, dass ein konkreter Werkstoff
        # per P31 an seiner Klasse haengt (Stahl ist INSTANZ von Legierung).
        props = ["P31", "P279"] if depth == 0 else ["P279"]
        next_frontier = []
        for prop in props:
            found, lbl = fetch_parents(frontier, prop)
            labels.update(lbl)
            for child, parents in found.items():
                for parent in parents:
                    edges_up.setdefault(child, []).append((parent, prop))
                    if parent not in dist:
                        dist[parent] = depth + 1
                        next_frontier.append(parent)
        if root_qid in dist and root_depth is None:
            root_depth = dist[root_qid]
        # nach dem Fund noch `slack` Ebenen weiter, sonst bleiben die
        # laengeren Parallelzweige unsichtbar
        if root_depth is not None and depth + 1 >= root_depth + slack:
            break
        if not next_frontier or len(dist) >= max_nodes:
            break
        frontier = next_frontier

    if root_depth is None:
        return [], labels

    limit = root_depth + slack
    paths = []
    seen_paths = set()

    def walk(node, trail):
        if len(paths) >= max_paths or len(trail) > limit:
            return
        if node == root_qid:
            key = tuple(trail)
            if key not in seen_paths:
                seen_paths.add(key)
                paths.append(list(trail))
            return
        for parent, prop in edges_up.get(node, []):
            if any(parent == n for n, _ in trail):  # Zyklen im DAG abfangen
                continue
            walk(parent, trail + [(parent, prop)])

    walk(qid, [])
    paths.sort(key=len)
    labels.update(fetch_labels([qid]))
    return paths, labels


def format_path(path: list, qid: str, labels: dict) -> str:
    parts = [f"{labels.get(qid, qid)} ({qid})"]
    for node, prop in path:
        arrow = "--P31-->" if prop == "P31" else "--P279->"
        parts.append(f"{arrow} {labels.get(node, node)} ({node})")
    return " ".join(parts)


def plot_trace(traces: list, labels: dict, root_qid: str = ROOT_QID,
               path_png: str = "trace_graph.png", title: str = "") -> None:
    """Zeichnet mehrere Traces in EINEN Graphen.

    `traces` ist eine Liste von (start_qid, pfade). Mehrere Startpunkte
    zusammen zu zeichnen ist der eigentliche Zweck: so werden die gemeinsamen
    Knotenpunkte sichtbar, ueber die alles laeuft.
    """
    g = nx.DiGraph()
    starts = {qid for qid, _ in traces}
    for qid, paths in traces:
        g.add_node(qid, label=labels.get(qid, qid))
        for path in paths:
            prev = qid
            for node, prop in path:
                g.add_node(node, label=labels.get(node, node))
                g.add_edge(prev, node, prop=prop)
                prev = node

    # Ebene = Abstand zur Wurzel entgegen der Kantenrichtung. Ohne das landet
    # alles im spring_layout, und bei einer Hierarchie ist das unlesbar -
    # graphviz_layout ("dot") faellt aus, solange pygraphviz/pydot fehlen.
    levels = nx.single_source_shortest_path_length(g.reverse(), root_qid)
    for node in g.nodes:
        g.nodes[node]["layer"] = levels.get(node, max(levels.values(), default=0) + 1)
    per_layer = {}
    for node in g.nodes:
        per_layer.setdefault(g.nodes[node]["layer"], []).append(node)
    widest = max(len(v) for v in per_layer.values())
    # gedeckelt: eine Ebene mit 16 Knoten ergaebe sonst ein 40-Zoll-Bild, auf
    # dem die Beschriftung zu einem Strich zusammenschrumpft
    width = max(11, min(30, 1.9 * widest))
    height = max(7, 2.6 * len(per_layer))

    plt.figure(figsize=(width, height))
    try:
        pos = nx.nx_agraph.graphviz_layout(g, prog="dot")
    except Exception:
        pos = nx.multipartite_layout(g, subset_key="layer", align="horizontal")
        # Wurzel (layer 0) nach oben statt nach unten
        pos = {n: (x, -y) for n, (x, y) in pos.items()}
        # dichte Ebenen zweizeilig versetzen, sonst ueberlappen die Labels
        ys = sorted({pos[n][1] for n in g.nodes})
        gap = min((b - a for a, b in zip(ys, ys[1:])), default=1.0)
        for nodes in per_layer.values():
            if len(nodes) <= 6:
                continue
            for i, node in enumerate(sorted(nodes, key=lambda n: pos[n][0])):
                if i % 2:
                    x, y = pos[node]
                    pos[node] = (x, y - gap * 0.38)

    colors = ["gold" if n == root_qid else "lightgreen" if n in starts else "lightblue"
              for n in g.nodes]
    p31 = [(u, v) for u, v, d in g.edges(data=True) if d["prop"] == "P31"]
    p279 = [(u, v) for u, v, d in g.edges(data=True) if d["prop"] == "P279"]
    nx.draw_networkx_nodes(g, pos, node_color=colors, node_size=2200)
    nx.draw_networkx_labels(g, pos, labels=nx.get_node_attributes(g, "label"),
                            font_size=7)
    nx.draw_networkx_edges(g, pos, edgelist=p31, edge_color="darkorange",
                           style="dashed", arrowsize=13)
    nx.draw_networkx_edges(g, pos, edgelist=p279, edge_color="gray", arrowsize=13)
    plt.title((title or f"Pfade -> {labels.get(root_qid, root_qid)}") +
              "\ngruen = Startpunkt, gold = Wurzel | "
              "orange gestrichelt = P31 (instance of), grau = P279 (subclass of)")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path_png, dpi=150)
    plt.close()
    print(f"Graph geschrieben: {path_png}", file=sys.stderr)


def fetch_direct_subclasses(root_qid: str) -> list:
    """Nur die direkten Subklassen (P279 exakt eine Stufe) - schnell, gut fuer
    einen ersten Ueberblick."""
    sparql = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item wdt:P279 wd:{root_qid} .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    return [
        (b["item"]["value"].rsplit("/", 1)[-1], b.get("itemLabel", {}).get("value", "?"))
        for b in sparql_query(sparql).get("results", {}).get("bindings", [])
    ]


# ---------------------------------------------------------------------------
# 2) Einzelne Werkstoffe aufloesen und pruefen
# ---------------------------------------------------------------------------

def resolve_qid(label: str, lang: str = "de") -> Optional[dict]:
    resp = request_with_retry(
        "GET", WIKIDATA_API,
        params={
            "action": "wbsearchentities", "search": label, "language": lang,
            "format": "json", "limit": 1, "type": "item",
        },
    )
    hits = resp.json().get("search", [])
    if not hits:
        return None
    return {"qid": hits[0]["id"], "label": hits[0].get("label", label)}


# hint:Prior bezieht sich auf das UNMITTELBAR davor stehende Triple, muss also
# HINTER das P279*-Pfadtriple. "forward" zwingt Blazegraph, vom gebundenen Item
# nach oben zu laufen, statt die ~936.000 Klassen unter der Wurzel aufzuzaehlen.
# Gemessen an Q11427 (Edelstahl): ohne Hint 42s, mit Hint 1,5s.
GEARING_HINT = 'hint:Prior hint:gearing "forward" .'


def path_via_subclass(qid: str, root_qid: str = ROOT_QID) -> bool:
    """Ist item selbst (transitiv) eine Subklasse von root?"""
    return ask(f'ASK {{ wd:{qid} wdt:P279* wd:{root_qid} . {GEARING_HINT} }}')


def path_via_instance_of(qid: str, root_qid: str = ROOT_QID) -> bool:
    """Ist item eine Instanz einer (transitiven) Subklasse von root?
    (deckt den haeufigen Fall ab, dass ein konkreter Werkstoff per P31 an
    einer Klasse haengt, die selbst unter Q214609 liegt.)

    Der Pfad ist bewusst in zwei Triples aufgeteilt: an ein
    P31/P279*-Pfadtriple laesst sich der Gearing-Hint nicht haengen, und
    ohne ihn laeuft die Abfrage in den Timeout.
    """
    return ask(
        f'ASK {{ wd:{qid} wdt:P31 ?c . ?c wdt:P279* wd:{root_qid} . {GEARING_HINT} }}'
    )


def get_direct_classes(qid: str) -> dict:
    """Direkte P31- und P279-Werte mit Labels."""
    sparql = f"""
    SELECT ?p31 ?p31Label ?p279 ?p279Label WHERE {{
      OPTIONAL {{ wd:{qid} wdt:P31 ?p31 . }}
      OPTIONAL {{ wd:{qid} wdt:P279 ?p279 . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    p31, p279 = set(), set()
    for b in sparql_query(sparql).get("results", {}).get("bindings", []):
        if "p31" in b:
            p31.add(b.get("p31Label", {}).get("value", b["p31"]["value"]))
        if "p279" in b:
            p279.add(b.get("p279Label", {}).get("value", b["p279"]["value"]))
    return {"instance_of": sorted(p31), "subclass_of": sorted(p279)}


def check_materials(labels: list) -> list:
    rows = []
    for label in labels:
        # gedrosselt wird zentral in request_with_retry
        resolved = resolve_qid(label)
        if not resolved:
            rows.append({"input": label, "status": "NICHT_GEFUNDEN"})
            continue
        qid = resolved["qid"]

        via_subclass = path_via_subclass(qid)
        via_instance = path_via_instance_of(qid)
        classes = get_direct_classes(qid)

        reachable = via_subclass or via_instance
        rows.append({
            "input": label,
            "qid": qid,
            "label": resolved["label"],
            "status": "OK (Pfad zu material vorhanden)" if reachable else "AUFFAELLIG (kein Pfad zu material)",
            "via_subclass_of": via_subclass,
            "via_instance_of": via_instance,
            "direct_instance_of": "; ".join(classes["instance_of"]) or "-",
            "direct_subclass_of": "; ".join(classes["subclass_of"]) or "-",
        })
    return rows


# ---------------------------------------------------------------------------
# 3) Ausgabe: CSV + Graphen
# ---------------------------------------------------------------------------

def write_report_csv(rows: list, path: str = "werkstoff_check.csv") -> None:
    fieldnames = ["input", "qid", "label", "status", "via_subclass_of",
                  "via_instance_of", "direct_instance_of", "direct_subclass_of"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Bericht geschrieben: {path}", file=sys.stderr)


def plot_subclass_tree(edges: list, path: str = "subclass_tree_material.png") -> None:
    g = nx.DiGraph()
    g.add_node(ROOT_QID, label=ROOT_LABEL)
    for child, child_label, parent, parent_label in edges:
        g.add_node(child, label=child_label)
        g.add_node(parent, label=parent_label)
        g.add_edge(parent, child)

    plt.figure(figsize=(14, 10))
    try:
        pos = nx.nx_agraph.graphviz_layout(g, prog="dot")
    except Exception:
        pos = nx.spring_layout(g, k=0.6, seed=42)

    labels = nx.get_node_attributes(g, "label")
    colors = ["gold" if n == ROOT_QID else "lightblue" for n in g.nodes]
    nx.draw(g, pos, labels=labels, with_labels=True, node_color=colors,
            node_size=800, font_size=6, arrowsize=8, edge_color="gray")
    plt.title(f"Subclass-Hierarchie unter '{ROOT_LABEL}' ({ROOT_QID})")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Graph geschrieben: {path}", file=sys.stderr)


def plot_material_check(rows: list, path: str = "werkstoff_graph.png") -> None:
    g = nx.DiGraph()
    g.add_node(ROOT_QID, label=ROOT_LABEL, color="gold")

    for row in rows:
        if row.get("status") == "NICHT_GEFUNDEN":
            continue
        node_id = row["qid"]
        reachable = row["via_subclass_of"] or row["via_instance_of"]
        g.add_node(node_id, label=row["label"], color="lightgreen" if reachable else "salmon")
        # direkte Verbindung zur Wurzel nur zur Illustration einzeichnen,
        # wenn tatsaechlich ein Pfad existiert
        if reachable:
            g.add_edge(ROOT_QID, node_id, style="reachable")
        else:
            # gestrichelte "fehlende" Verbindung visuell andeuten
            g.add_edge(ROOT_QID, node_id, style="missing")

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(g, k=0.8, seed=42)
    colors = [g.nodes[n].get("color", "lightblue") for n in g.nodes]
    solid_edges = [(u, v) for u, v, d in g.edges(data=True) if d.get("style") == "reachable"]
    missing_edges = [(u, v) for u, v, d in g.edges(data=True) if d.get("style") == "missing"]

    labels = nx.get_node_attributes(g, "label")
    nx.draw_networkx_nodes(g, pos, node_color=colors, node_size=1200)
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=7)
    nx.draw_networkx_edges(g, pos, edgelist=solid_edges, edge_color="green")
    nx.draw_networkx_edges(g, pos, edgelist=missing_edges, edge_color="red", style="dashed")
    plt.title("Grün = Pfad zu 'material' (Q214609) vorhanden | Rot = kein Pfad (paralleler Zweig)")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Graph geschrieben: {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 4) Trace-Laeufe
# ---------------------------------------------------------------------------

def run_trace(qids: list, root: str, out_png: str, title: str = "") -> int:
    """Verfolgt alle `qids` hinauf zu `root` und zeichnet sie in EINEN Graphen.

    Rueckgabe: Anzahl der Startpunkte OHNE Pfad - genau die interessanten
    Faelle, in denen ein Werkstoff nur am parallelen Zweig haengt.
    """
    root_label = fetch_labels([root]).get(root, root)
    traces, all_labels, ohne_pfad = [], {}, 0

    for qid in qids:
        paths, labels = trace_to_root(qid, root_qid=root)
        all_labels.update(labels)
        name = f"{labels.get(qid, qid)} ({qid})"
        if not paths:
            ohne_pfad += 1
            print(f"  KEIN Pfad: {name} -> {root_label} ({root}) "
                  f"- paralleler Zweig.", file=sys.stderr)
            continue
        print(f"\n{name}: {len(paths)} Pfad(e), "
              f"Laenge {len(paths[0])}-{len(paths[-1])}")
        for path in paths:
            print("  " + format_path(path, qid, labels))
        traces.append((qid, paths))

    print()
    if traces:
        all_labels[root] = root_label
        plot_trace(traces, all_labels, root_qid=root, path_png=out_png,
                   title=title or f"Pfade zu {root_label} ({root})")
    else:
        print(f"Kein einziger Pfad gefunden - {out_png} nicht geschrieben.",
              file=sys.stderr)
    return ohne_pfad


def run_default_traces(out_dir: str = ".") -> None:
    """Erzeugt die trace_<gruppe>_<achse>.png-Matrix aus TRACE_GROUPS x
    TRACE_ROOTS - dieselben vier Dateien, die frueher von Hand entstanden."""
    for gruppe, qids in TRACE_GROUPS.items():
        for achse, root in TRACE_ROOTS.items():
            out_png = os.path.join(out_dir, f"trace_{gruppe}_{achse}.png")
            root_label = fetch_labels([root]).get(root, root)
            print(f"\n=== {gruppe} -> {root_label} ({root}) ===",
                  file=sys.stderr)
            ohne = run_trace(qids, root, out_png,
                             title=f"{gruppe.capitalize()}: Pfade zu "
                                   f"{root_label} ({root})")
            print(f"  {len(qids) - ohne}/{len(qids)} mit Pfad, "
                  f"{ohne} ohne.", file=sys.stderr)


# ---------------------------------------------------------------------------
# 5) Szenarien: Periodensystem, Legierungen, Minerale
# ---------------------------------------------------------------------------
#
# Drei feste Ausschnitte der Klassenhierarchie, je einer pro --szenario. Sie
# beantworten dieselbe Frage wie die Trace-Graphen ("wie haengt das an der
# Wurzel?"), nur fuer Gruppen, bei denen die Antwort nicht am Pfad, sondern an
# der Klassenvergabe selbst haengt:
#
#   periodensystem  alle 118 Elemente im PSE-Raster, eingefaerbt nach ihrer
#                   P279-Klasse. Sichtbar wird, dass die Klassen ungleich
#                   vergeben sind (17 Elemente als Uebergangsmetall, aber nur
#                   6 ueberhaupt als "Metall") und viele Zellen leer bleiben.
#   legierungen     10 Legierungsklassen mit ihren direkten Subklassen -
#                   also der Blick nach UNTEN statt nach oben.
#   minerale        10 Mineralarten mit ihren Pfaden hinauf zu Mineral
#                   (Q7946); Minerale haengen ueber P31 "Mineralart" und
#                   P279 "Silicate"/"Carbonate"/... dort, nicht ueber Q214609.

ELEMENT_QID = "Q11344"   # chemisches Element
ALLOY_ROOT = "Q37756"    # Legierung
MINERAL_ROOT = "Q7946"   # Mineral

# Bewusst QIDs: die Labelsuche liefert fuer "Diamant" ein Schiff und fuer
# "Gips" einen Familiennamen (beides wbsearchentities-Treffer vor dem Mineral).
SZENARIO_LEGIERUNGEN = [
    "Q11427",    # Stahl
    "Q172587",   # rostfreier Stahl
    "Q34095",    # Bronze
    "Q39782",    # Messing
    "Q483269",   # Gusseisen
    "Q518350",   # Kupferlegierung
    "Q447725",   # Aluminiumlegierung
    "Q1985623",  # Nickelbasislegierung
    "Q3300719",  # Titanlegierung
    "Q637345",   # Superlegierung
]

SZENARIO_MINERALE = [
    "Q43010",    # Quarz
    "Q171917",   # Calcit
    "Q50769",    # Pyrit
    "Q103223",   # Haematit
    "Q181395",   # Magnetit
    "Q5314",     # Halit
    "Q82658",    # Gips
    "Q131777",   # Korund
    "Q102151",   # Fluorit
    "Q5283",     # Diamant
]

# Reihenfolge = Vorrang bei der Einfaerbung: ein Element traegt oft mehrere
# dieser Klassen (Platin ist Platinmetall UND Uebergangsmetall), gezeichnet
# wird die spezifischere. Alles andere landet in "andere Klasse".
PSE_KATEGORIEN = [
    ("Q19609", "#ffe08a"),     # Edelgas
    ("Q19557", "#ff9e7a"),     # Alkalimetalle
    ("Q19563", "#ffc08a"),     # 2. Hauptgruppe (Erdalkalimetalle)
    ("Q19605", "#d7f28a"),     # 17. Hauptgruppe (Halogene)
    ("Q104567", "#c7e6a0"),    # 16. Hauptgruppe
    ("Q223995", "#b7d4f0"),    # Platinmetalle
    ("Q19588", "#9fc7e8"),     # Uebergangsmetalle
    ("Q19577", "#d9b8e8"),     # Actinoide
    ("Q428778", "#c3a0d8"),    # Transactinoide
    ("Q19596", "#a8ddd6"),     # Halbmetalle
    ("Q19753344", "#c8f0c0"),  # zweiatomiges Nichtmetall
    ("Q19753345", "#a8e6a0"),  # vielatomige Nichtmetalle
    ("Q19600", "#8fd98a"),     # Nichtmetalle
    ("Q19591", "#cfcfe8"),     # Metall des p-Blocks
    ("Q11426", "#bdbdd8"),     # Metalle
]

FARBE_ANDERE = "#e6e6e6"
FARBE_KEINE = "#ffffff"


def fetch_elemente(max_z: int = 118) -> list:
    """Alle chemischen Elemente mit Ordnungszahl, Symbol und ihren
    P279-Klassen.

    Zwei Abfragen statt einer: das Label-Service laesst sich mit GROUP_CONCAT
    ueber optionale Klassen nicht zuverlaessig kombinieren, und getrennt
    bleibt jede Abfrage im Sekundenbereich.
    """
    basis = f"""
    SELECT ?e ?eLabel ?num ?sym WHERE {{
      ?e wdt:P31 wd:{ELEMENT_QID} ; wdt:P1086 ?num .
      FILTER(xsd:integer(?num) <= {max_z})
      OPTIONAL {{ ?e wdt:P246 ?sym }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    nach_z = {}
    for b in sparql_query(basis).get("results", {}).get("bindings", []):
        qid = b["e"]["value"].rsplit("/", 1)[-1]
        z = int(b["num"]["value"])
        el = {
            "qid": qid, "z": z,
            "label": b.get("eLabel", {}).get("value", qid),
            "symbol": b.get("sym", {}).get("value", ""),
            "klassen": {},
        }
        # Mehrere Items koennen dieselbe Ordnungszahl tragen (Isotopen- und
        # Duplikat-Items). Das kanonische Element hat die kleinste QID.
        alt = nach_z.get(z)
        if alt is None or int(qid[1:]) < int(alt["qid"][1:]):
            if alt is not None:
                print(f"  Ordnungszahl {z}: {alt['qid']} verworfen zugunsten "
                      f"von {qid}", file=sys.stderr)
            nach_z[z] = el

    klassen = f"""
    SELECT ?e ?c ?cLabel WHERE {{
      ?e wdt:P31 wd:{ELEMENT_QID} ; wdt:P1086 ?num ; wdt:P279 ?c .
      FILTER(xsd:integer(?num) <= {max_z})
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    nach_qid = {el["qid"]: el for el in nach_z.values()}
    for b in sparql_query(klassen).get("results", {}).get("bindings", []):
        el = nach_qid.get(b["e"]["value"].rsplit("/", 1)[-1])
        if el is None:
            continue
        cqid = b["c"]["value"].rsplit("/", 1)[-1]
        el["klassen"][cqid] = b.get("cLabel", {}).get("value", cqid)

    return [nach_z[z] for z in sorted(nach_z)]


def pse_position(z: int) -> Optional[tuple]:
    """Ordnungszahl -> (Zeile, Spalte) im 18-spaltigen Raster.

    Lanthanoide und Actinoide bekommen die abgesetzten Zeilen 8 und 9 -
    dieselbe Konvention wie im gedruckten Periodensystem.
    """
    if z == 1:
        return (1, 1)
    if z == 2:
        return (1, 18)
    if z in (3, 4):
        return (2, z - 2)
    if 5 <= z <= 10:
        return (2, z + 8)
    if z in (11, 12):
        return (3, z - 10)
    if 13 <= z <= 18:
        return (3, z)
    if 19 <= z <= 36:
        return (4, z - 18)
    if 37 <= z <= 54:
        return (5, z - 36)
    if z in (55, 56):
        return (6, z - 54)
    if 57 <= z <= 71:
        return (8, z - 54)
    if 72 <= z <= 86:
        return (6, z - 68)
    if z in (87, 88):
        return (7, z - 86)
    if 89 <= z <= 103:
        return (9, z - 86)
    if 104 <= z <= 118:
        return (7, z - 100)
    return None


def plot_periodensystem(elemente: list, path_png: str) -> None:
    """PSE-Raster, jede Zelle eingefaerbt nach ihrer spezifischsten Klasse.

    Weiss-schraffiert = das Element hat ueberhaupt keine P279-Klasse; genau
    diese Zellen sind die Luecke, um die es hier geht.
    """
    from matplotlib.patches import Patch

    farben = dict(PSE_KATEGORIEN)
    vorrang = [qid for qid, _ in PSE_KATEGORIEN]
    alle_klassen = {}
    genutzt = {}
    ohne_klasse = []

    fig, ax = plt.subplots(figsize=(21, 13))
    for el in elemente:
        pos = pse_position(el["z"])
        if pos is None:
            continue
        zeile, spalte = pos
        y = -(zeile + (0.7 if zeile >= 8 else 0.0))
        for cqid, clabel in el["klassen"].items():
            alle_klassen[cqid] = (clabel, alle_klassen.get(cqid, (clabel, 0))[1] + 1)

        kategorie = next((q for q in vorrang if q in el["klassen"]), None)
        if kategorie:
            farbe = farben[kategorie]
            genutzt[kategorie] = el["klassen"][kategorie]
        elif el["klassen"]:
            farbe = FARBE_ANDERE
        else:
            farbe = FARBE_KEINE
            ohne_klasse.append(el)

        ax.add_patch(plt.Rectangle(
            (spalte, y), 0.94, 0.94, facecolor=farbe, edgecolor="0.3",
            linewidth=0.9, hatch="///" if not el["klassen"] else None))
        ax.text(spalte + 0.07, y + 0.76, str(el["z"]), fontsize=6.5, color="0.35")
        ax.text(spalte + 0.47, y + 0.50, el["symbol"] or "?", fontsize=14,
                fontweight="bold", ha="center", va="center")
        ax.text(spalte + 0.47, y + 0.24, el["label"][:14], fontsize=5.5,
                ha="center", va="center", color="0.2")
        ax.text(spalte + 0.47, y + 0.08,
                f"{len(el['klassen'])} Klassen" if el["klassen"] else "keine Klasse",
                fontsize=5, ha="center", va="center", color="0.35")

    # Kopfband ueber dem Raster freihalten: die Legende hat 17 Eintraege und
    # laege sonst ueber Wasserstoff und den Alkalimetallen.
    ax.set_xlim(0.5, 19.6)
    ax.set_ylim(-10.1, 2.1)
    ax.set_aspect("equal")
    ax.axis("off")

    handles = [Patch(facecolor=farben[q], edgecolor="0.3", label=genutzt[q])
               for q in vorrang if q in genutzt]
    handles.append(Patch(facecolor=FARBE_ANDERE, edgecolor="0.3",
                         label="nur andere Klassen"))
    handles.append(Patch(facecolor=FARBE_KEINE, edgecolor="0.3", hatch="///",
                         label=f"keine P279-Klasse ({len(ohne_klasse)})"))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 2.0),
              bbox_transform=ax.transData, ncol=5, fontsize=8, frameon=False)

    rang = sorted(alle_klassen.values(), key=lambda t: (-t[1], t[0]))
    fusszeile = textwrap.fill(
        "alle vergebenen P279-Klassen: " +
        " · ".join(f"{n}× {label}" for label, n in rang), 210)
    ax.set_title(
        f"Periodensystem: Klassenzuordnung (P279) in Wikidata\n"
        f"{len(elemente)} Elemente, {len(alle_klassen)} verschiedene Klassen, "
        f"{len(ohne_klasse)} Elemente ganz ohne Klasse", fontsize=13)
    fig.text(0.5, 0.045, fusszeile, ha="center", fontsize=6.5, color="0.25")
    fig.savefig(path_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Graph geschrieben: {path_png}", file=sys.stderr)


def write_elemente_csv(elemente: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ordnungszahl", "symbol", "label", "qid",
                         "anzahl_klassen", "klassen"])
        for el in elemente:
            writer.writerow([
                el["z"], el["symbol"], el["label"], el["qid"],
                len(el["klassen"]),
                "; ".join(f"{lbl} ({q})" for q, lbl in sorted(
                    el["klassen"].items(), key=lambda kv: kv[1])),
            ])
    print(f"Bericht geschrieben: {path}", file=sys.stderr)


def fetch_subclasses(qids: list, limit: int) -> tuple:
    """Direkte Subklassen (P279 genau eine Stufe) je QID.

    Liefert ({qid: [(kind_qid, kind_label)]}, {qid: gesamtzahl}) - die Liste
    ist auf `limit` gekuerzt, die Gesamtzahl bleibt erhalten, damit die
    Kuerzung im Bild benannt werden kann.
    """
    values = " ".join(f"wd:{q}" for q in qids)
    sparql = f"""
    SELECT ?p ?s ?sLabel WHERE {{
      VALUES ?p {{ {values} }}
      ?s wdt:P279 ?p .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }}
    """
    kinder = {}
    for b in sparql_query(sparql).get("results", {}).get("bindings", []):
        parent = b["p"]["value"].rsplit("/", 1)[-1]
        child = b["s"]["value"].rsplit("/", 1)[-1]
        kinder.setdefault(parent, {})[child] = b.get("sLabel", {}).get("value", child)
    gesamt = {q: len(kinder.get(q, {})) for q in qids}
    gekuerzt = {
        q: sorted(kinder.get(q, {}).items(), key=lambda kv: kv[1])[:limit]
        for q in qids
    }
    return gekuerzt, gesamt


def plot_subklassen_faecher(root: str, eltern: list, kinder: dict, gesamt: dict,
                            labels: dict, path_png: str, title: str) -> None:
    """Wurzel -> 10 Beispiele -> deren Subklassen, je Beispiel eine Spalte.

    Kein spring_layout: die Positionen stehen fest (Spalte je Beispiel), sonst
    schieben sich die langen Legierungsnamen uebereinander.
    """
    g = nx.DiGraph()
    pos, tiefste = {}, 0
    g.add_node(root)
    pos[root] = ((len(eltern) - 1) / 2.0, 1.35)
    for i, parent in enumerate(eltern):
        g.add_node(parent)
        pos[parent] = (float(i), 0.0)
        g.add_edge(root, parent)
        for j, (child, _) in enumerate(kinder.get(parent, [])):
            g.add_node(child)
            # Eine Subklasse kann unter mehreren Beispielen haengen (Alumel
            # unter Aluminium- UND Nickelbasislegierung). Sie behaelt ihre
            # erste Spalte, die zweite Kante laeuft dann quer - genau das
            # soll sichtbar bleiben.
            pos.setdefault(child, (float(i), -0.55 - j * 0.5))
            g.add_edge(parent, child)
            tiefste = max(tiefste, j + 1)

    def beschriftung(qid: str) -> str:
        # break_long_words=False: sonst zerfaellt "Aluminiumlegierung" mitten
        # im Wort; ein zu breiter Kasten ist das kleinere Uebel.
        return textwrap.fill(labels.get(qid, qid), 17, break_long_words=False)

    fig = plt.figure(figsize=(max(14, 2.1 * len(eltern)), 4.5 + 0.62 * tiefste))
    nx.draw_networkx_edges(g, pos, edge_color="0.6", arrows=False, width=0.8)
    stil = dict(font_size=7, bbox=dict(boxstyle="round,pad=0.35", linewidth=0.7))
    nx.draw_networkx_labels(g, pos, labels={root: beschriftung(root)},
                            font_weight="bold",
                            **{**stil, "bbox": dict(stil["bbox"], facecolor="gold",
                                                    edgecolor="0.3")})
    nx.draw_networkx_labels(
        g, pos,
        labels={p: f"{beschriftung(p)}\n({gesamt.get(p, 0)} Subklassen)"
                for p in eltern},
        **{**stil, "bbox": dict(stil["bbox"], facecolor="lightgreen",
                                edgecolor="0.3")})
    kinder_labels = {c: beschriftung(c) for p in eltern
                     for c, _ in kinder.get(p, [])}
    if kinder_labels:
        nx.draw_networkx_labels(
            g, pos, labels=kinder_labels, font_size=6,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue",
                      edgecolor="0.55", linewidth=0.6))
    plt.title(f"{title}\ngold = Wurzel, gruen = Beispiel, blau = direkte "
              f"Subklasse (P279); je Beispiel hoechstens die ersten "
              f"{max((len(v) for v in kinder.values()), default=0)} "
              f"alphabetisch, Querkanten = Subklasse mehrerer Beispiele",
              fontsize=11)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path_png, dpi=150)
    plt.close()
    print(f"Graph geschrieben: {path_png}", file=sys.stderr)


def szenario_periodensystem(out_dir: str) -> None:
    print("Lade alle chemischen Elemente mit ihren Klassen ...", file=sys.stderr)
    elemente = fetch_elemente()
    print(f"  {len(elemente)} Elemente geladen.", file=sys.stderr)
    write_elemente_csv(elemente, os.path.join(out_dir, "szenario_periodensystem.csv"))
    plot_periodensystem(elemente, os.path.join(out_dir, "szenario_periodensystem.png"))
    ohne = [el for el in elemente if not el["klassen"]]
    if ohne:
        print("  ohne jede P279-Klasse: " +
              ", ".join(f"{el['symbol'] or el['label']}" for el in ohne),
              file=sys.stderr)


def szenario_legierungen(out_dir: str, limit: int) -> None:
    print("Lade Subklassen der Legierungs-Beispiele ...", file=sys.stderr)
    kinder, gesamt = fetch_subclasses(SZENARIO_LEGIERUNGEN, limit)
    labels = fetch_labels(SZENARIO_LEGIERUNGEN + [ALLOY_ROOT])
    labels.update({c: l for p in SZENARIO_LEGIERUNGEN
                   for c, l in kinder.get(p, [])})
    for qid in SZENARIO_LEGIERUNGEN:
        gezeigt = kinder.get(qid, [])
        print(f"  {labels.get(qid, qid)} ({qid}): {gesamt.get(qid, 0)} Subklassen"
              + (f", gezeigt {len(gezeigt)}" if len(gezeigt) < gesamt.get(qid, 0)
                 else ""))
        for child, clabel in gezeigt:
            print(f"      {clabel} ({child})")
    plot_subklassen_faecher(
        ALLOY_ROOT, SZENARIO_LEGIERUNGEN, kinder, gesamt, labels,
        os.path.join(out_dir, "szenario_legierungen.png"),
        f"Legierungen: 10 Beispiele und ihre Subklassen unter "
        f"{labels.get(ALLOY_ROOT, ALLOY_ROOT)} ({ALLOY_ROOT})")


def szenario_minerale(out_dir: str) -> None:
    root_label = fetch_labels([MINERAL_ROOT]).get(MINERAL_ROOT, MINERAL_ROOT)
    print(f"Verfolge 10 Mineralarten hinauf zu {root_label} ({MINERAL_ROOT}) ...",
          file=sys.stderr)
    ohne = run_trace(SZENARIO_MINERALE, MINERAL_ROOT,
                     os.path.join(out_dir, "szenario_minerale.png"),
                     title=f"Minerale: 10 Beispiele und ihre Pfade zu "
                           f"{root_label} ({MINERAL_ROOT})")
    print(f"  {len(SZENARIO_MINERALE) - ohne}/{len(SZENARIO_MINERALE)} mit Pfad, "
          f"{ohne} ohne.", file=sys.stderr)


SZENARIEN = {
    "periodensystem": lambda out_dir, limit: szenario_periodensystem(out_dir),
    "legierungen": lambda out_dir, limit: szenario_legierungen(out_dir, limit),
    "minerale": lambda out_dir, limit: szenario_minerale(out_dir),
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", nargs="+", default=DEFAULT_MATERIALS)
    parser.add_argument("--tree", action="store_true",
                         help="zusaetzlich subclass_tree_material.png zeichnen. "
                              "Standardmaessig AUS: der Ausschnitt, der sich aus "
                              "~936.000 Klassen zeichnen laesst, ist willkuerlich "
                              "und traegt nichts zur Frage bei, wie ein einzelner "
                              "Werkstoff an der Wurzel haengt - dafuer sind die "
                              "Trace-Graphen da")
    parser.add_argument("--skip-traces", action="store_true",
                         help="die trace_<gruppe>_<achse>.png-Matrix aus "
                              "TRACE_GROUPS x TRACE_ROOTS ueberspringen")
    parser.add_argument("--depth", type=int, default=1,
                         help="nur mit --tree: Tiefe des Subclass-Baums (Default 1: 413 direkte "
                              "Subklassen, vollstaendig. Der volle Baum hat "
                              "~936.000 Klassen und ist weder in einer Abfrage "
                              "holbar noch zeichenbar - ab Tiefe 2 liefert "
                              "--max-nodes zwangslaeufig einen Ausschnitt)")
    parser.add_argument("--max-nodes", type=int, default=500,
                         help="nur mit --tree: Obergrenze fuer Knoten im "
                              "Subclass-Baum (Default 500)")
    parser.add_argument("--trace", metavar="QID", nargs="+",
                         help="statt des Standardlaufs: die Pfade von einer oder "
                              "mehreren QIDs hinauf zur Wurzel zeigen, alle in "
                              "einem Graphen (z. B. --trace Q11427 Q39782)")
    parser.add_argument("--trace-root", metavar="QID", default=ROOT_QID,
                         help=f"Zielwurzel fuer --trace (Default {ROOT_QID} "
                              f"material; z. B. Q79529 fuer die chemische Achse)")
    parser.add_argument("--trace-out", metavar="PNG", default="trace_graph.png",
                         help="Ausgabedatei fuer den Trace-Graphen")
    parser.add_argument("--szenario", nargs="+", metavar="NAME",
                         choices=sorted(SZENARIEN) + ["alle"],
                         help="statt des Standardlaufs eines oder mehrere "
                              "Szenarien zeichnen: periodensystem (alle 118 "
                              "Elemente nach P279-Klasse eingefaerbt), "
                              "legierungen (10 Beispiele mit ihren "
                              "Subklassen), minerale (10 Beispiele mit ihren "
                              "Pfaden zu Mineral Q7946) oder alle")
    parser.add_argument("--szenario-out", metavar="DIR",
                         help="Zielverzeichnis fuer die Szenario-Dateien "
                              "(Default: das Verzeichnis dieses Skripts)")
    parser.add_argument("--max-subklassen", type=int, default=8, metavar="N",
                         help="nur mit --szenario legierungen: hoechstens N "
                              "Subklassen je Beispiel zeichnen (Default 8; "
                              "Kupferlegierung allein hat 44)")
    args = parser.parse_args()

    # QID direkt angeben umgeht die Labelsuche - wbsearchentities loest z. B.
    # "Stahl" auf Q1236029 (Familienname) statt auf den Werkstoff Q11427 auf.
    if args.szenario:
        out_dir = args.szenario_out or os.path.dirname(os.path.abspath(__file__))
        os.makedirs(out_dir, exist_ok=True)
        namen = sorted(SZENARIEN) if "alle" in args.szenario else args.szenario
        for name in dict.fromkeys(namen):
            print(f"\n=== Szenario: {name} ===", file=sys.stderr)
            SZENARIEN[name](out_dir, args.max_subklassen)
        return

    if args.trace:
        run_trace(args.trace, args.trace_root, args.trace_out)
        return

    if args.tree:
        print("Lade Subclass-Baum unter Q214609 ...", file=sys.stderr)
        edges = fetch_subclass_tree(ROOT_QID, depth=args.depth,
                                    max_nodes=args.max_nodes)
        print(f"{len(edges)} Kanten gefunden.", file=sys.stderr)
        plot_subclass_tree(edges)

    print("Pruefe einzelne Werkstoffe ...", file=sys.stderr)
    rows = check_materials(args.materials)
    write_report_csv(rows)
    plot_material_check(rows)

    print("\n--- Kurzuebersicht ---", file=sys.stderr)
    for row in rows:
        print(f"  {row['input']:20s} -> {row.get('status')}", file=sys.stderr)

    # frueher nur von Hand aufgerufen - dadurch veralteten die Bilder still
    if not args.skip_traces:
        print("\nZeichne Trace-Graphen ...", file=sys.stderr)
        run_default_traces(os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    main()
