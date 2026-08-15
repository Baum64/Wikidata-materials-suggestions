# Kategorie Hirachie — Wikidata-Klassenhierarchie der Werkstoffe

Prüft und zeichnet, wie Werkstoffe in der Wikidata-Klassenhierarchie unter
`material` (Q214609) hängen — und macht sichtbar, welche stattdessen über
einen **parallelen Zweig** laufen.

## Der strukturelle Befund

Aus den Constraint-Definitionen von `P186` "made from material" abgeleitet:

> Wikidata modelliert `material` (Q214609) **nicht** als gemeinsame Oberklasse
> aller Werkstoffe. `P186` erlaubt mehrere **gleichrangige** Werttypen
> nebeneinander: material (Q214609), alloy (Q37756), chemical compound
> (Q11173), chemical element (Q11344), substance (Q10683158), building
> material (Q206615), food (Q2095), physical object (Q223557) …

Eine Legierung (Edelstahl) oder eine chemische Verbindung (Siliciumcarbid)
braucht also **keinen** `P279*`-Pfad bis Q214609, um korrekt eingeordnet zu
sein — sie hängt an einer parallelen Klassenhierarchie. Ein "kein Pfad"-Befund
ist deshalb nicht automatisch ein Fehler, aber für eine materialorientierte
Auswertung überraschend. Genau das prüft dieses Skript empirisch.

Praktische Folge für [../benchmark/](../benchmark/): dessen Grundgesamtheit
muss Instanzen **und** Unterklassen vereinigen, sonst zählt sie an den
tatsächlich modellierten Werkstoffen vorbei.

## Nutzung

Aus dem Repo-Wurzelverzeichnis (Installation siehe [../README.md](../README.md);
dieses Werkzeug braucht zusätzlich `networkx` und `matplotlib`):

```bash
# Standardlauf: Subclass-Baum + Werkstoff-Check der Default-Liste
python "Kategorie Hirachie/material_hierarchy_check.py"

# eigene Liste, ohne den großen Baum
python "Kategorie Hirachie/material_hierarchy_check.py" --skip-tree \
    --materials Stahl Titan Beton Diamant PVC

# Pfade einzelner QIDs nach oben verfolgen, alle in einem Graphen
python "Kategorie Hirachie/material_hierarchy_check.py" \
    --trace Q11427 Q39782 --trace-out trace_werkstoffe_material.png
```

| Option | Bedeutung |
|---|---|
| `--materials` | zu prüfende Werkstoffe (Standard: Stahl, Edelstahl, Titan, Aluminium, Beton, Glas, Diamant, Polyethylen, PVC, Siliciumcarbid, Holz, Kupfer) |
| `--skip-tree` | den vollen Subclass-Baum überspringen, nur den Werkstoff-Check laufen lassen |
| `--depth` | Tiefe des Subclass-Baums (Standard 1 = die 413 direkten Subklassen, vollständig) |
| `--max-nodes` | Obergrenze für Knoten im Baum (Standard 500) |
| `--trace` | statt des Standardlaufs: die Pfade einer oder mehrerer QIDs hinauf zur Wurzel zeigen |
| `--trace-root` | Zielwurzel für `--trace` (Standard `Q214609` material; z.B. `Q79529` für die chemische Achse) |
| `--trace-out` | Ausgabedatei für den Trace-Graphen (Standard `trace_graph.png`) |

**QIDs direkt angeben**, wo es auf Genauigkeit ankommt: die Labelsuche löst
z.B. "Stahl" auf `Q1236029` (Familienname) auf statt auf den Werkstoff
`Q11427`. Genau dieser Fall steht als `AUFFAELLIG` in der Beispiel-CSV.

Der volle Baum unter Q214609 umfasst rund **936.000 Klassen** — weder in einer
Abfrage holbar noch als Bild lesbar. Ab `--depth 2` liefert `--max-nodes`
zwangsläufig einen Ausschnitt.

## Ausgabedateien

Alle landen im aktuellen Arbeitsverzeichnis und sind gitignoriert:

| Datei | Inhalt |
|---|---|
| `werkstoff_check.csv` | eine Zeile je geprüftem Werkstoff: `input`, `qid`, `label`, `status`, `via_subclass_of`, `via_instance_of`, `direct_instance_of`, `direct_subclass_of` |
| `werkstoff_graph.png` | die geprüften Werkstoffe mit ihrer tatsächlichen Anbindung (rot = kein Pfad zu Q214609, grün = Pfad vorhanden) |
| `subclass_tree_material.png` | Subclass-Hierarchie unter Q214609, begrenzt durch `--depth` / `--max-nodes` |
| `trace_*.png` | Pfad-Graphen aus `--trace` |

Status in der CSV ist entweder `OK (Pfad zu material vorhanden)`,
`AUFFAELLIG (kein Pfad zu material)` oder `NICHT_GEFUNDEN`, wenn die
Labelsuche nichts liefert.

## Vor dem Einsatz anpassen

`USER_AGENT` oben im Skript mit echtem Namen/Kontakt füllen. Zwischen allen
SPARQL- und API-Aufrufen liegt eine Pause von 1 s, mit Backoff bei Fehlern.
