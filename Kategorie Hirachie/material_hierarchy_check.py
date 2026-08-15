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
  - subclass_tree_material.png   : Graph der Subclass-Hierarchie unter Q214609,
                                    begrenzt auf --depth Ebenen und --max-nodes
                                    Knoten (der volle Baum umfasst rund 936.000
                                    Klassen - nicht in einer Abfrage holbar und
                                    als Bild ohnehin nicht lesbar)
  - werkstoff_check.csv          : Tabelle je geprueftem Werkstoff
  - werkstoff_graph.png          : Graph mit den geprueften Werkstoffen und
                                    ihrer tatsaechlichen Anbindung (rot = kein
                                    Pfad zu Q214609, gruen = Pfad vorhanden)

Nutzung
-------
  python material_hierarchy_check.py
  # oder mit eigener Liste:
  python material_hierarchy_check.py --materials Stahl Titan Beton Diamant PVC
"""

import argparse
import csv
import os
import sys
import time
from typing import Optional

# konfig.py liegt im Repo-Wurzelverzeichnis.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import konfig  # noqa: E402

import networkx as nx
import matplotlib.pyplot as plt
import requests

# Kontaktadresse aus .env im Repo-Wurzelverzeichnis - siehe .env.beispiel.
USER_AGENT = ("MaterialsWikidataAnalysisBot/0.1 "
              f'(mailto:{konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")})')
HEADERS = {"User-Agent": USER_AGENT}
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

ROOT_QID = "Q214609"  # material
ROOT_LABEL = "material"

DEFAULT_MATERIALS = [
    "Stahl", "Edelstahl", "Titan", "Aluminium", "Beton", "Glas",
    "Diamant", "Polyethylen", "PVC", "Siliciumcarbid", "Holz", "Kupfer",
]


# ---------------------------------------------------------------------------
# 0) HTTP mit Drosselung und Backoff
# ---------------------------------------------------------------------------

REQUEST_DELAY_SEC = 1.0
_LAST_REQUEST = 0.0


def request_with_retry(method: str, url: str, attempts: int = 5, timeout: int = 60,
                       **kwargs):
    """Einziger HTTP-Einstiegspunkt: drosselt und wiederholt bei 429/5xx.

    Der Query-Service liefert auch bei kleinen Abfragen sporadisch 502; ohne
    Retry reisst ein einzelner Ausfall den kompletten Lauf ab. Ein 504 nach
    ~60s ist dagegen kein transienter Fehler, sondern das Query-Timeout - da
    hilft nur eine kleinere Abfrage (siehe fetch_subclass_tree).
    """
    global _LAST_REQUEST
    delay = 3.0
    for attempt in range(1, attempts + 1):
        wait = REQUEST_DELAY_SEC - (time.monotonic() - _LAST_REQUEST)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST = time.monotonic()
        try:
            resp = requests.request(method, url, headers=HEADERS, timeout=timeout,
                                    **kwargs)
        except requests.RequestException as exc:
            if attempt == attempts:
                raise
            print(f"  {type(exc).__name__} - Versuch {attempt}/{attempts}",
                  file=sys.stderr)
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp
            if attempt == attempts:
                resp.raise_for_status()
            print(f"  HTTP {resp.status_code} - Versuch {attempt}/{attempts}, "
                  f"warte {delay:.0f}s", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"nicht erreichbar: {url}")


def sparql_query(query: str) -> dict:
    """SPARQL per POST - GET reisst bei laengeren VALUES-Bloecken die URL-Laenge."""
    resp = request_with_retry(
        "POST", WIKIDATA_SPARQL,
        data={"query": query, "format": "json"},
    )
    return resp.json()


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


def ask(query: str) -> bool:
    return sparql_query(query).get("boolean", False)


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
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", nargs="+", default=DEFAULT_MATERIALS)
    parser.add_argument("--skip-tree", action="store_true",
                         help="vollen Subclass-Baum ueberspringen (nur Werkstoff-Check)")
    parser.add_argument("--depth", type=int, default=1,
                         help="Tiefe des Subclass-Baums (Default 1: 413 direkte "
                              "Subklassen, vollstaendig. Der volle Baum hat "
                              "~936.000 Klassen und ist weder in einer Abfrage "
                              "holbar noch zeichenbar - ab Tiefe 2 liefert "
                              "--max-nodes zwangslaeufig einen Ausschnitt)")
    parser.add_argument("--max-nodes", type=int, default=500,
                         help="Obergrenze fuer Knoten im Subclass-Baum (Default 500)")
    parser.add_argument("--trace", metavar="QID", nargs="+",
                         help="statt des Standardlaufs: die Pfade von einer oder "
                              "mehreren QIDs hinauf zur Wurzel zeigen, alle in "
                              "einem Graphen (z. B. --trace Q11427 Q39782)")
    parser.add_argument("--trace-root", metavar="QID", default=ROOT_QID,
                         help=f"Zielwurzel fuer --trace (Default {ROOT_QID} "
                              f"material; z. B. Q79529 fuer die chemische Achse)")
    parser.add_argument("--trace-out", metavar="PNG", default="trace_graph.png",
                         help="Ausgabedatei fuer den Trace-Graphen")
    args = parser.parse_args()

    # QID direkt angeben umgeht die Labelsuche - wbsearchentities loest z. B.
    # "Stahl" auf Q1236029 (Familienname) statt auf den Werkstoff Q11427 auf.
    if args.trace:
        root = args.trace_root
        root_label = fetch_labels([root]).get(root, root)
        traces, all_labels = [], {}
        for qid in args.trace:
            paths, labels = trace_to_root(qid, root_qid=root)
            all_labels.update(labels)
            name = f"{labels.get(qid, qid)} ({qid})"
            if not paths:
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
            plot_trace(traces, all_labels, root_qid=root, path_png=args.trace_out,
                       title=f"Pfade zu {root_label} ({root})")
        else:
            print("Kein einziger Pfad gefunden - kein Graph geschrieben.",
                  file=sys.stderr)
        return

    if not args.skip_tree:
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


if __name__ == "__main__":
    main()
