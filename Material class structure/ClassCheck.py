"""
P279-Struktur der Werkstoffe pruefen und eine gestaffelte Empfehlung entwerfen
=============================================================================

Der Benchmark in benchmark/ misst, welche MESSWERTE an den Werkstoff-Items
fehlen. Dieses Skript misst etwas anderes: ob die Items ueberhaupt richtig
EINGEHAENGT sind - also wie P279 (Unterklasse von) unterhalb der Werkstoffe
verwendet wird, wo die Kante fehlt, wo sie doppelt ist, wo sie verkehrt herum
zeigt und wo statt P279 faelschlich P31 steht.

Hier sind zwei Ansaetze zusammengefuehrt: die Strukturpruefungen auf dem
P279-Graphen und die Label-Heuristik aus dem frueheren
material_subclass_check.py, das darin aufgegangen ist.

Warum ueberhaupt? Aus dem Vorlauf dieses Repos sind drei Befunde bekannt:

  * Wikidata fuehrt "Metall" (Q11426) als UNTERKLASSE von "Legierung"
    (Q37756) - fachlich verkehrt herum. Dadurch haengt jedes Metall samt
    Isotopen unter "Legierung"; materialswiki muss das mit einem Filter
    ausgleichen (LEGIERUNG_OHNE_ELEMENTE). Der Filter kuriert das Symptom,
    die Kante bleibt.
  * Die Gruppierung der benannten Legierungen nach Basismetall, die
    [[en:List of named alloys]] vorgibt, existiert in Wikidata so nicht.
  * [[Wikidata:WikiProject Materials/Materials]] wuenscht eine differenzierte
    Einhaengung (Material -> Metallic material -> Alloy -> Ferrous alloy ->
    Steel -> Alloy steel -> ...). Die laesst sich aus dem Basismetall allein
    NICHT ableiten.

Die Ausgabe: EINE gestaffelte Empfehlung
----------------------------------------
Es entsteht genau eine Datei, und sie ist zum Durchsehen am Bildschirm
gebaut. Vier Stufen, sortiert nach BEWEISKRAFT - nicht nach Wichtigkeit.
Der Leser kann jederzeit aufhoeren; das Gepruefte bleibt gueltig.

  Stufe 1  MECHANISCH SICHER      folgt allein aus dem Graphen und behauptet
                                  nichts. Als einzige ausfuehrbar.
  Stufe 2  STRUKTURELL BEGRUENDET aus dem Graphen abgeleitet, aber mit einer
                                  fachlichen Entscheidung davor.
  Stufe 3  GERECHNET/GERATEN      aus einer Bezeichnung oder einem Messwert
                                  gegen eine Konvention.
  Stufe 4  NUR MELDUNG            beschreibt die Lage, fordert nichts.

Innerhalb einer Stufe wird nach EIGENSCHAFT gegliedert (P279, P31, P361),
darunter nach Befundart, darunter nach ZIEL - nicht nach Item. Der
Unterschied ist beim Durchsehen der ganze Punkt: nach Item sortiert steht
in der Datei hundertmal dieselbe Ueberlegung neu da, nach Ziel sortiert
steht einmal "diese 21 Items werden Uebergangsmetalle", und wer das Ziel
einmal geprueft hat, arbeitet die Gruppe darunter am Stueck ab. Wo alle
Vorschlaege einer Zielgruppe dieselbe Pruefanweisung tragen, steht sie
einmal im Gruppenkopf statt in jedem Eintrag.

FREIGEBEN HEISST: EIN ZEICHEN LOESCHEN. Ab Stufe 2 steht jeder Entwurf als
"#Q123<TAB>P279<TAB>Q456" da - ein einzelnes '#' davor, ohne Leerzeichen.
QuickStatements liest es als Kommentar; wer die Zeile freigibt, loescht genau
dieses eine Zeichen. Fliesstext traegt dagegen immer '# ' MIT Leerzeichen,
im Editor findet die Suche nach "#Q" und "#-Q" also trotzdem genau die
Entwuerfe. Die Datei laesst sich jederzeit als GANZES nach QuickStatements
kopieren, ohne dass eine ungepruefte Zeile zur Aussage wird.

Die Datei ist zum UEBERFLIEGEN gebaut, nicht zum Lesen: ein Vorschlag sind
in der Regel zwei Zeilen. Was sich wiederholen wuerde - Zielklasse, Link,
Pruefanweisung - steht einmal im Gruppenkopf. Fuer die 118 Elemente sind das
rund 600 Zeilen statt rund 1130.

Die zwoelf Pruefungen
--------------------
  1. kennzahlen        Wie wird P279 in der Grundgesamtheit ueberhaupt
                       benutzt: P279, P31, beides, keines; Mehrfacheltern;
                       Tiefe.
  2. redundant         Item hat P279 auf A UND auf B, wobei A ueber P279
                       ohnehin bei B landet -> ENTFERNEN.        [Stufe 1]
                       Aber nur, wenn der Ersatzpfad selbst haelt: laeuft er
                       ueber eine Kante aus Pruefung 5, wird der Befund zu
                       'redundant-unsicher'.                     [Stufe 2]
  3. instanz-als-klasse  Item hat P31 auf eine Werkstoffklasse, ist aber
                       selbst Oberklasse von etwas.              [Stufe 2]
  4. metaklasse        Legierung ohne chemische Metaklasse: die Guideline
                       des WikiProject Chemistry verlangt an jedem Item einer
                       chemischen Entitaet genau EINE, fuer Gemische
                       Q119892838. Aus der Klassenzugehoerigkeit, nicht aus
                       dem Namen.                                [Stufe 2]
                       ENTWORFEN wird sie nur an Items, die selbst KEINE
                       Klasse sind. Ist das Item eine Werkstoffklasse (hat
                       es P279 oder Unterklassen), bleibt es bei der
                       Meldung - siehe pruefe_metaklasse().      [Stufe 4]
  5. verkehrt          Kante n -> p, obwohl unter n mehr haengt als unter p
                       ohne n - der Metall/Legierung-Fall, generisch
                       gefasst. Siehe verkehrt_kandidaten().     [Stufe 2]
  6. zyklus            Eine Klasse ist ueber P279 ihre eigene Oberklasse.
                       Immer ein Fehler, nie automatisch aufloesbar. [Stufe 2]
  7. zusammensetzung   Der Name nennt die Zusammensetzung ("Nickel brass
                       (70% Copper, 18% Zinc, 12% Nickel)"). Das Element mit
                       dem groessten Anteil IST das Basismetall, damit steht
                       die Legierungsklasse fest - hier Kupferlegierung.
                       Diese Auswertung raet nicht, sie rechnet.  [Stufe 3]
  8. zu-allgemein      Item haengt direkt unter einer sehr allgemeinen
                       Klasse, obwohl seine Bezeichnung eine speziellere
                       nennt. Aus material_subclass_check.py uebernommen,
                       mit drei Filtern, ohne die es nicht traegt - siehe
                       den Block bei ALLGEMEINE_WURZELN.         [Stufe 3]
  9. ohne-einordnung   Benannte Legierung ohne jeden Pfad zu "Legierung".
                       Wo es fuer das Basismetall eine Klasse GIBT, wird sie
                       vorgeschlagen.                            [Stufe 3]
 10. p31-neben-p279    Item haengt direkt unter einer allgemeinen Klasse und
                       hat zusaetzlich P31. Nur Meldung - siehe
                       pruefe_p31_neben_p279() dazu, warum kein Entwurf
                       daraus wird.                              [Stufe 4]
 11. parallelzweig     Item ohne P279*-Pfad zu "material" (Q214609). Kein
                       Fehler (P186 erlaubt mehrere gleichrangige Werttypen,
                       siehe visualisierung.py daneben).        [Stufe 4]
 12. elementklasse     NUR im Szenario 'periodensystem' (siehe unten). Drei
                       Fragen an ein chemisches Element: fehlt die
                       Elementkategorie (Alkalimetall, Uebergangsmetall,
                       Halbmetall, ...), fehlt die Gruppe des
                       Periodensystems, und ist es nach seiner Dichte ein
                       Leicht- oder ein Schwermetall.  [Stufe 2, 3 und 4]

Das Szenario 'periodensystem'
-----------------------------
--population periodensystem prueft NUR die 118 chemischen Elemente, und nur
mit den Pruefungen, die dort etwas bedeuten (kennzahlen, elementklasse,
redundant, zyklus - ueberschreibbar mit --pruefungen). Es ist der einzige
Fall in diesem Skript, in dem die Grundgesamtheit abgeschlossen und der
Massstab bekannt ist: aus der Ordnungszahl (P1086) folgt die Stellung im
Periodensystem, also auch die Kategorie und die Gruppe. Hier wird nichts
aus Bezeichnungen geraten - hier wird nachgerechnet.

Der Schwerpunkt liegt auf den Unterklassen: Uebergangsmetalle (Q19588),
Leicht- (Q428766) und Schwermetalle (Q105789) und die einzelnen
Hauptgruppen. Der Ist-Zustand ist loechrig - gemessen am 2026-08-29 tragen
17 der 38 Uebergangsmetalle ihre Kategorie, Leichtmetall steht an genau
einem Element, die 15 Lanthanoide tragen zusammen kein einziges P279. Die
Gruppen dagegen sind ueber P361 vollstaendig gepflegt; an einzelnen
Elementen stehen sie aber als P279 daneben.

Wo die Lehrbuecher uneinig sind - die 12. Gruppe (Zink, Cadmium,
Quecksilber), Selen, Polonium, Astat und alles ab Ordnungszahl 113, wo die
Eigenschaften nur berechnet sind - entsteht bewusst KEIN Entwurf, sondern
eine Meldung mit den Lesarten. Dasselbe bei der Dichte: die 5-g/cm3-Grenze
zwischen Leicht- und Schwermetall ist Konvention, deshalb bleibt ein
Graubereich von 0,5 g/cm3 darum herum vorschlagsfrei.

Alle Pruefungen bleiben in der Werkstoff-Ecke - unterhalb von material
(Q214609) oder Legierung (Q37756), plus die Grundgesamtheit selbst. Das ist
keine Bequemlichkeit: die P279-Huelle nach oben endet zwangslaeufig in der
obersten Ontologie, und dort finden dieselben Pruefungen dieselben Fehler bei
"Begriff", "Typ" oder "Kunstgewerbe". Die Befunde waeren richtig und trotzdem
nicht unsere Sache - eine dort eingespielte Aenderung trifft hunderttausende
Items ausserhalb jedes Werkstoffbezugs.

Vier Sperren gegen den eigenen Unsinn
-------------------------------------
Die Pruefungen widersprechen sich, wenn man sie einzeln laufen laesst. Das
faellt beim Bauen nicht auf, beim Einspielen schon:

  * Eine Redundanz, deren Ersatzpfad ueber eine beanstandete Kante laeuft,
    ist keine. Sonst entfernt man die gute Kante und repariert spaeter die
    schlechte - und das Item haengt nirgends mehr.
  * Eine beanstandete Klasse taugt nicht als ZIEL einer Umhaengung. Sonst
    schlaegt dasselbe Skript vor, ein Item unter eine Klasse zu haengen,
    deren Platz es zwei Stufen weiter oben in Frage stellt.
  * Chemische Elemente (P1086) taugen nie als Ziel. Sie stehen nur wegen der
    falschen Metall/Legierung-Kante im Kandidatenpool.
  * Klasse und Instanz werden vor JEDEM Entwurf getrennt. [[Help:Basic
    membership properties]] sagt, woran man eine Klasse erkennt: sie hat
    P279 oder Unterklassen. Daraus folgt beides -
      an eine Werkstoffklasse schreibt dieses Werkzeug kein P31, und
      an eine Instanz kein P279.
    Wo die Klassenzugehoerigkeit aus dem Graphen nicht folgt, entsteht eine
    Meldung statt eines Entwurfs. Das ist der Grund, warum Pruefung 4 und
    Pruefung 9 seltener entwerfen als frueher.

Ausgabe
-------
  proposals/qs_class_<Population>_<Zeitstempel>.txt   die Empfehlung
  --csv <pfad>                                       zusaetzlich, optional
Beide landen in proposals/ (CLAUDE.md, "Arbeitsweise" Punkt 2) - im selben
Ordner wie alles, was "python -m lauf <gruppe>" schreibt. --out-dir stellt
den Ordner um.

Aufruf
------
Kurz ueber den gemeinsamen Sammelbefehl (empfohlen - Ausgabe landet mit
Benchmark und materialswiki im selben proposals/-Ordner):

  python -m lauf legierungen --nur-struktur
  python -m lauf periodensystem --nur-struktur
  python -m lauf legierungen --struktur          # zusammen mit dem Rest

Direkt:

  python "Material class structure/ClassCheck.py"
  python "Material class structure/ClassCheck.py" --population legierungen
  python "Material class structure/ClassCheck.py" --pruefungen redundant verkehrt
  python "Material class structure/ClassCheck.py" --pruefungen metaklasse
  python "Material class structure/ClassCheck.py" --tiefe 3 --beleg beides
  python "Material class structure/ClassCheck.py" --vorsichtig   # nichts einspielbar
  python "Material class structure/ClassCheck.py" --population periodensystem --ohne-dichte
  python "Material class structure/ClassCheck.py" --population oxide
  python "Material class structure/ClassCheck.py" --population material --out-dir laeufe/

Grundgesamtheiten (--population)
-------------------------------
  benannte-legierungen   die Prueferliste aus [[en:List of named alloys]] (Vorgabe)
  legierungen            Legierungen unter Q37756, ohne Elemente/Isotope
  metallischer-werkstoff unterhalb von Q1924900
  material               unterhalb von Q214609
  oxide                  Oxide mit Summenformel (Q50690) - dieselbe Menge wie
                         'python -m lauf oxide'; eigene Pruefungsauswahl
  periodensystem         die 118 chemischen Elemente (P31 Q11344)
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys
from typing import Optional

# Dieser Ordner (wikidata_graph) UND die Repo-Wurzel (materialswiki) in den
# Pfad. Die Grundgesamtheiten werden aus materialswiki importiert, nicht
# kopiert - dasselbe Vorgehen wie in benchmark/benchmark.py, sonst driften
# Benchmark und Vorschlagslauf auseinander.
_HIER = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HIER)
sys.path[:0] = [_HIER, _REPO]

# Alle Vorschlagsdateien gehoeren nach proposals/ (CLAUDE.md, "Arbeitsweise"
# Punkt 2) - unabhaengig davon, aus welchem Verzeichnis das Skript startet.
PROPOSALS_DIR = os.path.join(_REPO, "proposals")

from materialswiki.cli import (  # noqa: E402
    KUNSTSTOFF_QID, LEGIERUNG_PATTERN, LEGIERUNG_QID,
    MAGNET_PATTERN, MAGNETWERKSTOFF_QID, OXID_PATTERN, fetch_named_alloys,
)

# Die Wikidata-Zugriffsschicht teilt sich dieses Skript mit visualisierung.py
# daneben - HTTP-Retry, SPARQL-POST, QID-Zerlegung, VALUES-Stueckelung.
from wikidata_graph import (  # noqa: E402
    ENWIKI_API, hole_labels_api, in_bloecken, qid as qid_aus,
    request_with_retry, sparql, werte_klausel,
)

try:
    import networkx as nx
except ImportError:  # pragma: no cover - Hinweis ist hilfreicher als Traceback
    raise SystemExit(
        "networkx fehlt. Installation: pip install -r requirements.txt")

MATERIAL_QID = "Q214609"        # material
METALL_WERKSTOFF_QID = "Q1924900"  # metallischer Werkstoff
OXID_QID = "Q50690"             # Oxid - Bereichswurzel der Grundgesamtheit 'oxide'

SUBTREE_PATTERN = (
    "{{ ?i wdt:P31/wdt:P279* wd:{root} }} UNION {{ ?i wdt:P279* wd:{root} }}"
)

# Fuer die grossen Wurzeln (material, metallischer Werkstoff) nur die KLASSEN,
# nicht zusaetzlich jede Instanz jeder Unterklasse. Der Instanz-Zweig
# (P31/P279*) laesst die Abfrage unter Q214609 zuverlaessig ins Timeout
# laufen - ~936.000 Treffer - und ein zufaelliger Instanz-Ausschnitt sagt
# fuer eine Strukturpruefung ohnehin nichts. Diese Grundgesamtheiten sind als
# "gross" markiert und brauchen ein --limit (siehe hole_population).
SUBTREE_KLASSEN_PATTERN = "?i wdt:P279* wd:{root} ."

# ---------------------------------------------------------------------------
# Szenario Periodensystem: die Einordnung der chemischen Elemente
# ---------------------------------------------------------------------------
#
# Ein eigenes Szenario, weil hier eine Sonderlage herrscht, die es sonst
# nirgends gibt: die Grundgesamtheit ist ABGESCHLOSSEN und VOLLSTAENDIG
# BEKANNT. 118 Elemente, jedes mit einer Ordnungszahl (P1086), und aus der
# Ordnungszahl allein folgt die Stellung im Periodensystem. Es muss also
# nichts aus Bezeichnungen geraten werden - die Zuordnung steht im Lehrbuch
# und laesst sich Zeile fuer Zeile nachrechnen.
#
# Warum ueberhaupt? Der Ist-Zustand ist loechrig (gemessen 2026-08-29 an
# allen 118 Elementen):
#
#   * 17 der 38 Uebergangsmetalle tragen Q19588; Chrom, Mangan, Eisen,
#     Cobalt, Nickel und Kupfer nicht.
#   * Leichtmetalle (Q428766) steht an genau EINEM Element (Titan),
#     Schwermetalle (Q105789) an genau einem (Wolfram).
#   * Die 15 Lanthanoide tragen zusammen KEIN einziges P279.
#   * Die Gruppen dagegen sind ueber P361 nahezu vollstaendig gepflegt -
#     alle 18 Gruppen sind besetzt. An einzelnen Elementen steht die Gruppe
#     aber als P279 statt als P361 (Sauerstoff, Fluor, Chlor, Schwefel).
#
# Die Zuordnungen unten sind nach Ordnungszahl aufgeschrieben und NICHT aus
# Wikidata geholt - das ist hier ausdruecklich richtig herum: sie sind der
# Massstab, gegen den Wikidata geprueft wird. Eine aus Wikidata geholte
# Erwartung wuerde nur bestaetigen, was ohnehin dort steht.

ELEMENT_QID = "Q11344"          # chemisches Element
LETZTE_ORDNUNGSZAHL = 118       # Oganesson; darueber gibt es nur Entwuerfe

# Die Elementkategorien. Die Bezeichnungen sind die deutschen aus Wikidata,
# damit der Vorschlag im Editor wiederzuerkennen ist. Zugeordnet wird per
# P31, nicht P279 - siehe .claude/rules/periodic-table-conventions.md:
# ein Element ist eine Instanz, keine Klasse.
ELEMENTKATEGORIEN = {
    "Q19557": "Alkalimetalle",
    "Q19563": "Erdalkalimetalle (2. Gruppe)",
    "Q19569": "Lanthanoide",
    "Q19577": "Actinoide",
    "Q19588": "Uebergangsmetalle",
    "Q19591": "Metalle des p-Blocks",
    "Q19596": "Halbmetalle",
    "Q19600": "Nichtmetalle",
    "Q19605": "Halogene (17. Gruppe)",
    "Q19609": "Edelgase (18. Gruppe)",
}

# Leicht- und Schwermetall sind KEINE Kategorien des Periodensystems,
# sondern eine Einteilung nach Dichte - deshalb stehen sie getrennt und
# werden auch getrennt geprueft (aus P2054 gerechnet, nicht aus der
# Ordnungszahl abgeleitet).
LEICHTMETALL_QID = "Q428766"
SCHWERMETALL_QID = "Q105789"
# Die uebliche Grenze der deutschsprachigen Literatur. Sie ist Konvention,
# nicht Physik - andere Quellen nennen 4,5 g/cm3. Deshalb ein Graubereich
# darum herum, in dem NICHTS vorgeschlagen wird: Beryllium (1,85), Titan
# (4,51) und Vanadium (6,0) sind eindeutig, Scandium (2,99) auch - aber wer
# knapp an der Grenze liegt, wird nicht per Schwellwert entschieden.
DICHTE_GRENZE = 5.0             # g/cm3
DICHTE_GRAUBEREICH = 0.5        # g/cm3 beidseits der Grenze

# Einheiten, in denen P2054 an den Elementen tatsaechlich steht, mit dem
# Faktor auf g/cm3. Alles andere wird uebersprungen statt geraten.
DICHTE_EINHEITEN = {
    "Q13147228": 1.0,        # Gramm pro Kubikzentimeter
    "Q844211": 0.001,        # Kilogramm pro Kubikmeter
}

# Die Gruppen des Periodensystems (P31 = Q83306). Die QIDs sind an den
# Elementen geprueft, die schon ein P361 tragen - die deutschen Labels sind
# teilweise irrefuehrend ("4. Hauptgruppe" heisst dort die 4. GRUPPE), die
# Mitgliederlisten dagegen sind eindeutig.
GRUPPEN_QID = {
    1: "Q10801007", 2: "Q19563", 3: "Q108307", 4: "Q189302",
    5: "Q193276", 6: "Q193280", 7: "Q202602", 8: "Q202224",
    9: "Q208107", 10: "Q205253", 11: "Q185870", 12: "Q191875",
    13: "Q189294", 14: "Q106693", 15: "Q106675", 16: "Q104567",
    17: "Q19605", 18: "Q19609",
}

# Die acht HAUPTGRUPPEN - der Schwerpunkt dieses Szenarios. Die uebrigen
# zehn sind Nebengruppen und stehen nur der Vollstaendigkeit halber mit da.
HAUPTGRUPPEN = {1, 2, 13, 14, 15, 16, 17, 18}

# Grundgesamtheiten. 'legierungen' kommt woertlich aus materialswiki, damit
# dieses Skript und der Vorschlagslauf garantiert dieselbe Menge meinen.
POPULATIONEN = {
    "legierungen": {
        "pattern": LEGIERUNG_PATTERN,
        "beschreibung": "Legierungen (Q37756, ohne Elemente und Isotope)",
    },
    "benannte-legierungen": {
        "pattern": None,  # kommt aus der Wikipedia-Liste, nicht aus SPARQL
        "beschreibung": "benannte Legierungen aus [[en:List of named alloys]]",
    },
    "metallischer-werkstoff": {
        "pattern": SUBTREE_KLASSEN_PATTERN.format(root=METALL_WERKSTOFF_QID),
        "beschreibung": "Klassen unterhalb von metallischer Werkstoff (Q1924900)",
        "gross": True,
    },
    "material": {
        "pattern": SUBTREE_KLASSEN_PATTERN.format(root=MATERIAL_QID),
        "beschreibung": "Klassen unterhalb von material (Q214609)",
        "gross": True,
    },
    # Oxide - dieselbe Menge wie 'python -m lauf oxide' und der Benchmark:
    # OXID_PATTERN kommt woertlich aus materialswiki.gruppen, damit die drei
    # Werkzeuge garantiert dieselbe Grundgesamtheit meinen. Die Summenformel
    # (P274) ist dort Teil der Definition - ohne sie besteht der Subtree unter
    # Q50690 fast nur aus 27000 labellosen Massenimporten, ein untauglicher
    # Kandidatenpool (siehe DEFAULT_TIEFE).
    #
    # Andere Pruefungen als die Legierungs-Voreinstellung: 'metaklasse',
    # 'zusammensetzung' und 'ohne-einordnung' setzen den Legierungsbezug
    # (Q37756, [[List of named alloys]]) voraus und finden an Oxiden nichts;
    # 'elementklasse' braucht die Ordnungszahl. 'zu-allgemein' und
    # 'p31-neben-p279' holen einen Kandidatenpool unter material/Legierung
    # (tausende Items), der die Oxidwurzel gar nicht enthaelt - teuer und
    # fruchtlos. Bleibt der Strukturkern auf dem Graphen selbst.
    "oxide": {
        "pattern": OXID_PATTERN,
        "beschreibung": "Oxide mit Summenformel (Q50690) - wie 'lauf oxide'",
        "pruefungen": ["kennzahlen", "redundant", "verkehrt",
                       "instanz-als-klasse", "zyklus", "parallelzweig"],
        "bereichswurzel": OXID_QID,
    },
    # Das Szenario Periodensystem. Es teilt sich mit den uebrigen nur den
    # Rahmen (Graph, Staffelung, Ausgabe) - die Pruefungen sind andere,
    # deshalb bringt es seine eigene Voreinstellung mit. Wer '--pruefungen'
    # angibt, ueberschreibt sie.
    "periodensystem": {
        "pattern": ("?i wdt:P31 wd:Q11344 ; wdt:P1086 ?z . "
                    f"FILTER(?z <= {LETZTE_ORDNUNGSZAHL})"),
        "beschreibung": ("die chemischen Elemente (P31 Q11344, "
                         f"Ordnungszahl bis {LETZTE_ORDNUNGSZAHL})"),
        "pruefungen": ["kennzahlen", "elementklasse", "redundant", "zyklus"],
        "bereichswurzel": ELEMENT_QID,
    },
    # Polymere/Kunststoffe und Magnetwerkstoffe. Wie bei 'oxide' der
    # reduzierte Strukturkern: 'metaklasse', 'zusammensetzung',
    # 'zu-allgemein' und 'ohne-einordnung' setzen den Legierungsbezug
    # (Q37756, [[List of named alloys]]) voraus und finden hier nichts;
    # 'elementklasse' braucht die Ordnungszahl.
    #
    # polymer prueft NUR die Klassen (P279*, ~206) - anders als der
    # materialswiki-/Benchmark-Lauf, der ueber KUNSTSTOFF_PATTERN auch die
    # Instanzen mitnimmt. Fuer eine Strukturpruefung sind die Instanzen
    # (konkrete Kunststoffsorten, per P31 an ihrer Klasse) nur Rauschen:
    # 'parallelzweig' meldete sonst ~580x "kein P279*-Pfad zu material",
    # was fuer Instanzen normal ist. Gleiche Logik wie bei 'material' /
    # 'metallischer-werkstoff' (SUBTREE_KLASSEN_PATTERN).
    #
    # magnetwerkstoffe ist mit dem Isotopenfilter ohnehin nur 10 Klassen -
    # da schadet der Instanzzweig nicht, und MAGNET_PATTERN bleibt mit dem
    # Benchmark identisch.
    "polymer": {
        "pattern": SUBTREE_KLASSEN_PATTERN.format(root=KUNSTSTOFF_QID),
        "beschreibung": "Klassen der Polymere / Kunststoffe (Q11474)",
        "pruefungen": ["kennzahlen", "redundant", "verkehrt",
                       "instanz-als-klasse", "zyklus", "parallelzweig"],
        "bereichswurzel": KUNSTSTOFF_QID,
    },
    "magnetwerkstoffe": {
        "pattern": MAGNET_PATTERN,
        "beschreibung": ("Magnetwerkstoffe (Q949573, ohne Isotope) - wie "
                         "'lauf magnetwerkstoffe'"),
        "pruefungen": ["kennzahlen", "redundant", "verkehrt",
                       "instanz-als-klasse", "zyklus", "parallelzweig"],
        "bereichswurzel": MAGNETWERKSTOFF_QID,
    },
}

PRUEFUNGEN = ["kennzahlen", "zyklus", "redundant", "verkehrt",
              "instanz-als-klasse", "metaklasse", "zusammensetzung",
              "zu-allgemein", "ohne-einordnung", "p31-neben-p279",
              "parallelzweig", "elementklasse"]

# Pruefungen, die nur in der Grundgesamtheit 'periodensystem' etwas
# bedeuten. Sie brauchen die Ordnungszahl - ausserhalb des Periodensystems
# hat kein Item eine.
NUR_PERIODENSYSTEM = {"elementklasse"}

# ---------------------------------------------------------------------------
# Chemische Metaklasse (P31) fuer Legierungen
# ---------------------------------------------------------------------------
#
# [[Wikidata:WikiProject Chemistry/Guidelines/Basic metaclasses and relations]]
# verlangt an JEDEM Item einer chemischen Entitaet genau EINE Metaklasse ueber
# P31 - und fuer Gemische ausdruecklich eine eigene, nicht die der reinen
# Stoffe. Eine Legierung ist per Definition ein Gemisch (Q37756: "mixture or
# metallic solid solution"), die Metaklasse ist damit eindeutig bestimmt und
# muss nicht geraten werden.
#
# Diese Pruefung stand bis 2026-08-23 in materialswiki (Stufe --metaklasse)
# und gehoert hierher: sie folgt aus der KLASSENZUGEHOERIGKEIT des Items,
# nicht aus einer Messung. Dieses Skript hat den P279-Graphen ohnehin schon
# im Speicher - dort kostet die Pruefung keine einzige zusaetzliche Abfrage,
# waehrend materialswiki sie sich mit einer eigenen SPARQL-Runde je Charge
# erkaufen musste. Zahlen und Abgrenzung: README, "Chemische Metaklasse
# (P31) fuer Legierungen".

# Die Metaklasse fuer Gemische. Q119896085 ("Art von Polymer") ist ihre
# einzige Unterklasse in der Guideline und fuer Legierungen nicht gemeint.
GEMISCH_METAKLASSE = "Q119892838"   # "definiertes Gemisch chemischer Substanzen"

# Alle Chemie-Metaklassen der Guideline. Traegt ein Item schon eine davon,
# wird KEINE zweite vorgeschlagen: "Every item should have only one metaclass
# from the above. No other chemistry-related metaclass should be present."
CHEMIE_METAKLASSEN = {
    "Q113145171": "definierte chemische Substanz",
    GEMISCH_METAKLASSE: "definiertes Gemisch chemischer Substanzen",
    "Q119896085": "Art von Polymer",
    "Q47154513": "offene Klasse (Struktur)",
    "Q56256173": "offene Klasse (Funktion)",
    "Q56256178": "offene Klasse (Herkunft)",
    "Q55640599": "geschlossene Klasse",
    "Q15711994": "geschlossene Klasse (Summenformel)",
    "Q59199015": "geschlossene Klasse (Stereoisomere)",
    "Q55662456": "geschlossene Klasse (ortho/meta/para)",
    "Q74892521": "unpraezise Klasse chemischer Substanzen",
}

# Mineralarten bleiben aussen vor: sie sind ueber die IMA modelliert
# (P31 = Q12089225), und ob ein Mineral zusaetzlich eine Chemie-Metaklasse
# tragen soll, ist eine Frage an das Mineralprojekt, nicht an dieses Werkzeug.
MINERALART_QID = "Q12089225"

# Wikidata fuehrt Q11426 "Metall" als Unterklasse von Q37756 "Legierung" -
# dieselbe schiefe Kante, an der sich die Pruefung 'verkehrt' abarbeitet.
# Ueber diesen Knoten haengt alles Metallische unter der Legierung, auch
# Sammelbegriffe wie "Platinmetalle" oder "metals of antiquity", die gar
# keine Werkstoffe sind, sondern Aufzaehlungen. Ihnen die Gemisch-Metaklasse
# zu geben waere schlicht falsch - siehe legierungs_items.
METALL_QID = "Q11426"

# ---------------------------------------------------------------------------
# Label-Heuristik: haengt ein Item zu allgemein?
# ---------------------------------------------------------------------------
#
# Uebernommen aus material_subclass_check.py, das in dieses Skript aufgegangen
# ist. Die Idee: ein Item, das DIREKT unter einer sehr allgemeinen Klasse
# haengt, traegt seine eigentliche Oberklasse oft im Namen ("Formgedaechtnis-
# KERAMIK" unter "Material", obwohl es "Keramik" gibt).
#
# Die Idee traegt - aber nur mit drei Filtern. Ohne sie war die Trefferquote
# unbrauchbar (gemessen 2026-08-23 an 325 Vorschlaegen):
#
#   * 42 % zielten auf Q16829513, ein ZWEITES Item namens "material", das
#     selbst unter Q214609 haengt. Formal eine Unterklasse, sachlich ein
#     Synonym - keine Spezialisierung. -> ALLGEMEINE_BEZEICHNUNGEN
#   * 60 % stuetzten sich allein auf die Beschreibung. Dass dort das Wort
#     "material" vorkommt, sagt nichts ueber die Klasse. -> --beleg
#   * Reine Substring-Zufaelle: "Mater" (Q5460003, flong) traf in
#     "MATERial", "compo" in "COMPOsite", "Stoff" in "InhaltsSTOFF".
#     -> Wortgrenzen statt roher Substring-Suche
ALLGEMEINE_WURZELN = {
    MATERIAL_QID: "material",
    LEGIERUNG_QID: "Legierung",
    METALL_WERKSTOFF_QID: "metallischer Werkstoff",
}

# Bezeichnungen, die als ZIEL nichts taugen: Synonyme der Wurzel selbst.
# Ein Vorschlag "haeng es unter 'material' statt unter 'material'" ist keiner.
ALLGEMEINE_BEZEICHNUNGEN = {
    "material", "materials", "werkstoff", "werkstoffe", "stoff", "substanz",
    "substance", "matter", "medium", "mater", "compo", "masse", "mass",
    "produkt", "product", "gegenstand", "objekt", "object", "ware",
}

# Mindestlaenge einer Bezeichnung, damit sie als Suchbegriff taugt.
MIN_LABEL_LEN = 4

# ---------------------------------------------------------------------------
# Zusammensetzung aus dem Namen
# ---------------------------------------------------------------------------
#
# Viele Items tragen ihre Legierungszusammensetzung im Namen:
#   "Nickel brass (70% Copper, 18% Zinc, 12% Nickel)"
# Daraus folgt das Basismetall zwingend - es ist das Element mit dem groessten
# Anteil - und damit die Legierungsklasse: hier Kupferlegierung.
#
# Das ist die belastbarste Namensauswertung im ganzen Skript: sie raet nicht,
# sie RECHNET. Deshalb steht sie in Stufe 3 vor der Namensaehnlichkeit.
#
# Zwei Schreibweisen kommen vor, beide muessen erkannt werden:
#   "90% Copper"     - Anteil zuerst
#   "Aluminium 98%"  - Element zuerst
ZUSAMMENSETZUNG_MUSTER = [
    re.compile(r"([\d]+(?:[.,]\d+)?)\s*%\s*([A-Za-z][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df-]{2,})"),
    re.compile(r"([A-Za-z][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df-]{2,})\s+([\d]+(?:[.,]\d+)?)\s*%"),
]

# Steht das im Namen, beschreiben die Prozente NUR die Auflage, nicht das
# Item: "Brass plated steel (Plating: 72.5% Copper, 27.5% Zinc)" ist kein
# Kupferwerkstoff, sondern Stahl mit Messingauflage. Hier waere die Regel
# falsch angewandt - deshalb wird gar nicht erst vorgeschlagen.
AUFLAGE_MARKER = ("plating:", "plating :", "coating:", "auflage:")

# Verbundbezeichnungen: die Prozente gelten fuer den ganzen Koerper, aber das
# Item ist ein Schichtverbund, keine Legierung. Vorschlag ja - aber mit
# ausdruecklicher Warnung, denn "Copper clad aluminium" ist kein
# Kupferwerkstoff, auch wenn Kupfer den groesseren Anteil haette.
VERBUND_MARKER = ("plated", "clad", "plattiert", "centre in", "center in",
                  "ring", "core")

# Ab welchem Abstand zum Zweitplatzierten das Basismetall als eindeutig gilt
# (in Prozentpunkten). Bei "48% Copper, 52% Aluminium" ist die Zuordnung
# eine Muenze auf der Kante, nicht ein Befund.
MIN_ABSTAND_PROZENT = 5.0

# Bis zu welcher Ebene unter der Wurzel der Kandidatenpool geholt wird.
# Groessenordnung unter material (gemessen 2026-08-23): Ebene 1 -> 392,
# Ebene 2 -> 5.787, Ebene 3 -> 14.974. Der VOLLE Baum hat 936.891 Items, ist
# in einer Abfrage nicht holbar - daran ist material_subclass_check.py mit
# 502 Bad Gateway abgebrochen - und waere als Pool auch nicht sinnvoll:
# weiter unten stehen einzelne Mineralien und Handelsprodukte, ein
# Substring-Treffer gegen die waere fast immer Zufall.
DEFAULT_TIEFE = 2

# ---------------------------------------------------------------------------
# Basismetall -> Legierungsklasse
# ---------------------------------------------------------------------------
#
# [[en:List of named alloys]] gruppiert nach Basismetall. Um daraus einen
# P279-Vorschlag zu machen, braucht es zu jedem Basismetall die passende
# KLASSE in Wikidata. Die wird gesucht, nicht geraten: ueber die englische
# Bezeichnung, und nur was selbst unter Q37756 haengt, zaehlt (siehe
# finde_basisklassen).
#
# Wikidata benennt diese Klassen uneinheitlich - mal "zinc alloy", mal
# "nickel-based alloy". Deshalb mehrere Muster je Basismetall.
KLASSEN_MUSTER = ["{b} alloy", "{b}-based alloy", "{b} based alloy",
                  "{b}-base alloy"]

# Abschnitte der Liste, die KEIN Basismetall benennen. Ohne diesen Filter
# landen "intermetallische Verbindung" und "list of brazing alloys" aus dem
# Abschnitt "See also" in der Grundgesamtheit und werden anschliessend als
# nicht klassifizierte Legierungen gemeldet - beides richtig und beides
# nutzlos, denn sie sollen dort gar nicht stehen.
# ("Alloys by base metal" ist die Einleitung, die nur die Basismetalle selbst
# auffuehrt; materialswiki filtert sie bereits beim Parsen.)
KEIN_BASISMETALL = {"See also", "References", "External links", "Notes",
                    "Further reading", "Bibliography", "Sources"}

# Die englische Wikipedia schreibt "Aluminum", Wikidata "aluminium". Ohne
# diese Umschrift findet die Suche die Klasse Q447725 nicht.
SCHREIBWEISEN = {
    "Aluminum": "aluminium",
    "Sulfur": "sulphur",
}

# Faelle, in denen das Muster nicht greift oder danebengreift. Jeder Eintrag
# braucht eine Begruendung - eine unbegruendete Zuordnung hier waere genau die
# fachliche Behauptung, die das Skript sonst vermeidet.
BASISKLASSEN_FEST = {
    # Amalgam IST die Quecksilberlegierung; "mercury alloy" gibt es nicht.
    "Mercury": ("Q182574", "amalgam"),
}

# Basismetalle, fuer die es in Wikidata KEINE Legierungsklasse gibt, obwohl
# die Projektseite eine verlangt. Nicht als Fehler melden, sondern als
# Luecke - anlegen kann dieses Werkzeug nichts.
#
# "Iron" ist der prominenteste Fall: [[Wikidata:WikiProject Materials]] nennt
# "Ferrous alloy" als Beispiel fuer die gewuenschte Zwischenklasse, in
# Wikidata existiert sie nicht (geprueft 2026-08-17). Q907347 "ferroalloy"
# ist NICHT dasselbe - das sind Vorlegierungen fuer die Stahlherstellung
# (Ferrochrom, Ferromangan), nicht die Oberklasse aller Eisenwerkstoffe.
BASISKLASSEN_BEKANNTE_LUECKE = {
    "Iron": "Ferrous alloy existiert nicht; Q907347 ferroalloy meint die "
            "Vorlegierung, nicht die Werkstoffklasse",
}


# HTTP-Drosselung, Retry, SPARQL-POST und qid_aus stehen in wikidata_graph.py
# und werden oben importiert - dieselbe Schicht nutzt visualisierung.py.


# ---------------------------------------------------------------------------
# Grundgesamtheit bestimmen
# ---------------------------------------------------------------------------

def hole_population_sparql(pattern: str, limit: Optional[int] = None) -> dict:
    """{qid: {'qid', 'label', 'basis'}} aus einem SPARQL-Muster."""
    grenze = f"LIMIT {limit}" if limit else ""
    zeilen = sparql(f"""
    SELECT DISTINCT ?i ?iLabel WHERE {{
      {pattern}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en". }}
    }} {grenze}
    """)
    return {qid_aus(b, "i"): {"qid": qid_aus(b, "i"),
                              "label": b.get("iLabel", {}).get("value", ""),
                              "basis": ""}
            for b in zeilen}


def hole_pruefliste(limit: Optional[int] = None) -> tuple:
    """({qid: eintrag}, [Titel ohne Item]) aus [[en:List of named alloys]].

    Die Aufloesung laeuft ueber die enwiki-Seiten-API MIT redirects=1, nicht
    ueber wbgetentities auf dem rohen Listentitel. Der Unterschied ist gross:
    die Liste verlinkt Weiterleitungen (Nitinol -> Nickel titanium, German
    silver -> Nickel silver, Heusler alloy -> Heusler compound, Lockalloy ->
    Beryllium-aluminium alloy), und ohne Aufloesung gelten deren Items als
    "nicht vorhanden". Genau daran sind im Vorlauf 25 Namen als itemlos
    gemeldet worden, die laengst ein Item haben.

    Ein Labelabgleich waere die falsche Alternative: bei "Mulberry" oder
    "Elektron" greift der munter daneben.
    """
    eintraege = [e for e in fetch_named_alloys()
                 if e["basis"] not in KEIN_BASISMETALL]
    if limit:
        eintraege = eintraege[:limit]
    nach_titel = {e["titel"]: e for e in eintraege}
    titel = list(nach_titel)

    # Schritt 1: Titel -> aufgeloester Titel -> QID, in Bloecken zu 50.
    ziel_von = {}   # Listentitel -> Titel nach Weiterleitung
    qid_von = {}    # aufgeloester Titel -> QID
    for start in range(0, len(titel), 50):
        block = titel[start:start + 50]
        daten = request_with_retry("GET", ENWIKI_API, params={
            "action": "query", "titles": "|".join(block), "redirects": 1,
            "prop": "pageprops", "ppprop": "wikibase_item",
            "format": "json", "formatversion": "2",
        }, timeout=60).json().get("query", {})
        for norm in daten.get("normalized", []):
            ziel_von[norm["from"]] = norm["to"]
        for weiter in daten.get("redirects", []):
            # Weiterleitungen koennen verkettet sein; erst am Ende aufloesen.
            ziel_von[weiter["from"]] = weiter["to"]
        for seite in daten.get("pages", []):
            wd = seite.get("pageprops", {}).get("wikibase_item")
            if wd:
                qid_von[seite["title"]] = wd

    def aufloesen(t: str, tiefe: int = 5) -> str:
        while t in ziel_von and tiefe:
            t, tiefe = ziel_von[t], tiefe - 1
        return t

    items, ohne_item = {}, []
    for t in titel:
        ziel = aufloesen(t)
        qid = qid_von.get(ziel)
        if not qid:
            ohne_item.append(t)
            continue
        # Zwei Listentitel koennen auf dasselbe Item zeigen (Weiterleitung
        # plus Zielartikel). Der erste gewinnt, das Basismetall des zweiten
        # geht dabei nicht verloren - es steht ohnehin im selben Abschnitt.
        items.setdefault(qid, {
            "qid": qid,
            "label": ziel,
            "basis": nach_titel[t]["basis"],
            "listentitel": t,
        })
    return items, sorted(ohne_item)


def hole_population(name: str, limit: Optional[int] = None) -> tuple:
    """(Items, Liste der Listennamen ohne Item)."""
    info = POPULATIONEN[name]
    if info.get("gross") and not limit:
        raise SystemExit(
            f"Grundgesamtheit '{name}' ist zu gross fuer eine einzelne Abfrage "
            f"(unter Q214609 haengen rund 936.000 Klassen) - der Query-Service "
            f"laeuft ins Timeout.\n"
            f"  Mit --limit N eine Stichprobe pruefen, z. B.\n"
            f"    python -m lauf struktur {name} --limit 500\n"
            f"  oder eine engere Grundgesamtheit waehlen (legierungen, oxide, "
            f"periodensystem, benannte-legierungen).")
    if info["pattern"] is None:
        items, ohne_item = hole_pruefliste(limit)
    else:
        items, ohne_item = hole_population_sparql(info["pattern"], limit), []
    print(f"{len(items)} Items in Grundgesamtheit '{name}' - "
          f"{info['beschreibung']}.", file=sys.stderr)
    if ohne_item:
        print(f"  {len(ohne_item)} Listeneintraege haben KEIN Wikidata-Item "
              f"(auch nicht ueber die Weiterleitung): {', '.join(ohne_item)}",
              file=sys.stderr)
    return items, ohne_item


# ---------------------------------------------------------------------------
# Den P279-Graphen holen
# ---------------------------------------------------------------------------

def hole_p279_huelle(start: list, abwaerts: bool = False,
                     max_runden: int = 30, block: int = 200) -> list:
    """Alle P279-Kanten ober- bzw. unterhalb von `start`, als (kind, elter).

    In Runden statt in einer Abfrage: ein einzelnes
    "?i wdt:P279* ?c . ?c wdt:P279 ?p" ueber tausend Startitems laeuft
    zuverlaessig in das 60s-Limit des Query-Service (gemessen: die Kanten
    unterhalb von Legierung sind mit 25s knapp drin, unterhalb von material
    nicht mehr). Rundenweise bleibt jede Abfrage klein, und der Fortschritt
    ist sichtbar.

    Nach oben ist die Huelle klein - ueber "material" hinaus geht es nur noch
    ueber wenige sehr allgemeine Klassen weiter, die Runden versiegen von
    selbst. Nach unten ist sie gross (unter Legierung haengen 3244 Klassen,
    weil der falsch modellierte Metalle-Zweig die Elemente mitbringt), aber
    endlich. max_runden ist die Reissleine gegen einen Zyklus, den der
    Besuchsspeicher nicht ohnehin abfaengt.
    """
    # Aufwaerts sind die abgefragten Knoten die Kinder, abwaerts die Eltern.
    von, nach = ("p", "c") if abwaerts else ("c", "p")
    richtung = "Unterklassen" if abwaerts else "Oberklassen"

    kanten, gesehen, offen = [], set(start), list(start)
    for runde in range(1, max_runden + 1):
        if not offen:
            break
        neu = set()
        for teil in in_bloecken(offen, block):
            for b in sparql(f"""SELECT ?c ?p WHERE {{
              VALUES ?{von} {{ {werte_klausel(teil)} }}
              ?c wdt:P279 ?p .
              FILTER(STRSTARTS(STR(?{nach}), "http://www.wikidata.org/entity/Q"))
            }}"""):
                kanten.append((qid_aus(b, "c"), qid_aus(b, "p")))
                weiter = qid_aus(b, nach)
                if weiter not in gesehen:
                    neu.add(weiter)
        print(f"  Runde {runde}: {len(offen)} Klassen abgefragt, "
              f"{len(neu)} neue {richtung}", file=sys.stderr)
        gesehen |= neu
        offen = sorted(neu)
    return kanten


def hole_p31_kanten(qids: list, block: int = 200) -> list:
    """(item, klasse)-Paare fuer P31 - fuer die Pruefung instanz-als-klasse."""
    kanten = []
    for teil in in_bloecken(qids, block):
        for b in sparql(f"""SELECT ?i ?c WHERE {{
          VALUES ?i {{ {werte_klausel(teil)} }}
          ?i wdt:P31 ?c .
          FILTER(STRSTARTS(STR(?c), "http://www.wikidata.org/entity/Q"))
        }}"""):
            kanten.append((qid_aus(b, "i"), qid_aus(b, "c")))
    return kanten


def hole_kinder(qids: list, block: int = 200) -> dict:
    """{qid: Anzahl direkter Unterklassen}. Nur die ZAHL wird gebraucht -
    fuer instanz-als-klasse zaehlt, DASS etwas darunter haengt."""
    kinder = {q: 0 for q in qids}
    for teil in in_bloecken(qids, block):
        for b in sparql(f"""SELECT ?p (COUNT(DISTINCT ?c) AS ?n) WHERE {{
          VALUES ?p {{ {werte_klausel(teil)} }}
          ?c wdt:P279 ?p .
        }} GROUP BY ?p"""):
            kinder[qid_aus(b, "p")] = int(b["n"]["value"])
    return kinder


def hole_labels(qids: list) -> dict:
    """{qid: Bezeichnung}, deutsch bevorzugt. Siehe wikidata_graph."""
    return hole_labels_api(qids, "de|en")


# ---------------------------------------------------------------------------
# Basismetall -> Legierungsklasse
# ---------------------------------------------------------------------------

def hole_ebenen_baum(wurzeln: list, tiefe: int, block: int = 100) -> dict:
    """{qid: {'label_de','label_en','desc_de','desc_en'}} bis Tiefe `tiefe`.

    Rueckgabe: (baum, qids der ersten Ebene). Die erste Ebene sind die DIREKT
    Eingehaengten - genau die, die pruefe_zu_allgemein untersucht. Sie faellt
    beim Aufbau ohnehin an; sie getrennt nachzuholen waere ein zweiter Satz
    Abfragen fuer Daten, die schon da sind.

    Ebenenweise mit VALUES-Bloecken, nicht am Stueck: "?i wdt:P279* ?wurzel"
    mit Labels und Beschreibungen laeuft unter material zuverlaessig in das
    60s-Limit des Query-Service. Siehe DEFAULT_TIEFE.
    """
    leer = {"label_de": "", "label_en": "", "desc_de": "", "desc_en": ""}
    baum, gesehen = {}, set(wurzeln)
    ebene = list(wurzeln)
    erste_ebene = set()

    for stufe in range(1, tiefe + 1):
        neu_auf_ebene = set()
        for teil in in_bloecken(ebene, block):
            for row in sparql(f"""SELECT ?item ?label ?desc WHERE {{
              VALUES ?parent {{ {werte_klausel(teil)} }}
              ?item wdt:P279 ?parent .
              OPTIONAL {{ ?item rdfs:label ?label .
                          FILTER(LANG(?label) IN ("de", "en")) }}
              OPTIONAL {{ ?item schema:description ?desc .
                          FILTER(LANG(?desc) IN ("de", "en")) }}
            }}"""):
                qid = qid_aus(row, "item")
                eintrag = baum.setdefault(qid, dict(leer))
                if qid not in gesehen:
                    neu_auf_ebene.add(qid)
                # Die Sprache haengt am Literal, nicht an der Projektion.
                for feld, praefix in (("label", "label"), ("desc", "desc")):
                    if feld in row:
                        lang = row[feld].get("xml:lang", "")
                        if lang in ("de", "en"):
                            eintrag[f"{praefix}_{lang}"] = row[feld]["value"]
        gesehen |= neu_auf_ebene
        if stufe == 1:
            erste_ebene = set(baum)
        print(f"  Ebene {stufe}: +{len(neu_auf_ebene)} Klassen "
              f"({len(baum)} insgesamt)", file=sys.stderr)
        if not neu_auf_ebene:
            break
        ebene = sorted(neu_auf_ebene)
    return baum, erste_ebene


def hole_elemente(qids: list, block: int = 200) -> set:
    """Die QIDs mit Ordnungszahl (P1086) - Elemente und ihre Isotope.

    Genau der Schnitt, den materialswiki seit jeher macht
    (LEGIERUNG_OHNE_ELEMENTE): weil Wikidata "Metall" faelschlich unter
    "Legierung" haengt, steht das halbe Periodensystem im Legierungsbaum.

    Als ZIEL einer Einordnung taugen sie nie: ein Werkstoff ist keine
    Unterklasse des Elements Kupfer. Ohne diesen Filter zielten 32 % der
    Heuristik-Vorschlaege auf copper, aluminium oder nickel (gemessen
    2026-08-23 an 118 Vorschlaegen).
    """
    elemente = set()
    for teil in in_bloecken(qids, block):
        for b in sparql(f"""SELECT ?i WHERE {{
          VALUES ?i {{ {werte_klausel(teil)} }}
          ?i wdt:P1086 ?ordnungszahl .
        }}"""):
            elemente.add(qid_aus(b, "i"))
    return elemente


def baue_suchbegriffe(baum: dict, elemente: set = frozenset()) -> list:
    """[(qid, bezeichnung, sprache, muster)] - der Kandidatenpool.

    Vorberechnet, weil der Pool fuer JEDES zu pruefende Item durchlaufen wird:
    ohne das wuerde jede Bezeichnung tausendfach neu kleingeschrieben und neu
    zu einem regulaeren Ausdruck uebersetzt.

    Gesucht wird auf WORTGRENZEN. Die rohe Substring-Suche der Vorlage fand
    "Mater" in "Material" und "compo" in "composite" - beides Zufall, beides
    ein Vorschlag, der eine bestehende Einordnung ersetzt haette.

    `elemente` fliegt raus - siehe hole_elemente.
    """
    begriffe = []
    for qid, eintrag in baum.items():
        if qid in ALLGEMEINE_WURZELN or qid in elemente:
            continue
        for lang in ("de", "en"):
            bez = (eintrag.get(f"label_{lang}") or "").strip()
            if len(bez) < MIN_LABEL_LEN:
                continue
            if bez.lower() in ALLGEMEINE_BEZEICHNUNGEN:
                continue
            begriffe.append((qid, bez, lang,
                             re.compile(r"\b" + re.escape(bez.lower()) + r"\b")))
    return begriffe


def pruefe_zu_allgemein(kandidaten: dict, begriffe: list, graph,
                        labels: dict, verdaechtige_ziele: set,
                        nur_name: bool = True) -> list:
    """Item haengt direkt unter einer sehr allgemeinen Klasse, obwohl seine
    Bezeichnung eine speziellere nennt.

    `kandidaten` sind die direkten Kinder der allgemeinen Wurzeln, mit Label
    und Beschreibung. Vorgeschlagen wird, die allgemeine Kante durch die
    speziellere zu ERSETZEN - also zwei Zeilen, und die erste entfernt etwas.
    Genau deshalb steht das Ganze in der heuristischen Stufe: bei einem
    Fehltreffer haengt das Item ersatzlos aus dem Baum.

    Uebersprungen wird, was das Item ohnehin schon erfuellt: fuehrt im
    Graphen bereits ein P279-Pfad zum Treffer, gibt es nichts vorzuschlagen.

    Ebenfalls uebersprungen: `verdaechtige_ziele`, also Klassen, die
    pruefe_verkehrt selbst beanstandet. Sonst schlaegt dieses Skript vor,
    ein Item unter eine Klasse zu haengen, deren Platz es zwei Stufen weiter
    oben in Frage stellt - beobachtet an "Orgelmetall", das von Legierung
    nach Metall (Q11426) umgehaengt werden sollte, ausgerechnet der Klasse
    mit der falsch modellierten Kante.
    """
    treffer = []
    for qid, eintrag in sorted(kandidaten.items()):
        name = " ".join(filter(None, (eintrag.get("label_de"),
                                      eintrag.get("label_en")))).lower()
        beschreibung = " ".join(filter(None, (eintrag.get("desc_de"),
                                              eintrag.get("desc_en")))).lower()
        anzeige = (eintrag.get("label_de") or eintrag.get("label_en")
                   or labels.get(qid, qid))

        gefunden = []
        for kand_qid, bez, lang, muster in begriffe:
            if kand_qid == qid or kand_qid in verdaechtige_ziele:
                continue
            im_namen = bool(muster.search(name))
            in_beschreibung = bool(muster.search(beschreibung))
            if not im_namen and (nur_name or not in_beschreibung):
                continue
            # Schon eingeordnet? Dann ist nichts zu tun.
            if qid in graph and kand_qid in graph:
                try:
                    if nx.has_path(graph, qid, kand_qid):
                        continue
                except nx.NodeNotFound:
                    pass
            gefunden.append((len(bez), kand_qid, bez,
                             "Name" if im_namen else "Beschreibung"))
        if not gefunden:
            continue

        # Laengster Treffer zuerst - er ist der spezifischste.
        gefunden.sort(reverse=True)
        _, ziel_qid, ziel_bez, beleg = gefunden[0]
        weitere = "; ".join(f"{q} ({b})" for _, q, b, _ in gefunden[1:4])

        for wurzel_qid, wurzel_name in ALLGEMEINE_WURZELN.items():
            if not (qid in graph and graph.has_edge(qid, wurzel_qid)):
                continue
            treffer.append(befund(
                "zu-allgemein", qid, anzeige,
                f"-{qid}\tP279\t{wurzel_qid}\n{qid}\tP279\t{ziel_qid}",
                f"haengt direkt unter {wurzel_qid} ({wurzel_name}), obwohl "
                f"{beleg.lower()} '{ziel_bez}' nennt - dafuer gibt es "
                f"{ziel_qid}."
                + (f" Weitere Treffer: {weitere}." if weitere else ""),
                "Heuristik auf Wortgrenzen. Erst pruefen, ob der Treffer "
                "sachlich passt - die erste Zeile ENTFERNT die bestehende "
                "Einordnung.",
                ziel_qid=ziel_qid, ziel_label=ziel_bez, kennzahl=beleg))
    # Nach ZIELKLASSE gruppiert ausgeben, nicht nach QID. Beim Durchsehen
    # stehen damit alle "-> bronze" beieinander: die Entscheidung faellt
    # einmal fuer die Gruppe statt zwoelfmal einzeln, und ein systematischer
    # Fehlgriff der Heuristik faellt als Block auf statt verstreut.
    return sorted(treffer, key=lambda t: (t["ziel_label"].lower(), t["label"]))


def hole_elementnamen() -> dict:
    """{bezeichnung in Kleinschreibung: kanonischer englischer Name} fuer die
    chemischen Elemente - inklusive Aliassen und Symbolen.

    Kanonisch ist die englische BEZEICHNUNG (rdfs:label), nicht der kuerzeste
    Alias. Das klingt nach einer Formalie, ist aber der Unterschied zwischen
    "copper" und "Cu": nur mit der Bezeichnung findet finde_basisklassen
    anschliessend die Klasse "copper-based alloy".

    Die Aliasse sind als SCHLUESSEL noetig, nicht als Wert: Wikidata fuehrt
    das Element als "aluminium", die Muenz-Items schreiben "Aluminum", und
    manche Zusammensetzung nennt nur das Symbol. Ohne die Aliasse faellt
    jede dieser Schreibweisen durch.

    Geholt statt gepflegt: eine handgeschriebene Elementliste im Quelltext
    waere eine zweite Wahrheit neben Wikidata, und dieses Skript soll gegen
    Wikidata pruefen, nicht gegen eine Kopie davon.
    """
    namen = {}
    for b in sparql("""SELECT ?label ?name WHERE {
      ?e wdt:P31 wd:Q11344 ; wdt:P1086 ?z .
      FILTER(?z <= 118)
      ?e rdfs:label ?label .
      FILTER(LANG(?label) = "en")
      { ?e rdfs:label ?name . FILTER(LANG(?name) IN ("en", "de")) }
      UNION
      { ?e skos:altLabel ?name . FILTER(LANG(?name) IN ("en", "de")) }
    }"""):
        kanonisch = b["label"]["value"].strip()
        schluessel = b["name"]["value"].strip().lower()
        # Erster Treffer gewinnt: ein Alias, den sich zwei Elemente teilen,
        # waere ohnehin nicht eindeutig aufloesbar.
        namen.setdefault(schluessel, kanonisch)
    return namen


def lies_zusammensetzung(text: str, elementnamen: dict) -> tuple:
    """([(anteil, element)], [nicht erkannte Bestandteile]).

    Erkennt beide Schreibweisen (siehe ZUSAMMENSETZUNG_MUSTER) und wirft
    weg, was kein chemisches Element ist - "27.5% Steel" und "Other Metals
    2%" kommen in den Daten vor und sind als Basismetall unbrauchbar.
    Sie gehen nicht verloren, sondern in die zweite Rueckgabe: dass ein
    Bestandteil nicht zugeordnet werden konnte, gehoert in die Begruendung.
    """
    gefunden, unbekannt = {}, []
    for i, muster in enumerate(ZUSAMMENSETZUNG_MUSTER):
        for a, b in muster.findall(text):
            anteil_roh, name = (a, b) if i == 0 else (b, a)
            name = name.strip().strip("-").lower()
            try:
                anteil = float(anteil_roh.replace(",", "."))
            except ValueError:
                continue
            element = elementnamen.get(name)
            if element is None:
                if name not in unbekannt and len(name) > 2:
                    unbekannt.append(name)
                continue
            # Dasselbe Element kann in beiden Mustern anschlagen; der
            # groessere Fund gewinnt, doppelt gezaehlt wird nichts.
            gefunden[element] = max(gefunden.get(element, 0.0), anteil)
    anteile = sorted(((a, e) for e, a in gefunden.items()), reverse=True)
    return anteile, unbekannt


def pruefe_zusammensetzung(kandidaten: dict, elementnamen: dict,
                           basisklassen: dict, graph, labels: dict) -> list:
    """Basismetall aus der Zusammensetzung im Namen ableiten.

    "Nickel brass (70% Copper, 18% Zinc, 12% Nickel)" ist eine
    Kupferlegierung - das Element mit dem groessten Anteil ist definitionsgemaess
    das Basismetall. Diese Auswertung raet nicht, sie rechnet; sie ist die
    belastbarste Namensauswertung im Skript.

    Drei Faelle bekommen trotzdem KEINEN Vorschlag:

      * "Plating: ..." - die Prozente gelten nur der Auflage. "Brass plated
        steel (Plating: 72.5% Copper, 27.5% Zinc)" ist Stahl mit
        Messingauflage, kein Kupferwerkstoff.
      * Kein klarer Sieger (siehe MIN_ABSTAND_PROZENT). Bei "48% Copper,
        52% Aluminium" entscheidet die Zuordnung eine Nachkommastelle.
      * Kein Legierungsklasse fuer das Basismetall in Wikidata - dann ist
        nichts vorzuschlagen, nur zu melden.

    Ein vierter Fall bekommt einen Vorschlag MIT Warnung: Schichtverbunde
    ("clad", "plated"). Die Prozente stimmen dort fuer den Koerper, aber ein
    Verbund ist keine Legierung.
    """
    treffer = []
    for qid, eintrag in sorted(kandidaten.items()):
        anzeige = (eintrag.get("label_de") or eintrag.get("label_en")
                   or labels.get(qid, qid))
        text = " ".join(filter(None, (eintrag.get("label_de"),
                                      eintrag.get("label_en"))))
        if "%" not in text:
            continue

        klein = text.lower()
        if any(m in klein for m in AUFLAGE_MARKER):
            treffer.append(befund(
                "zusammensetzung", qid, anzeige, "",
                f"Der Name nennt eine Zusammensetzung, aber als 'Plating' - "
                f"die Prozente gelten der AUFLAGE, nicht dem Item.",
                "Kein Vorschlag: das Basismetall der Auflage sagt nichts "
                "ueber die Klasse des Werkstoffs. Von Hand entscheiden.",
                eigenschaft="P279", kennzahl="Auflage"))
            continue

        anteile, unbekannt = lies_zusammensetzung(text, elementnamen)
        if not anteile:
            continue

        zerlegung = ", ".join(f"{a:g}% {e}" for a, e in anteile)
        rest = (f" Nicht zugeordnet: {', '.join(unbekannt)}."
                if unbekannt else "")
        spitze, basis = anteile[0]
        zweiter = anteile[1][0] if len(anteile) > 1 else 0.0

        if spitze - zweiter < MIN_ABSTAND_PROZENT:
            treffer.append(befund(
                "zusammensetzung", qid, anzeige, "",
                f"Zusammensetzung {zerlegung}.{rest} Kein klares Basismetall: "
                f"{basis} fuehrt nur mit {spitze - zweiter:g} Prozentpunkten.",
                f"Kein Vorschlag - unter {MIN_ABSTAND_PROZENT:g} "
                f"Prozentpunkten Abstand entscheidet eine Nachkommastelle.",
                eigenschaft="P279",
                kennzahl=f"{spitze:g}:{zweiter:g}"))
            continue

        eintrag_klasse = basisklassen.get(basis.capitalize()) or \
            basisklassen.get(basis)
        if not eintrag_klasse:
            treffer.append(befund(
                "zusammensetzung", qid, anzeige, "",
                f"Zusammensetzung {zerlegung}.{rest} Basismetall {basis} "
                f"({spitze:g}%), aber dafuer gibt es in Wikidata keine "
                f"Legierungsklasse.",
                "Kein Vorschlag moeglich - die Klasse muesste erst angelegt "
                "werden, und das tut dieses Werkzeug nicht.",
                eigenschaft="P279", kennzahl=f"{spitze:g}%"))
            continue

        ziel_qid, ziel_label = eintrag_klasse
        if qid in graph and ziel_qid in graph:
            try:
                if nx.has_path(graph, qid, ziel_qid):
                    continue  # laengst eingeordnet
            except nx.NodeNotFound:
                pass

        verbund = [m for m in VERBUND_MARKER if m in klein]
        warnung = ""
        if verbund:
            warnung = (f" ACHTUNG: '{verbund[0]}' im Namen - das Item ist "
                       f"vermutlich ein Schichtverbund, keine Legierung. "
                       f"Dann trifft die Zuordnung nicht zu.")

        quickstatements = f"{qid}\tP279\t{ziel_qid}"
        # Die allgemeine Kante nur entfernen, wenn es sie ueberhaupt gibt.
        for wurzel_qid in ALLGEMEINE_WURZELN:
            if qid in graph and graph.has_edge(qid, wurzel_qid):
                quickstatements = (f"-{qid}\tP279\t{wurzel_qid}\n"
                                   + quickstatements)
                break

        treffer.append(befund(
            "zusammensetzung", qid, anzeige, quickstatements,
            f"Zusammensetzung {zerlegung}.{rest} Basismetall ist {basis} mit "
            f"{spitze:g}%, also {ziel_qid} ({ziel_label}).",
            ("Gerechnet, nicht geraten - der Anteil steht im Namen." + warnung
             if not verbund else warnung.strip()),
            ziel_qid=ziel_qid, ziel_label=ziel_label,
            kennzahl=f"{spitze:g}%"))
    return treffer


def pruefe_p31_neben_p279(p31_kanten: list, kinder: dict, direkt_allgemein: set,
                          labels: dict) -> list:
    """Item haengt direkt unter einer allgemeinen Klasse UND hat P31.

    Die Vorlage (material_subclass_check.py, "Fall B") schloss daraus auf ein
    physisches Einzelobjekt und empfahl P186 statt P279. Diese Praemisse
    haelt nicht: die tatsaechlichen P31-Werte sind ganz ueberwiegend
    KLASSENmarkierungen - "type of material" (6x), "class of chemical
    substances by use" (4x), "Stoffgruppe" (3x), "Produktkategorie" (2x),
    gemessen an 68 Items am 2026-08-23. Das sind keine Einzelobjekte.

    Deshalb hier nur noch Meldung, kein Entwurf. Wer P31 UND Unterklassen
    hat, wird ohnehin von pruefe_instanz_als_klasse erfasst - das ist der
    Teil des Gedankens, der strukturell traegt.
    """
    nach_item = {}
    for item, klasse in p31_kanten:
        if item in direkt_allgemein and not kinder.get(item):
            nach_item.setdefault(item, []).append(klasse)

    return [befund(
        "p31-neben-p279", qid, labels.get(qid, qid), "",
        "haengt direkt unter einer allgemeinen Klasse und hat zusaetzlich "
        "P31 auf: " + ", ".join(f"{k} ({labels.get(k, k)})" for k in werte[:4]),
        "Nur zur Kenntnis. Ist der P31-Wert eine Klassenmarkierung (type of "
        "material, Stoffgruppe), ist alles in Ordnung. Meint er ein "
        "Einzelobjekt, gehoert das Material ueber P186 daran - das laesst "
        "sich hier nicht entscheiden.",
        eigenschaft="P31", kennzahl=len(werte))
        for qid, werte in sorted(nach_item.items())]


def finde_basisklassen(basen: list) -> tuple:
    """({Basismetall: (qid, label)}, {Basismetall: Grund fuer die Luecke}).

    Gesucht wird ueber die englische Bezeichnung nach KLASSEN_MUSTER, und es
    zaehlt nur, was selbst unter Q37756 haengt. Diese Bedingung ist der Kern
    der Pruefung: sonst faende "silicon bronze" oder ein gleichnamiges
    Handelsprodukt genauso wie eine echte Werkstoffklasse.
    """
    kandidaten = {}   # Bezeichnung -> Basismetall
    for basis in basen:
        wort = SCHREIBWEISEN.get(basis, basis).lower()
        for muster in KLASSEN_MUSTER:
            kandidaten[muster.format(b=wort)] = basis

    gefunden = {}
    namen = list(kandidaten)
    for i in range(0, len(namen), 100):
        werte = " ".join(f'"{n}"@en' for n in namen[i:i + 100])
        for b in sparql(f"""SELECT ?c ?l WHERE {{
          VALUES ?l {{ {werte} }}
          ?c rdfs:label ?l .
          ?c wdt:P279* wd:{LEGIERUNG_QID} .
        }}"""):
            basis = kandidaten[b["l"]["value"]]
            # Erster Treffer gewinnt - KLASSEN_MUSTER steht nach Haeufigkeit
            # der Wikidata-Schreibweise sortiert.
            gefunden.setdefault(basis, (qid_aus(b, "c"), b["l"]["value"]))

    for basis, eintrag in BASISKLASSEN_FEST.items():
        if basis in basen:
            gefunden[basis] = eintrag

    luecken = {}
    for basis in basen:
        if basis in gefunden:
            continue
        luecken[basis] = BASISKLASSEN_BEKANNTE_LUECKE.get(
            basis, "keine Klasse '<Basismetall> alloy' unter Q37756 gefunden")
    return gefunden, luecken


# ---------------------------------------------------------------------------
# Die Pruefungen
# ---------------------------------------------------------------------------

# Aus einer QuickStatements-Zeile die Eigenschaft herauslesen. Das Format
# ist durchgaengig '[-]QID<TAB>Pnnn<TAB>Wert'.
_QS_EIGENSCHAFT = re.compile(r"\t(P\d+)\t")


def eigenschaft_aus(quickstatements: str) -> str:
    """Die Eigenschaften eines Entwurfs, in der Reihenfolge der Zeilen.

    Zweizeilige Entwuerfe beruehren zwei Eigenschaften ('P31 -> P279'
    ersetzt die eine durch die andere); die werden zu EINEM Schluessel
    zusammengezogen, damit sie in der Ausgabe zusammenbleiben. Ein Entwurf,
    der P31 loescht und P279 setzt, gehoert weder unter das eine noch unter
    das andere allein.
    """
    gesehen = []
    for pid in _QS_EIGENSCHAFT.findall(quickstatements or ""):
        if pid not in gesehen:
            gesehen.append(pid)
    return " -> ".join(gesehen)


def befund(art: str, qid: str, label: str, quickstatements: str,
           begruendung: str, entscheidung: str, **extra) -> dict:
    """Ein Befund. `quickstatements` leer heisst: hier gibt es nichts zu
    entwerfen, der Befund ist reine Meldung.

    `eigenschaft` ist der Sortierschluessel der Ausgabe. Wo ein Entwurf
    dasteht, wird sie aus ihm gelesen - eine zweite, von Hand gepflegte
    Angabe koennte davon abweichen. Nur die reinen Meldungen muessen sie
    mitgeben; dort gibt es keinen Entwurf, aus dem sie folgen wuerde."""
    return {"befund": art, "qid": qid, "label": label,
            "quickstatements": quickstatements, "begruendung": begruendung,
            "entscheidung": entscheidung,
            "eigenschaft": (eigenschaft_aus(quickstatements)
                            or extra.get("eigenschaft", "")),
            "ziel_qid": extra.get("ziel_qid", ""),
            "ziel_label": extra.get("ziel_label", ""),
            "kennzahl": extra.get("kennzahl", "")}


def pruefe_zyklen(graph, im_bereich: set, labels: dict,
                  max_zyklen: int = 50) -> list:
    """P279-Zyklen: eine Klasse ist ueber P279 ihre eigene Oberklasse.

    Immer ein Fehler, aber nie automatisch aufloesbar: der Zyklus sagt, DASS
    eine Kante der Kette falsch ist, nicht WELCHE. Deshalb nur Meldung.

    Lokal gerechnet statt per SPARQL - eine transitive Selbstreferenz
    ("?a wdt:P279+ ?b . ?b wdt:P279+ ?a") ist fuer den Query-Service teuer,
    fuer networkx auf dem bereits geholten Graphen fast umsonst.

    Auf die Werkstoff-Ecke begrenzt, aus demselben Grund wie bei
    pruefe_redundant: die Huelle nach oben endet in der Oberontologie, und
    ein Zyklus zwischen "Kunstgewerbe" und "angewandte Kunst" ist zwar ein
    echter Fehler, aber keiner, den dieses Projekt zu reparieren hat.
    """
    treffer = []
    for i, zyklus in enumerate(
            z for z in nx.simple_cycles(graph) if im_bereich.issuperset(z)):
        if i >= max_zyklen:
            break
        kette = " -> ".join(f"{q} ({labels.get(q, q)})"
                            for q in zyklus + [zyklus[0]])
        treffer.append(befund(
            "zyklus", zyklus[0], labels.get(zyklus[0], zyklus[0]), "",
            f"P279-Zyklus ueber {len(zyklus)} Klassen: {kette}",
            "Welche Kante der Kette falsch ist, entscheidet die Fachlichkeit "
            "- hier wird nichts vorgeschlagen.",
            eigenschaft="P279", kennzahl=len(zyklus)))
    return treffer


def pruefe_redundant(graph, im_bereich: set, verdaechtig: set, labels: dict,
                     max_umweg: int = 4) -> list:
    """Kante n -> p, obwohl n ueber einen anderen Elter ohnehin bei p landet.

    Die einzige Pruefung mit einspielbarem Vorschlag, und zwar aus einem
    Grund: sie behauptet nichts. Entfernt wird eine Kante, die keine
    Information traegt - nach dem Entfernen ist n weiterhin Unterklasse von
    p, nur eben abgeleitet statt doppelt notiert. Das ist gaengige
    Wikidata-Praxis (Redundanz macht Baeume unlesbar und Constraint-Berichte
    laut), und es ist reversibel.

    `max_umweg` begrenzt die Laenge des Ersatzpfades. Ein Umweg ueber zehn
    Klassen ist zwar formal derselbe Befund, laesst sich aber nicht mehr in
    einer Zeile pruefen - und was nicht pruefbar ist, gehoert nicht in den
    einspielbaren Abschnitt.

    `im_bereich` begrenzt auf die Werkstoff-Ecke. Die Huelle nach oben endet
    zwangslaeufig in der obersten Ontologie, und dort findet dieselbe Pruefung
    dieselben Redundanzen bei "Begriff", "Typ", "Ereignis" oder
    "Kunstgewerbe". Die Befunde sind richtig, gehen dieses Projekt aber
    nichts an: wer Werkstoffe pflegt, hat keinen Anlass, an der
    Oberontologie zu schrauben, und eine dort eingespielte Aenderung trifft
    hunderttausende Items.

    `verdaechtig` sind die Kanten, die pruefe_verkehrt beanstandet - und sie
    sind der Grund, warum diese Pruefung nicht so harmlos ist, wie sie
    aussieht. Die Redundanz gilt nur, solange der ERSATZPFAD haelt. Genau das
    ist hier oft nicht der Fall: "Ferrolegierung P279 Legierung" sieht
    redundant aus, weil es ueber ferrous metal -> Metalle -> Legierung auch
    so geht - aber der letzte Schritt ist die falsch modellierte Kante. Wer
    die direkte Kante entfernt und spaeter die falsche repariert, hat
    Ferrolegierung aus dem Legierungsbaum geworfen.

    Solche Befunde bekommen die Art 'redundant-unsicher' und landen damit im
    auskommentierten Teil. Erst die falsche Kante klaeren, dann diese hier.
    """
    treffer = []
    for n in graph.nodes:
        if n not in im_bereich:
            continue
        eltern = list(graph.successors(n))
        if len(eltern) < 2:
            continue
        for p in eltern:
            # Alle Ersatzpfade sammeln: n -> (anderer Elter) -> ... -> p.
            # Die direkte Kante bleibt dabei aussen vor, sonst ist jeder Pfad
            # trivial. Gesammelt statt beim ersten Treffer abgebrochen, weil
            # ein SAUBERER Ersatzpfad einen verdaechtigen schlaegt - und der
            # kann der zweite sein.
            pfade = []
            for q in eltern:
                if q == p or q == n:
                    continue
                try:
                    pfad = nx.shortest_path(graph, q, p)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                if len(pfad) > max_umweg:   # len(pfad) = Kanten ab n
                    continue
                voll = [n] + pfad
                kaputt = [(a, b) for a, b in zip(voll, voll[1:])
                          if (a, b) in verdaechtig]
                pfade.append((bool(kaputt), voll, kaputt))
            if not pfade:
                continue
            # False < True: der ungefaehrdete Pfad gewinnt, danach der kuerzere.
            unsicher, voll, kaputt = min(pfade, key=lambda t: (t[0], len(t[1])))

            kette = " -> ".join(f"{x} ({labels.get(x, x)})" for x in voll)
            q = voll[1]
            grund = (f"{n} hat P279 auf {p} ({labels.get(p, p)}) UND auf "
                     f"{q} ({labels.get(q, q)}); ueber {q} ist {p} ohnehin "
                     f"erreichbar: {kette}")
            if unsicher:
                a, b = kaputt[0]
                treffer.append(befund(
                    "redundant-unsicher", n, labels.get(n, n),
                    f"-{n}\tP279\t{p}", grund,
                    f"NICHT einspielen, solange {a} ({labels.get(a, a)}) -> "
                    f"{b} ({labels.get(b, b)}) ungeklaert ist: der Ersatzpfad "
                    f"laeuft ueber diese beanstandete Kante. Faellt sie, "
                    f"faellt auch die Einordnung von {n}.",
                    ziel_qid=p, ziel_label=labels.get(p, p),
                    kennzahl=len(voll) - 1))
            else:
                treffer.append(befund(
                    "redundant", n, labels.get(n, n),
                    f"-{n}\tP279\t{p}", grund,
                    "Entfernen aendert nichts an der abgeleiteten "
                    "Klassenzugehoerigkeit - nur die doppelte Notation faellt weg.",
                    ziel_qid=p, ziel_label=labels.get(p, p),
                    kennzahl=len(voll) - 1))
    return treffer


def verkehrt_kandidaten(graph, im_bereich: set,
                        min_unterbau: int = 25) -> list:
    """[(n, p, |unter n|, |eigener Unterbau von p|)] - Kandidaten fuer eine
    verkehrte Kante.

    Die Messgroesse: die naive Fassung "Unterbau von n groesser als Unterbau
    von p" kann nie ausschlagen, denn die Kante n -> p macht alles unter n
    automatisch auch zu etwas unter p. Gemessen wird deshalb der EIGENE
    Unterbau von p, also ohne den Teil, den p nur ueber n hat. Traegt n mehr
    als p selbst, dann haengt die weite Klasse unter der engen.

    Bei Metall (Q11426) unter Legierung (Q37756) faellt das drastisch aus:
    ohne den Metalle-Zweig bleibt Legierung kaum eigener Unterbau, waehrend
    unter Metall die Elemente samt Isotopen haengen. materialswiki gleicht das
    seit jeher mit einem Filter aus (LEGIERUNG_OHNE_ELEMENTE) - die Kante
    selbst bleibt falsch.

    Zwei Bedingungen halten das Ergebnis brauchbar, beide notwendig:

    `im_bereich` sind die Klassen der ABWAERTS vollstaendig geholten Huelle
    unter der Bereichswurzel. Nur fuer sie stimmt die lokal gezaehlte
    Unterbaugroesse mit der echten ueberein - fuer alles darueber zaehlt der
    Graph nur, was zufaellig mitgeholt wurde. Ohne diese Einschraenkung
    besteht das Ergebnis fast ausschliesslich aus der oberen Ontologie
    (Entitaet, Objekt, Materie, Substanz ...), wo die Zahlen ein Artefakt
    der Abfrage sind und keine Aussage.

    `min_unterbau` haelt das Rauschen darunter draussen: bei zwei Klassen mit
    je drei Unterklassen sagt der Vergleich nichts.
    """
    unterbau = {n: nx.ancestors(graph, n) for n in im_bereich if n in graph}
    treffer = []
    for n, p in graph.edges:
        if n not in unterbau or p not in unterbau:
            continue
        unter_n = unterbau[n]
        if len(unter_n) < min_unterbau:
            continue
        eigen_p = unterbau[p] - unter_n - {n}
        if len(unter_n) <= len(eigen_p):
            continue
        treffer.append((n, p, len(unter_n), len(eigen_p)))
    return sorted(treffer, key=lambda t: -t[2])


def pruefe_verkehrt(kandidaten: list, labels: dict) -> list:
    return [befund(
        "verkehrt", n, labels.get(n, n),
        f"-{n}\tP279\t{p}",
        f"Unter {n} ({labels.get(n, n)}) haengen {gross} Klassen, unter "
        f"{p} ({labels.get(p, p)}) ohne diesen Zweig nur {klein}. Die "
        f"weitere Klasse haengt unter der engeren.",
        "Verdacht auf verkehrte Kante. Ob sie zu entfernen oder umzudrehen "
        "ist, ist eine fachliche Entscheidung.",
        ziel_qid=p, ziel_label=labels.get(p, p),
        kennzahl=f"{gross}:{klein}")
        for n, p, gross, klein in kandidaten]


def pruefe_instanz_als_klasse(p31_kanten: list, kinder: dict, im_baum: set,
                              labels: dict) -> list:
    """Item mit P31 auf eine Werkstoffklasse, das SELBST Unterklassen hat.

    Wer Unterklassen hat, ist eine Klasse - und Klassen haengen in Wikidata
    mit P279 ineinander, nicht mit P31. Der Entwurf dreht beides um (P31 weg,
    P279 hin), bleibt aber auskommentiert: es gibt Items, die zu Recht beides
    sind (eine Norm-Legierung kann Instanz eines Normwerks und zugleich
    Oberklasse ihrer Varianten sein).
    """
    treffer = []
    for item, klasse in p31_kanten:
        if klasse not in im_baum or not kinder.get(item):
            continue
        treffer.append(befund(
            "instanz-als-klasse", item, labels.get(item, item),
            f"-{item}\tP31\t{klasse}\n{item}\tP279\t{klasse}",
            f"{item} ist P31 von {klasse} ({labels.get(klasse, klasse)}), hat "
            f"aber selbst {kinder[item]} Unterklassen - wer Unterklassen hat, "
            f"ist eine Klasse.",
            "P31 -> P279 umstellen, wenn das Item wirklich nur Klasse ist. "
            "Beides zugleich ist moeglich und dann kein Fehler.",
            ziel_qid=klasse, ziel_label=labels.get(klasse, klasse),
            kennzahl=kinder[item]))
    return treffer


def legierungs_items(graph, qids: list, p31_kanten: list) -> set:
    """Welche der Items sind Legierungen - ohne den Umweg ueber "Metall"?

    Gefragt ist nicht bloss, ob das Item irgendwie unter Q37756 haengt: das
    tut wegen Q11426 (siehe METALL_QID) jeder Sammelbegriff fuer Metalle. Der
    Knoten wird deshalb aus dem Graphen genommen und der Rest des
    Klassenwegs darauf durchlaufen. Ein simples "hat gar keinen Metall-Weg"
    reicht nicht: Stahl hat einen, kommt aber ausserdem ueber Ferrolegierung
    an die Legierung heran und ist selbstverstaendlich eine.

    P31 zaehlt als erster Schritt mit ("X ist ein/e Aluminiumlegierung") -
    genauso wie bei `eingeordnet` in main().
    """
    if LEGIERUNG_QID not in graph:
        return set()
    ohne_metall = graph.copy()
    if METALL_QID in ohne_metall:
        ohne_metall.remove_node(METALL_QID)
    erreichbar = nx.ancestors(ohne_metall, LEGIERUNG_QID)
    menge = set(qids)
    treffer = {q for q in menge if q in erreichbar}
    treffer |= {i for i, k in p31_kanten
                if i in menge and (k in erreichbar or k == LEGIERUNG_QID)}
    # Q11426 selbst haengt NUR ueber die defekte Kante unter der Legierung.
    # Ohne diesen Sonderfall bekaeme ausgerechnet es die Gemisch-Metaklasse.
    return treffer - {METALL_QID, LEGIERUNG_QID}


def pruefe_metaklasse(items: dict, legierungen: set, p31_kanten: list,
                      ist_klasse: set, labels: dict,
                      auch_mit_p31: bool = False) -> list:
    """P31-Vorschlag: die Gemisch-Metaklasse fuer eine Legierung.

    Vorgeschlagen wird NUR die Metaklasse, nie eine inhaltliche Einordnung
    ("Kupferlegierung", "Werkzeugstahl") - die ist eine fachliche
    Entscheidung und faellt in die Pruefungen 'ohne-einordnung' und
    'zusammensetzung'.

    KEIN P31 an eine Werkstoffklasse. `ist_klasse` sind die Items, die nach
    [[Help:Basic membership properties]] Klassen sind: sie haben P279 oder
    Unterklassen. Fuer sie entsteht nur die Meldung 'metaklasse-klasse',
    kein Entwurf.

    Die Chemie-Guideline will die Metaklasse formal auch dort - eine Klasse
    darf Instanz einer Metaklasse sein, das ist der Zweck einer Metaklasse.
    Aber der Graph belegt an einem solchen Item nur, dass es IRGENDWO unter
    Q37756 haengt, und genau das ist an dieser Grundgesamtheit die schwache
    Stelle: ueber die schiefe Metall-Kante haengen dort Stahlrohre,
    Markenzeichen und Sammelbegriffe wie "Platinmetalle". Ein P31 sagt
    "dieses Ding IST ein definiertes Gemisch chemischer Substanzen" - eine
    Aussage ueber die Natur des Items, die aus einer P279-Kette nicht folgt.
    Bei einer Fehleinordnung faellt ein falsches P279 als schiefe Kante auf;
    ein falsches P31 auf eine Metaklasse liest niemand mehr nach.

    Bleibt der Fall, in dem entworfen wird: das Item hat weder P279 noch
    Unterklassen, ist also nach derselben Regel keine Klasse, sondern eine
    Instanz - und an eine Instanz gehoert P31.

    Das hat eine Folge, die man kennen muss: in die Menge `legierungen`
    kommt ein Item nur ueber P279 ODER ueber P31 (siehe legierungs_items).
    Wer keine Klasse ist, kam also ueber P31 herein und TRAEGT damit schon
    eines. Ohne --metaklasse-auch-mit-p31 entsteht hier deshalb kein
    Entwurf mehr, sondern nur noch die Meldung. Der Schalter entwirft dann
    genau an den Instanzen - dort, wo P31 hingehoert.

    Standardmaessig nur an Items, die GAR KEIN P31 tragen. Wo schon eines
    steht, ist es in aller Regel eine richtige Klassenzugehoerigkeit
    ("P31 = Legierung"), und die Metaklasse waere eine ZWEITE P31-Aussage
    daneben - fuer die spricht die Guideline, aber es ist eine
    Massenaenderung. Mit --metaklasse-auch-mit-p31 kommen sie dazu; die
    Zahlen stehen im README.

    Traegt das Item bereits eine ANDERE Chemie-Metaklasse, wird nichts
    entworfen, sondern gemeldet: die Guideline laesst nur eine zu, und die
    falsche zu entfernen ist nichts, was dieses Werkzeug nebenbei tut.
    """
    p31 = {}
    for item, klasse in p31_kanten:
        p31.setdefault(item, []).append(klasse)

    treffer, schon_da, ausgelassen, klassen = [], 0, 0, 0
    for qid in sorted(items):
        if qid not in legierungen:
            continue
        werte = p31.get(qid, [])
        if MINERALART_QID in werte:
            continue
        name = labels.get(qid, items[qid].get("label", qid))

        vorhanden = [k for k in werte if k in CHEMIE_METAKLASSEN]
        if GEMISCH_METAKLASSE in vorhanden:
            schon_da += 1
            continue
        if vorhanden:
            namen = ", ".join(f"{k} ({CHEMIE_METAKLASSEN[k]})"
                              for k in vorhanden)
            treffer.append(befund(
                "metaklasse-konflikt", qid, name, "",
                f"traegt bereits die Chemie-Metaklasse {namen}. Fuer ein "
                f"Gemisch ist {GEMISCH_METAKLASSE} "
                f"({CHEMIE_METAKLASSEN[GEMISCH_METAKLASSE]}) vorgesehen, und "
                f"die Guideline laesst nur EINE zu - die bestehende muesste "
                f"also weichen.",
                "Von Hand entscheiden. Entfernt wird hier nichts: die "
                "bestehende Metaklasse kann auch heissen, dass das Item gar "
                "keine Legierung ist.",
                eigenschaft="P31"))
            continue
        if werte and not auch_mit_p31:
            ausgelassen += 1
            continue

        fehlt = (f"ist ueber P279/P31 als Legierung eingeordnet (Q37756, "
                 f"'mixture or metallic solid solution'), traegt aber keine "
                 f"Chemie-Metaklasse. Fuer Gemische verlangt die Guideline "
                 f"{GEMISCH_METAKLASSE} "
                 f"({CHEMIE_METAKLASSEN[GEMISCH_METAKLASSE]}).")

        # Klasse: nur Meldung. Der Grund steht im Docstring - ein P31 waere
        # hier eine Aussage ueber die Natur des Items, die der Graph nicht
        # hergibt.
        if qid in ist_klasse:
            klassen += 1
            treffer.append(befund(
                "metaklasse-klasse", qid, name, "",
                fehlt + " Das Item ist aber selbst eine KLASSE (es hat P279 "
                        "oder Unterklassen) - an eine Werkstoffklasse "
                        "schreibt dieses Werkzeug kein P31.",
                "Von Hand entscheiden. Formal will die Guideline die "
                "Metaklasse auch an Klassen; hier steht sie nur als Meldung, "
                "weil in dieser Menge ueber die schiefe Metall-Kante auch "
                "Rohre, Markenzeichen und Sammelbegriffe liegen, und ein "
                "falsches P31 auf eine Metaklasse faellt spaeter niemandem "
                "mehr auf.",
                eigenschaft="P31", ziel_qid=GEMISCH_METAKLASSE,
                ziel_label=CHEMIE_METAKLASSEN[GEMISCH_METAKLASSE]))
            continue

        treffer.append(befund(
            "metaklasse", qid, name,
            f"{qid}\tP31\t{GEMISCH_METAKLASSE}",
            fehlt + " Das Item hat weder P279 noch Unterklassen, ist also "
                    "keine Klasse, sondern eine Instanz - dort gehoert P31 "
                    "hin."
            + (f" Achtung: das Item traegt bereits P31 auf "
               f"{', '.join(werte)} - die Metaklasse kaeme als ZWEITE "
               f"P31-Aussage daneben." if werte else ""),
            "Ist das Item wirklich ein Werkstoff? In dieser Menge stecken "
            "Rohre, Markenzeichen und Sammelbegriffe, die nur ueber die "
            "schiefe Metall-Kante hier landen.",
            ziel_qid=GEMISCH_METAKLASSE,
            ziel_label=CHEMIE_METAKLASSEN[GEMISCH_METAKLASSE]))

    if schon_da or ausgelassen or klassen:
        print(f"  Metaklasse: {schon_da} Items tragen sie bereits"
              + (f", {klassen} sind selbst Klassen (nur Meldung, kein P31)"
                 if klassen else "")
              + (f", {ausgelassen} mit bestehendem P31 ausgelassen "
                 f"(--metaklasse-auch-mit-p31 nimmt sie dazu)"
                 if ausgelassen else ""), file=sys.stderr)
    return treffer


def pruefe_ohne_einordnung(items: dict, eingeordnet: set, labels: dict,
                           ist_klasse: set, hat_p31: dict) -> list:
    """Benannte Legierung ohne jeden Pfad zu "Legierung" (Q37756).

    Nur fuer die Pruefliste sinnvoll: dort steht durch die HERKUNFT fest,
    dass es sich um eine Legierung handeln soll. In den SPARQL-Gruppen ist
    die Klassifikation per Definition schon erfuellt.

    Wo es fuer das Basismetall eine Klasse gibt, wird sie vorgeschlagen -
    aber auskommentiert, denn die Projektseite verlangt eine differenzierte
    Einhaengung (Ferrous alloy, Alloy steel, ...), und "Nickel" sagt nicht,
    ob etwas Superlegierung, Lotlegierung oder Widerstandslegierung ist. Der
    Vorschlag ist also die GROBE, sichere Einordnung - die feine bleibt
    Handarbeit.

    KEIN P279 an eine Instanz. Diese Grundgesamtheit kommt aus einer
    Wikipedia-Liste, nicht aus dem Klassenbaum - was hier steht, muss
    ueberhaupt keine Klasse sein. [[Help:Basic membership properties]]:
    "both subject and value are classes". Drei Faelle:

      * Item hat P279 oder Unterklassen -> Klasse, Entwurf wie bisher.
      * Item hat NUR P31 -> als Instanz modelliert. Ein P279 widerspraeche
        dem, und ein P31 auf die Werkstoffklasse schreibt dieses Werkzeug
        nicht (siehe pruefe_metaklasse). Also nur Meldung.
      * Item hat weder noch -> der Graph sagt nichts. Entwurf ja, aber mit
        ausdruecklichem Hinweis, dass die Klasseneigenschaft ungeprueft ist.

    Und ein Teil der Meldungen ist zu Recht keine Legierung: Titannitrid,
    Titancarbid und Uranhydrid sind Verbindungen. Auch das entscheidet hier
    niemand automatisch.
    """
    basen = sorted({e["basis"] for e in items.values()
                    if e["qid"] not in eingeordnet and e.get("basis")})
    klassen, luecken = finde_basisklassen(basen) if basen else ({}, {})

    treffer = []
    for eintrag in items.values():
        qid = eintrag["qid"]
        if qid in eingeordnet:
            continue
        basis = eintrag.get("basis", "")
        name = labels.get(qid, eintrag.get("label", qid))
        if basis in klassen:
            ziel_qid, ziel_label = klassen[basis]
            lage = (f"steht in [[en:List of named alloys]] unter '{basis}', "
                    f"hat aber keinen P279/P31-Pfad zu Legierung (Q37756). "
                    f"Passende Klasse: {ziel_qid} ({ziel_label}).")

            if qid not in ist_klasse and qid in hat_p31:
                # Als Instanz modelliert. P279 waere falsch, P31 auf eine
                # Werkstoffklasse schreiben wir nicht - also nichts entwerfen.
                treffer.append(befund(
                    "ohne-einordnung-instanz", qid, name, "",
                    lage + " Das Item traegt aber nur P31 (auf "
                    + ", ".join(f"{k} ({labels.get(k, k)})"
                                for k in hat_p31[qid][:3])
                    + ") und kein P279: es ist als INSTANZ modelliert.",
                    "Kein Entwurf. Ist das Item eine Klasse, fehlt ihm P279 "
                    "- dann erst das klaeren. Ist es wirklich eine Instanz, "
                    f"waere die Aussage P31 auf {ziel_qid} ({ziel_label}); "
                    "P31 auf eine Werkstoffklasse entwirft dieses Werkzeug "
                    "nicht.",
                    eigenschaft="P279",
                    ziel_qid=ziel_qid, ziel_label=ziel_label))
                continue

            ungeprueft = qid not in ist_klasse
            treffer.append(befund(
                "ohne-einordnung", qid, name,
                f"{qid}\tP279\t{ziel_qid}", lage,
                "Grobe Einordnung. Erst pruefen, ob das Item ueberhaupt eine "
                "Legierung ist (Nitride, Carbide und Hydride stehen auch in "
                "der Liste), dann ob eine engere Klasse besser passt."
                + (" ACHTUNG: das Item hat weder P279 noch P31 noch "
                   "Unterklassen - ob es eine KLASSE ist, sagt der Graph "
                   "nicht. P279 setzt das voraus." if ungeprueft else ""),
                ziel_qid=ziel_qid, ziel_label=ziel_label))
        else:
            grund = luecken.get(basis, "kein Basismetall in der Liste")
            treffer.append(befund(
                "ohne-einordnung", qid, name, "",
                f"steht in [[en:List of named alloys]] unter "
                f"'{basis or '?'}', hat aber keinen P279/P31-Pfad zu "
                f"Legierung (Q37756). Kein Vorschlag moeglich: {grund}.",
                "Ohne passende Oberklasse in Wikidata bleibt nur, sie "
                "anzulegen - das tut dieses Werkzeug nicht.",
                eigenschaft="P279"))
    return treffer, luecken


def pruefe_parallelzweig(items: dict, unter_material: set,
                         labels: dict) -> list:
    """Items ohne P279*-Pfad zu material (Q214609).

    Ausdruecklich KEIN Fehler: P279 erlaubt (und P186 verlangt) mehrere
    gleichrangige Werttypen nebeneinander - alloy, chemical compound,
    substance. Eine Legierung muss nicht unter Q214609 haengen, um richtig
    eingeordnet zu sein. Der ausfuehrliche Nachweis steht in
    visualisierung.py, im selben Ordner.

    Gemeldet wird trotzdem, weil die Zahl die Frage beantwortet, ob sich eine
    Vereinheitlichung ueberhaupt lohnt.
    """
    return [befund(
        "parallelzweig", qid, labels.get(qid, eintrag.get("label", qid)), "",
        "kein P279*-Pfad zu material (Q214609) - laeuft ueber einen "
        "parallelen Zweig (alloy, chemical compound, ...).",
        "Kein Fehler. Nur relevant, wenn die Hierarchie unter Q214609 "
        "vereinheitlicht werden soll.", eigenschaft="P279")
        for qid, eintrag in items.items() if qid not in unter_material]


def kennzahlen(items: dict, graph, p31_kanten: list, kinder: dict,
               unter_material: set, eingeordnet: set) -> list:
    """Wie wird P279 in dieser Grundgesamtheit ueberhaupt benutzt?"""
    qids = set(items)
    mit_p279 = {q for q in qids if q in graph and graph.out_degree(q)}
    mit_p31 = {i for i, _ in p31_kanten if i in qids}
    mehrfach = {q for q in mit_p279 if graph.out_degree(q) > 1}
    tiefen = []
    for q in qids & set(graph.nodes):
        try:
            tiefen.append(nx.shortest_path_length(graph, q, MATERIAL_QID))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

    werte = [
        ("Items gesamt", len(qids)),
        ("mit P279 (Unterklasse von)", len(mit_p279)),
        ("mit P31 (ist ein/e)", len(mit_p31)),
        ("mit beidem", len(mit_p279 & mit_p31)),
        ("mit keinem von beiden", len(qids - mit_p279 - mit_p31)),
        ("mit mehreren Oberklassen", len(mehrfach)),
        ("selbst Oberklasse (hat Unterklassen)",
         sum(1 for q in qids if kinder.get(q))),
        ("mit Pfad zu Legierung (Q37756)", len(qids & eingeordnet)),
        ("mit Pfad zu material (Q214609)", len(qids & unter_material)),
        ("kuerzester Abstand zu material, Median",
         sorted(tiefen)[len(tiefen) // 2] if tiefen else 0),
        ("Klassen im geholten Graphen", graph.number_of_nodes()),
        ("P279-Kanten im geholten Graphen", graph.number_of_edges()),
    ]
    return [befund("kennzahl", "", name, "", "", "", kennzahl=wert)
            for name, wert in werte]


def _kategorie_tabelle() -> dict:
    """{Ordnungszahl: Kategorie-QID} - die Sollzuordnung.

    Aus Bereichen aufgebaut statt als 118-Zeilen-Tabelle: so ist auf einen
    Blick zu sehen, dass es die Bloecke des Periodensystems sind und keine
    Aufzaehlung von Einzelfaellen.
    """
    tabelle = {}
    def setze(qid, *zahlen):
        for z in zahlen:
            tabelle[z] = qid
    setze("Q19600", 1, 6, 7, 8, 15, 16)                  # Nichtmetalle
    setze("Q19557", 3, 11, 19, 37, 55, 87)               # Alkalimetalle
    setze("Q19563", 4, 12, 20, 38, 56, 88)               # Erdalkalimetalle
    setze("Q19596", 5, 14, 32, 33, 51, 52)               # Halbmetalle
    setze("Q19605", 9, 17, 35, 53)                       # Halogene
    setze("Q19609", 2, 10, 18, 36, 54, 86)               # Edelgase
    setze("Q19569", *range(57, 72))                      # Lanthanoide
    setze("Q19577", *range(89, 104))                     # Actinoide
    setze("Q19588", *range(21, 30), *range(39, 48),      # Uebergangsmetalle
          *range(72, 80), *range(104, 112))
    setze("Q19591", 13, 31, 49, 50, 81, 82, 83)          # Metalle p-Block
    return tabelle


KATEGORIE_NACH_Z = _kategorie_tabelle()

# Die Faelle, in denen die Lehrbuecher NICHT einig sind. Hier entsteht
# bewusst kein Entwurf, sondern eine Meldung mit den Lesarten - ein
# Schwellwert oder eine Tabellenzeile wuerde hier eine Einigkeit behaupten,
# die es nicht gibt.
KATEGORIE_UMSTRITTEN = {
    30: "Zink, Cadmium, Quecksilber und Copernicium (12. Gruppe) sind bei "
        "der IUPAC keine Uebergangsmetalle (volle d-Schale in allen "
        "Oxidationsstufen), in vielen Lehrbuechern aber schon; sonst "
        "gelten sie als Metalle des p-Blocks.",
    34: "Selen wird ueberwiegend als Nichtmetall gefuehrt, in manchen "
        "Darstellungen als Halbmetall - Wikidata sagt derzeit Halbmetall.",
    84: "Polonium gilt teils als Metall des p-Blocks, teils als Halbmetall.",
    85: "Astat steht in der 17. Gruppe, wird aber wegen seiner "
        "Eigenschaften auch als Halbmetall oder Metall gefuehrt.",
    113: "Ab Nihonium (113) sind die Eigenschaften nur berechnet, nicht "
         "gemessen - die Stellung im p-Block ist eine Vorhersage.",
}
# Alle Ordnungszahlen, zu denen der obige Text gehoert.
UMSTRITTENE_Z = ({30, 48, 80, 112}          # 12. Gruppe -> siehe 30
                 | {34}                     # Selen
                 | {84}                     # Polonium
                 | {85, 117}                # Astat, Tenness
                 | set(range(113, 119)))    # Vorhersagen ab 113


def _umstritten_grund(z: int) -> str:
    """Der Erlaeuterungstext zu einer umstrittenen Ordnungszahl."""
    if z in KATEGORIE_UMSTRITTEN:
        return KATEGORIE_UMSTRITTEN[z]
    if z in {48, 80, 112}:
        return KATEGORIE_UMSTRITTEN[30]
    if z == 117:
        return KATEGORIE_UMSTRITTEN[85]
    if z >= 113:
        return KATEGORIE_UMSTRITTEN[113]
    return "die Zuordnung ist in der Literatur nicht einheitlich."


def gruppe_von(z: int) -> Optional[int]:
    """Die Gruppe des Periodensystems zur Ordnungszahl - oder None.

    None fuer die f-Block-Elemente: Lanthanoide und Actinoide stehen in
    KEINER Gruppe, sie bilden den herausgezogenen Block. Sie hier auf
    Gruppe 3 zu setzen waere genau die Behauptung, um die seit Jahrzehnten
    gestritten wird (La/Ac gegen Lu/Lr).
    """
    if z < 1 or z > LETZTE_ORDNUNGSZAHL:
        return None
    if z == 1:
        return 1
    if z == 2:
        return 18
    if 58 <= z <= 71 or 90 <= z <= 103:
        return None
    # Ordnungszahl der ersten Spalte der Periode -> Spaltenabstand.
    for beginn, laenge in ((3, 8), (11, 8), (19, 18), (37, 18),
                           (55, 32), (87, 32)):
        if beginn <= z < beginn + laenge:
            spalte = z - beginn
            if laenge == 8:
                return spalte + 1 if spalte < 2 else spalte + 11
            if laenge == 18:
                return spalte + 1
            # Periode 6 und 7: nach der 3. Gruppe folgt der f-Block.
            return spalte + 1 if spalte <= 2 else spalte - 13
    return None


def hole_elementdaten(qids: list, block: int = 100) -> dict:
    """{qid: {'z', 'dichten', 'p31', 'p279', 'p361'}} fuer die Elemente.

    Eine Abfrage fuer alles, was das Szenario braucht - Ordnungszahl,
    bestehende Einordnung und die Dichte MIT EINHEIT. Die Einheit ist keine
    Formalie: P2054 steht an den Elementen in zwei Einheiten nebeneinander
    (56 Werte in kg/m3, 45 in g/cm3, gemessen 2026-08-29). Wer den rohen
    Zahlenwert nimmt, haelt Natrium (1033 kg/m3) fuer ein Schwermetall.

    P31 wird zusaetzlich zu P279 geholt: nach
    .claude/rules/periodic-table-conventions.md gehoert JEDE Einordnung
    eines Elements (Kategorie, Leicht-/Schwermetall) an P31, nie an P279 -
    Elemente sind Instanzen, keine Klassen. Ohne den P31-Wert liesse sich
    ein bestehendes, falsch als P279 gesetztes Statement nicht von einem
    fehlenden unterscheiden.
    """
    daten = {}
    for teil in in_bloecken(qids, block):
        for b in sparql(f"""SELECT ?i ?z ?k ?c ?t ?d ?u WHERE {{
          VALUES ?i {{ {werte_klausel(teil)} }}
          ?i wdt:P1086 ?z .
          OPTIONAL {{ ?i wdt:P31 ?k }}
          OPTIONAL {{ ?i wdt:P279 ?c }}
          OPTIONAL {{ ?i wdt:P361 ?t }}
          OPTIONAL {{ ?i p:P2054/psv:P2054 [ wikibase:quantityAmount ?d ;
                                             wikibase:quantityUnit ?u ] }}
        }}"""):
            qid = qid_aus(b, "i")
            eintrag = daten.setdefault(qid, {"z": int(float(b["z"]["value"])),
                                             "dichten": set(), "p31": set(),
                                             "p279": set(), "p361": set()})
            if "k" in b:
                eintrag["p31"].add(qid_aus(b, "k"))
            if "c" in b:
                eintrag["p279"].add(qid_aus(b, "c"))
            if "t" in b:
                eintrag["p361"].add(qid_aus(b, "t"))
            faktor = DICHTE_EINHEITEN.get(qid_aus(b, "u")) if "u" in b else None
            if faktor and "d" in b:
                eintrag["dichten"].add(round(float(b["d"]["value"]) * faktor, 4))
    return daten


def _dichteklasse(dichten: set) -> tuple:
    """(QID, Bezeichnung, Begruendungstext) oder (None, None, Grund).

    Alle bekannten Dichtewerte muessen auf DERSELBEN Seite der Grenze
    liegen und den Graubereich meiden. Elemente tragen mehrere P2054-Werte
    (Allotrope, Temperaturen); ein einzelner herausgegriffener Wert waere
    Zufall.
    """
    if not dichten:
        return None, None, "keine Dichte (P2054) in bekannter Einheit"
    unten, oben = DICHTE_GRENZE - DICHTE_GRAUBEREICH, DICHTE_GRENZE + DICHTE_GRAUBEREICH
    liste = ", ".join(f"{d:g}" for d in sorted(dichten))
    if all(d < unten for d in dichten):
        return (LEICHTMETALL_QID, "Leichtmetalle",
                f"Dichte {liste} g/cm3, durchweg unter "
                f"{DICHTE_GRENZE:g} g/cm3")
    if all(d > oben for d in dichten):
        return (SCHWERMETALL_QID, "Schwermetalle",
                f"Dichte {liste} g/cm3, durchweg ueber "
                f"{DICHTE_GRENZE:g} g/cm3")
    return None, None, (f"Dichte {liste} g/cm3 - im Graubereich um die "
                        f"{DICHTE_GRENZE:g}-g/cm3-Grenze oder uneinheitlich")


# Kategorien, deren Elemente keine Metalle sind - fuer die ist die Frage
# nach Leicht- oder Schwermetall gegenstandslos.
NICHTMETALL_KATEGORIEN = {"Q19596", "Q19600", "Q19605", "Q19609"}

# Dieselbe Frage ist auch dort gegenstandslos, wo gar nicht feststeht, ob
# das Element ein Metall ist: Selen, Polonium, Astat und alles ab 113, wo
# die Eigenschaften nur berechnet sind. Zink, Cadmium und Quecksilber
# fehlen hier bewusst - ob sie Uebergangsmetalle sind, ist strittig, DASS
# sie Metalle sind, nicht.
KEIN_METALL_Z = {34, 84, 85} | set(range(113, 119))


def pruefe_elementklasse(items: dict, elementdaten: dict,
                         labels: dict, mit_dichte: bool = True) -> list:
    """Die Einordnung der Elemente gegen das Periodensystem.

    Nach .claude/rules/periodic-table-conventions.md (Fassung nach der
    Korrektur einer Ueberinterpretation) sind das DREI verschiedene Faelle,
    mit unterschiedlicher Zielproperty und unterschiedlicher Freigabe fuer
    einen automatischen Entwurf:

      Fall 1  Element -> chemisches Element: P31 -> Q11344. Prueft dieses
              Werkzeug nicht selbst - das ist die Grundgesamtheit des
              Szenarios 'periodensystem' (siehe POPULATIONEN), nicht ein
              Befund von pruefe_elementklasse.
      Fall 2  Element -> Periodensystem-Gruppe UND Element -> Elementkategorie
              (Alkalimetalle, Uebergangsmetalle, ...): BEIDE gehoeren an
              P361 (Mengenmitgliedschaft, keine Taxonomie) - NIE an P31 oder
              P279. Steht das richtige Ziel schon als P31 oder P279 da, ist
              das ein einfacher Property-Tausch und darf automatisch
              entworfen werden (element-kategorie-falsche-property /
              element-gruppe-falsche-property). Fehlt die Verknuepfung
              ganz, wird P361 vorgeschlagen (*-fehlt).
      Fall 3  Element -> Leicht-/Schwermetall: noch KEINE verbindliche
              Konvention (P31, P279 und P1552 sind alle noch offen). Kein
              automatischer Entwurf - der Fund geht als offene Frage nach
              proposals/review-needed.md (siehe schreibe_review_needed).

    Die drei Gruppen-Items, die zugleich Kategorie-Items sind (2., 17., 18.
    Gruppe = Erdalkalimetalle/Halogene/Edelgase), werden nur EINMAL
    gemeldet - im Kategorie-Block, siehe dort.
    """
    treffer = []
    for qid in sorted(items, key=lambda q: elementdaten.get(q, {}).get("z", 999)):
        eintrag = elementdaten.get(qid)
        if not eintrag:
            continue
        z = eintrag["z"]
        name = labels.get(qid, items[qid].get("label", qid))
        anzeige = f"{name} (Z={z})"
        if z > LETZTE_ORDNUNGSZAHL:
            continue

        # --- 1. Elementkategorie (Fall 2: Ziel ist P361) ---------------
        soll = KATEGORIE_NACH_Z.get(z)
        p31_kat = eintrag["p31"] & set(ELEMENTKATEGORIEN)
        p279_kat = eintrag["p279"] & set(ELEMENTKATEGORIEN)
        p361_kat = eintrag["p361"] & set(ELEMENTKATEGORIEN)
        vorhanden = p31_kat | p279_kat | p361_kat
        if z in UMSTRITTENE_Z:
            treffer.append(befund(
                "element-kategorie-umstritten", qid, anzeige, "",
                f"{_umstritten_grund(z)} Derzeit steht "
                + (", ".join(f"{k} ({ELEMENTKATEGORIEN[k]})"
                             for k in sorted(vorhanden))
                   if vorhanden else "keine Kategorie")
                + " am Item.",
                "Kein Entwurf. Wenn dieses Projekt sich auf ein Schema "
                "festlegt, gehoert die Entscheidung dokumentiert - nicht "
                "in einen Schwellwert.",
                eigenschaft="P361",
                ziel_qid=soll or "", ziel_label=ELEMENTKATEGORIEN.get(soll, "")))
        elif soll and soll not in p361_kat:
            falsch = [p for p, menge in (("P31", p31_kat), ("P279", p279_kat))
                     if soll in menge]
            if falsch:
                treffer.append(befund(
                    "element-kategorie-falsche-property", qid, anzeige,
                    "\n".join([f"-{qid}\t{p}\t{soll}" for p in falsch]
                              + [f"{qid}\tP361\t{soll}"]),
                    f"{soll} ({ELEMENTKATEGORIEN[soll]}) steht hier als "
                    f"{'/'.join(falsch)} statt als P361 - eine Kategorie ist "
                    f"Mengenmitgliedschaft, keine Taxonomie "
                    f"(periodic-table-conventions.md, Fall 2).",
                    "Automatischer Entwurf: Austausch einer fehlerhaften "
                    "Property gegen die korrekte, keine inhaltliche "
                    "Neubewertung.",
                    kennzahl=z))
            else:
                fremd = sorted(vorhanden - {soll})
                if fremd:
                    treffer.append(befund(
                        "element-kategorie-konflikt", qid, anzeige, "",
                        f"traegt P361 auf {', '.join(f'{k} ({ELEMENTKATEGORIEN[k]})' for k in fremd)}; "
                        f"nach der Ordnungszahl {z} steht das Element aber in "
                        f"{soll} ({ELEMENTKATEGORIEN[soll]}).",
                        "Von Hand entscheiden. Entfernt wird hier nichts - die "
                        "bestehende Kategorie kann einem anderen, ebenfalls "
                        "gebraeuchlichen Schema folgen.",
                        eigenschaft="P361",
                        ziel_qid=soll, ziel_label=ELEMENTKATEGORIEN[soll]))
                else:
                    treffer.append(befund(
                        "element-kategorie-fehlt", qid, anzeige,
                        f"{qid}\tP361\t{soll}",
                        f"Z={z} legt die Kategorie fest; am Item fehlt sie "
                        f"als P361.",
                        "Nachrechenbar aus der Ordnungszahl. Zu pruefen bleibt, "
                        "ob am Item nicht schon eine ENGERE Klasse steht "
                        "(Platinmetalle, Edelmetalle), unter der die Kategorie "
                        "ohnehin haengen sollte - dann gehoert die Kante dorthin.",
                        ziel_qid=soll, ziel_label=ELEMENTKATEGORIEN[soll],
                        kennzahl=z))

        # --- 2. Gruppe des Periodensystems (Fall 2: Ziel ist P361) -----
        nummer = gruppe_von(z)
        ziel_gruppe = GRUPPEN_QID.get(nummer) if nummer else None
        # Drei Gruppen-Items sind zugleich Kategorie-Items: die 2. Gruppe
        # IST "Erdalkalimetalle", die 17. IST "Halogene", die 18. IST
        # "Edelgase". Fuer die wird oben im Kategorie-Block bereits exakt
        # dieselbe Korrektur (-> P361) vorgeschlagen; hier nicht noch einmal
        # unter anderem Namen.
        if ziel_gruppe and ziel_gruppe not in ELEMENTKATEGORIEN:
            art = ("Hauptgruppe" if nummer in HAUPTGRUPPEN else "Nebengruppe")
            gruppe_label = labels.get(ziel_gruppe, ziel_gruppe)
            if ziel_gruppe not in eintrag["p361"]:
                falsch = [p for p, menge in
                         (("P31", eintrag["p31"]), ("P279", eintrag["p279"]))
                         if ziel_gruppe in menge]
                if falsch:
                    treffer.append(befund(
                        "element-gruppe-falsche-property", qid, anzeige,
                        "\n".join([f"-{qid}\t{p}\t{ziel_gruppe}" for p in falsch]
                                  + [f"{qid}\tP361\t{ziel_gruppe}"]),
                        f"die {nummer}. {art} ({gruppe_label}) steht hier als "
                        f"{'/'.join(falsch)} statt als P361; in Wikidata sind "
                        f"alle 18 Gruppen ueber P361 besetzt.",
                        "Automatischer Entwurf: Austausch einer fehlerhaften "
                        "Property gegen die korrekte, keine inhaltliche "
                        "Neubewertung.",
                        kennzahl=nummer))
                else:
                    treffer.append(befund(
                        "element-gruppe-fehlt", qid, anzeige,
                        f"{qid}\tP361\t{ziel_gruppe}",
                        f"Z={z} - {nummer}. {art}; am Item fehlt das P361.",
                        "Folgt aus der Ordnungszahl. Zu pruefen ist nur, ob "
                        "die Gruppe nicht schon unter einem anderen Item "
                        "danebensteht.",
                        ziel_qid=ziel_gruppe, ziel_label=gruppe_label,
                        kennzahl=nummer))

        # --- 3. Leicht- oder Schwermetall (Fall 3: noch offen) ---------
        # Keine verbindliche Konvention - P31, P279 und has quality (P1552)
        # stehen alle noch zur Debatte. Kein automatischer Entwurf; der Fund
        # geht als offene Frage nach proposals/review-needed.md, siehe
        # schreibe_review_needed().
        if (not mit_dichte or soll in NICHTMETALL_KATEGORIEN
                or z in KEIN_METALL_Z):
            continue
        ziel_dichte, dichte_label, grund = _dichteklasse(eintrag["dichten"])
        if not ziel_dichte:
            continue
        aktuell = [p for p, menge in
                  (("P31", eintrag["p31"]), ("P279", eintrag["p279"]),
                   ("P361", eintrag["p361"]))
                  if ziel_dichte in menge]
        treffer.append(befund(
            "element-dichteklasse-review", qid, anzeige, "",
            f"{grund} -> {dichte_label[:-1]}; aktuell am Item verwendete "
            f"Property fuer dieses Ziel: {'/'.join(aktuell) or 'keine'}.",
            "Noch keine verbindliche Konvention (periodic-table-"
            "conventions.md, Fall 3). Kein automatischer Entwurf - als "
            "offene Frage in proposals/review-needed.md eingetragen.",
            eigenschaft="(offen: P31/P279/P1552)",
            ziel_qid=ziel_dichte, ziel_label=dichte_label,
            kennzahl=z))
    return treffer


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

# Umbruchmass der Fliesstexte. Breiter als frueher (68), weil die Datei
# zum Ueberfliegen gebaut ist und nicht zum Lesen: je weniger Zeilen
# zwischen zwei Entwuerfen stehen, desto schneller ist sie durch.
BREITE = 96

_TRENNER = "# " + "=" * 70

# Reihenfolge und Ueberschrift der auskommentierten Abschnitte. Der Text
# hinter dem Doppelpunkt sagt, WARUM hier nichts einspielbar ist - das ist
# die Information, die beim Durchsehen zaehlt.
# Die Staffelung. Eine Stufe = EINE Art von Beweiskraft, und der Kopftext
# sagt, was der Mensch an dieser Stufe konkret pruefen muss. Das ist der
# ganze Zweck der Datei: von oben nach unten wird die Pruefung aufwendiger
# und die Trefferquote schlechter, also kann jederzeit aufgehoert werden.
STUFEN = [
    (1, "MECHANISCH SICHER", ["redundant"], True,
     "folgt allein aus dem Graphen, behauptet nichts, ist umkehrbar",
     ["Die entfernte Kante gilt danach weiter, nur abgeleitet statt doppelt",
      "notiert. PRUEFEN: Stimmt der angegebene Ersatzpfad?"]),
    (2, "STRUKTURELL BEGRUENDET", ["element-kategorie-fehlt",
                                   "element-kategorie-falsche-property",
                                   "element-gruppe-fehlt",
                                   "element-gruppe-falsche-property",
                                   "instanz-als-klasse", "metaklasse",
                                   "metaklasse-konflikt", "verkehrt",
                                   "redundant-unsicher", "zyklus"], False,
     "aus dem Graphen, aber mit einer fachlichen Entscheidung davor",
     ["Der Graph sagt, DASS etwas nicht stimmt - nicht, wie herum es richtig",
      "waere. PRUEFEN: Einzelfall, Item oeffnen, Aussage im Kontext ansehen.",
      "Die *-falsche-property-Funde sind ein reiner Property-Tausch (die",
      "falsche Aussage weg, P361 mit demselben Ziel hin) - trotzdem PRUEFEN,",
      "ob das Ziel selbst noch stimmt."]),
    (3, "GERECHNET ODER GERATEN", ["zusammensetzung",
                                   "zu-allgemein",
                                   "ohne-einordnung"], False,
     "aus einer Bezeichnung oder einem Messwert gegen eine Konvention",
     ["Die Beweiskraft ist je Gruppe SEHR verschieden - der Gruppenkopf sagt,",
      "woran man ist. ACHTUNG: Was aus der Bezeichnung kommt, hat ZWEI Zeilen,",
      "und die erste ENTFERNT die bestehende Einordnung. Im Zweifel: liegen-",
      "lassen. PRUEFEN: Passt die Oberklasse sachlich? Ist das Item ueberhaupt",
      "ein Werkstoff - oder ein Schichtverbund, eine Verbindung, ein Handelsname?"]),
    (4, "NUR MELDUNG - KEIN ENTWURF", ["element-kategorie-umstritten",
                                       "element-kategorie-konflikt",
                                       "element-dichteklasse-review",
                                       "metaklasse-klasse",
                                       "ohne-einordnung-instanz",
                                       "p31-neben-p279", "parallelzweig"],
     False,
     "beschreibt die Lage, fordert nichts - ein Teil ist KEIN Fehler",
     ["Hier gibt es nichts einzuspielen. Wo der Graph die Klassenzugehoerigkeit",
      "nicht hergibt, entsteht eine Meldung statt eines Entwurfs: an eine",
      "Werkstoffklasse schreibt dieses Werkzeug kein P31, an eine Instanz kein",
      "P279. Die element-dichteklasse-review-Funde stehen zusaetzlich in",
      "proposals/review-needed.md, siehe schreibe_review_needed()."]),
]

# Ueberschrift und Einzeiler je Befundart, fuer die Zwischenkoepfe.
ART_TITEL = {
    "redundant": ("Doppelte Kante", "gilt ueber einen anderen Elter ohnehin"),
    "instanz-als-klasse": ("P31 statt P279",
                           "das Item hat selbst Unterklassen"),
    "metaklasse": ("Chemische Metaklasse fehlt",
                   "Legierung ohne P31-Metaklasse - die Guideline verlangt "
                   "fuer Gemische Q119892838; entworfen nur an Items, die "
                   "selbst keine Klasse sind"),
    "metaklasse-klasse": ("Metaklasse fehlt, Item ist aber Klasse",
                          "nur Meldung: an eine Werkstoffklasse schreibt "
                          "dieses Werkzeug kein P31"),
    "metaklasse-konflikt": ("Falsche Chemie-Metaklasse",
                            "nur Meldung: die Guideline laesst nur EINE zu, "
                            "die bestehende muesste weichen"),
    "verkehrt": ("Kante verkehrt herum",
                 "die weitere Klasse haengt unter der engeren"),
    "redundant-unsicher": ("Doppelt, aber Ersatzpfad wackelt",
                           "der Ersatzpfad laeuft ueber eine Kante von oben"),
    "zyklus": ("Zyklus", "eine Klasse ist ihre eigene Oberklasse"),
    "zusammensetzung": ("Basismetall aus der Zusammensetzung",
                        "GERECHNET: der Anteil steht im Namen, das groesste "
                        "Element ist das Basismetall"),
    "zu-allgemein": ("Zu allgemein eingehaengt",
                     "GERATEN: die Bezeichnung nennt eine speziellere "
                     "Klasse - hier sind Fehltreffer die Regel"),
    "ohne-einordnung": ("Nicht als Legierung eingeordnet",
                        "steht in [[en:List of named alloys]]"),
    "ohne-einordnung-instanz": ("Nicht eingeordnet, aber Instanz",
                                "nur Meldung: das Item hat nur P31 - ein "
                                "P279 setzt eine Klasse voraus"),
    "p31-neben-p279": ("P31 neben P279", "nur zur Kenntnis"),
    "parallelzweig": ("Kein Pfad zu material (Q214609)",
                      "kein Fehler - P186 erlaubt parallele Werttypen"),
    "element-kategorie-fehlt": ("Elementkategorie fehlt (P361)",
                                "NACHGERECHNET: die Ordnungszahl legt die "
                                "Kategorie im Periodensystem eindeutig fest"),
    "element-kategorie-falsche-property": ("Kategorie steht als P31/P279 statt P361",
                                           "Property-Tausch: Mengenmitgliedschaft, "
                                           "keine Taxonomie - "
                                           "periodic-table-conventions.md Fall 2"),
    "element-gruppe-fehlt": ("Gruppe des Periodensystems fehlt (P361)",
                             "NACHGERECHNET aus der Ordnungszahl"),
    "element-gruppe-falsche-property": ("Gruppe steht als P31/P279 statt P361",
                                        "Property-Tausch: Mengenmitgliedschaft, "
                                        "keine Taxonomie - "
                                        "periodic-table-conventions.md Fall 2"),
    "element-dichteklasse-review": ("Leicht- oder Schwermetall - offene Frage",
                                    "GERECHNET aus P2054 gegen die 5-g/cm3-"
                                    "Grenze, aber KEIN Entwurf: welche Property "
                                    "richtig waere, ist noch nicht entschieden "
                                    "(Fall 3) - siehe proposals/review-needed.md"),
    "element-kategorie-konflikt": ("Andere Elementkategorie am Item",
                                   "nur Meldung: die vorhandene kann einem "
                                   "anderen gebraeuchlichen Schema folgen"),
    "element-kategorie-umstritten": ("Kategorie in der Literatur strittig",
                                     "nur Meldung: 12. Gruppe, Selen, "
                                     "Polonium, Astat und alles ab 113"),
}

WD = "https://www.wikidata.org/wiki/"

# Ueberschrift je Eigenschaft. Innerhalb einer Stufe wird nach ihr
# gruppiert - siehe _stufen_block.
EIGENSCHAFT_TITEL = {
    "P279": "P279 - Unterklasse von",
    "P31": "P31 - ist ein(e)",
    "P361": "P361 - Teil von",
    "P31 -> P279": "P31 -> P279 - Aussage umhaengen",
    "P31 -> P361": "P31 -> P361 - Aussage umhaengen (Element ist Instanz, keine Klasse)",
    "P279 -> P361": "P279 -> P361 - Aussage umhaengen (Element ist Instanz, keine Klasse)",
    "": "ohne Eigenschaft - der Befund benennt keine Aussage",
}

# Reihenfolge der Eigenschaftsbloecke. Was hier nicht steht, kommt danach
# in alphabetischer Folge; die leere Eigenschaft (reine Lagebeschreibung)
# immer zuletzt.
EIGENSCHAFT_REIHENFOLGE = ["P279", "P31 -> P279", "P31", "P31 -> P361",
                          "P279 -> P361", "P361"]


def _eigenschaft_rang(eigenschaft: str) -> tuple:
    if eigenschaft in EIGENSCHAFT_REIHENFOLGE:
        return (0, EIGENSCHAFT_REIHENFOLGE.index(eigenschaft), "")
    return (2, 0, "") if not eigenschaft else (1, 0, eigenschaft)


def _sortierschluessel(b: dict) -> tuple:
    """Innerhalb einer Eigenschaft: gleiches ZIEL zusammen.

    Der Punkt der ganzen Umstellung. Nach Item sortiert steht in der Datei
    118-mal dieselbe Ueberlegung neu da; nach Eigenschaft und Ziel sortiert
    steht einmal "diese 21 Items werden Uebergangsmetalle" - und wer das
    Ziel einmal geprueft hat, arbeitet die Gruppe am Stueck ab.
    """
    return (b.get("ziel_label", "").lower(), b.get("ziel_qid", ""),
            (b["label"] or b["qid"]).lower())


def _pruefkopf(anzahl: int, text: str) -> list:
    """Die gemeinsame Pruefanweisung eines Kopfes, eingerueckt."""
    vor = f"Pruefen (alle {anzahl}): " if anzahl > 1 else "Pruefen: "
    return [f"#      {satz}" for satz in _umbrechen(vor + text, BREITE - 7)]


def _stueck(anzahl: int) -> str:
    return "1 Item" if anzahl == 1 else f"{anzahl} Items"


def _befund_block(b: dict, einspielbar: bool, zaehler: list,
                  ohne_entscheidung: bool = False) -> list:
    """Ein einzelner Vorschlag - im Regelfall zwei Zeilen.

    Kopfzeile und Begruendung stehen zusammen in EINEM umbrochenen Absatz,
    das Ziel steht nicht dabei: es steht schon im Gruppenkopf darueber, und
    zweimal dasselbe zu lesen kostet beim Durchsehen mehr, als es hilft.

    `ohne_entscheidung` laesst die Pruefanweisung weg - dann steht sie
    einmal ueber der Gruppe statt sechsundfuenfzigmal darin.
    """
    zaehler[0] += 1
    name = b["label"] or b["qid"]
    kopf = f"[{zaehler[0]:04d}] {name}  {WD}{b['qid']}"
    text = f"{kopf}  |  {b['begruendung']}" if b["begruendung"] else kopf
    zeilen = [f"# {z}" if i == 0 else f"#        {z}"
              for i, z in enumerate(
                  _umbrechen(text, BREITE - 8, erste_laenge=len(kopf)))]
    if b["entscheidung"] and not ohne_entscheidung:
        for satz in _umbrechen("Pruefen: " + b["entscheidung"], BREITE - 8):
            zeilen.append(f"#        {satz}")
    for qs in (b["quickstatements"] or "").splitlines():
        # EIN '#' davor, sonst nichts: freigeben heisst genau ein Zeichen
        # loeschen. Fliesstext traegt immer '# ' mit Leerzeichen, Entwuerfe
        # nie - im Editor findet die Suche nach '#Q' und '#-Q' also genau
        # die Entwuerfe. In der einspielbaren Stufe steht die Zeile blank.
        zeilen.append(qs if einspielbar else f"#{qs}")
    return zeilen


def _stufen_block(nummer: int, titel: str, arten: list, einspielbar: bool,
                  kurz: str, erklaerung: list, befunde: list,
                  zaehler: list) -> list:
    """Ein Stufenblock als Zeilenliste. `zaehler` ist einelementig und
    laeuft ueber alle Stufen durch - die Nummer im Kopf jedes Vorschlags
    ist damit ueber die ganze Datei eindeutig und zitierbar.

    Gegliedert wird in drei Ebenen: Stufe -> EIGENSCHAFT -> Befundart, und
    innerhalb der Befundart nach Ziel. Die Eigenschaft ist die oberste,
    weil sie bestimmt, WAS beim Freigeben passiert: eine P279-Zeile haengt
    um, eine P31-Zeile klassifiziert, eine P361-Zeile ordnet ein Teil einem
    Ganzen zu.

    Jede Ueberschrift ist eine Zeile. Was sich wiederholen wuerde - Ziel,
    Link, Pruefanweisung - steht im Gruppenkopf und nicht in jedem Eintrag;
    die Datei wird dadurch rund halb so lang und laesst sich schneller nach
    QuickStatements kopieren.
    """
    teil = [b for b in befunde if b["befund"] in arten]
    marke = "  ***EINSPIELBAR***" if einspielbar else ""
    zeilen = ["", _TRENNER,
              f"# STUFE {nummer} - {titel} ({len(teil)}){marke}",
              f"# {kurz}"]
    zeilen += [f"# {z}".rstrip() for z in erklaerung]
    zeilen.append(_TRENNER)
    if not teil:
        zeilen.append("# (keine)")
        return zeilen

    nach_eigenschaft = {}
    for b in teil:
        nach_eigenschaft.setdefault(b.get("eigenschaft", ""), []).append(b)

    for eigenschaft in sorted(nach_eigenschaft, key=_eigenschaft_rang):
        gruppe = nach_eigenschaft[eigenschaft]
        kopf = EIGENSCHAFT_TITEL.get(eigenschaft, eigenschaft)
        zeilen += ["", f"# ==== EIGENSCHAFT {kopf} ({len(gruppe)}) "
                       .ljust(BREITE, "=")]
        for art in arten:
            eintraege = sorted((b for b in gruppe if b["befund"] == art),
                               key=_sortierschluessel)
            if not eintraege:
                continue
            art_kopf, zusatz = ART_TITEL.get(art, (art, ""))
            zeilen.append("")
            for i, satz in enumerate(_umbrechen(
                    f"---- {art_kopf} ({len(eintraege)})"
                    + (f" - {zusatz}" if zusatz else ""), BREITE)):
                zeilen.append(f"# {satz}" if i == 0 else f"#      {satz}")
            # Befundarten ohne Ziel (reine Lagemeldungen) bilden keine
            # Zielgruppen - dort steht die gemeinsame Pruefanweisung unter
            # dem Artkopf, sonst wiederholt sie sich dreizehnmal wortgleich.
            saetze = {b["entscheidung"] for b in eintraege}
            artweit = ("" if any(b.get("ziel_qid") for b in eintraege)
                       or len(saetze) != 1 else saetze.pop())
            if artweit:
                zeilen += _pruefkopf(len(eintraege), artweit)
            letztes_ziel, gemeinsam = None, artweit
            for b in eintraege:
                # Zwischenzeile, sobald das Ziel wechselt: sie traegt Label,
                # Link und - wenn sie fuer alle dieselbe ist - die
                # Pruefanweisung. Genau dafuer wird nach Ziel sortiert: die
                # Frage "passt dieses Ziel?" wird einmal gestellt.
                ziel = (b.get("ziel_qid", ""), b.get("ziel_label", ""))
                if ziel != letztes_ziel and ziel[0]:
                    gleich = [x for x in eintraege
                              if (x.get("ziel_qid", ""),
                                  x.get("ziel_label", "")) == ziel]
                    saetze = {x["entscheidung"] for x in gleich}
                    gemeinsam = saetze.pop() if len(saetze) == 1 else ""
                    zeilen += ["#", f"#   -> ZIEL {ziel[1]}  {WD}{ziel[0]}"
                                    f"   ({_stueck(len(gleich))})"]
                    if gemeinsam:
                        zeilen += _pruefkopf(len(gleich), gemeinsam)
                elif ziel != letztes_ziel:
                    gemeinsam = artweit
                letztes_ziel = ziel
                zeilen += _befund_block(b, einspielbar, zaehler,
                                        ohne_entscheidung=bool(gemeinsam))
    return zeilen


def _umbrechen(text: str, breite: int, erste_laenge: int = 0) -> list:
    """Fliesstext auf `breite` Zeichen umbrechen - ohne textwrap, weil der
    lange QIDs und Pfadketten mitten im Bezeichner trennt.

    `erste_laenge` haelt die erste Zeile mindestens so lang: der Kopf eines
    Vorschlags (Nummer, Bezeichnung, Link) gehoert zusammen, auch wenn der
    Link allein schon breiter ist als das Umbruchmass.
    """
    zeilen, aktuell = [], ""
    for wort in text.split():
        grenze = max(breite, erste_laenge) if not zeilen else breite
        if aktuell and len(aktuell) + 1 + len(wort) > grenze:
            zeilen.append(aktuell)
            aktuell = wort
        else:
            aktuell = f"{aktuell} {wort}".strip()
    if aktuell:
        zeilen.append(aktuell)
    return zeilen or [""]


def schreibe_empfehlung(befunde: list, pfad: str, population: str,
                        luecken: dict, ohne_item: list, vorsichtig: bool,
                        mengengeruest: str) -> None:
    """Die eine gestaffelte Empfehlung.

    Aufbau: Kopf mit Arbeitsanweisung und Inhaltsverzeichnis (mit
    Zeilennummern, damit sich im Editor direkt hinspringen laesst), dann vier
    Stufen nach Beweiskraft.

    Nur Stufe 1 steht als ausfuehrbare QuickStatements-Syntax da. Ab Stufe 2
    traegt jeder Entwurf ein einzelnes '#' - QuickStatements liest es als
    Kommentar, der Mensch loescht dieses eine Zeichen, wenn er die Zeile
    freigibt. Fliesstext traegt '# ' mit Leerzeichen, die Datei laesst sich
    also jederzeit als Ganzes einfuegen, ohne dass eine ungepruefte Zeile
    zur Aussage wird.
    """
    zaehler = [0]
    bloecke = []
    for nummer, titel, arten, einspielbar, kurz, erklaerung in STUFEN:
        bloecke.append((nummer, titel, arten,
                        _stufen_block(nummer, titel, arten,
                                      einspielbar and not vorsichtig,
                                      kurz, erklaerung, befunde, zaehler)))

    schluss = _schlussblock(luecken, ohne_item)

    # Kopf zweimal bauen: der erste Durchgang liefert nur seine Laenge,
    # damit die Zeilennummern im Inhaltsverzeichnis stimmen.
    def kopf(offsets: dict) -> list:
        z = [
            _TRENNER,
            "# EMPFEHLUNG ZUR KLASSENSTRUKTUR IN WIKIDATA",
            f"# {POPULATIONEN[population]['beschreibung']}",
            f"# Grundgesamtheit '{population}', erzeugt "
            f"{dt.datetime.now():%Y-%m-%d %H:%M}",
            "#",
            "# FREIGEBEN = EIN ZEICHEN LOESCHEN.",
            "#   Jeder Entwurf steht als '#Q123<TAB>P279<TAB>Q456' da - EIN",
            "#   '#' davor, ohne Leerzeichen. Geprueft und fuer richtig",
            "#   befunden? Das '#' weg, fertig. Sonst stehenlassen.",
            "#   Im Editor findet die Suche nach '#Q' und '#-Q' genau die",
            "#   Entwuerfe: Fliesstext traegt immer '# ' mit Leerzeichen.",
            "#   Stufe 1 steht schon ohne Marke da und ist einspielbar.",
            "#",
            "#   Die ganze Datei laesst sich jederzeit als GANZES nach",
            "#   QuickStatements kopieren - alles mit '#' wird ignoriert.",
            "#   '-QID<TAB>P279<TAB>QID' entfernt eine Aussage, ohne Minus",
            "#   setzt sie; zweizeilige Entwuerfe gehoeren zusammen.",
            "#",
            "# AUFBAU: Stufe (nach BEWEISKRAFT, nicht nach Wichtigkeit) ->",
            "#   EIGENSCHAFT -> Befundart -> ZIEL. Ziel, Link und",
            "#   Pruefanweisung stehen im Gruppenkopf, nicht in jedem",
            "#   Eintrag: das Ziel einmal pruefen, dann die Gruppe darunter",
            "#   am Stueck abarbeiten. Du kannst jederzeit aufhoeren.",
            "#",
            "# INHALT",
        ]
        for nummer, titel, arten, block in bloecke:
            anzahl = sum(1 for b in befunde if b["befund"] in arten)
            marke = "  EINSPIELBAR" if nummer == 1 and not vorsichtig else ""
            ort = (f"ab Zeile {offsets[nummer]:>5}" if offsets
                   else "ab Zeile     ?")
            z.append(f"#   Stufe {nummer}  {titel[:30]:<32}{anzahl:>4}   "
                     f"{ort}{marke}")
        if vorsichtig:
            z.append("#   (--vorsichtig: auch Stufe 1 ist nur ein Entwurf)")
        nach_eigenschaft = {}
        for b in befunde:
            if b["befund"] == "kennzahl":
                continue
            nach_eigenschaft.setdefault(b.get("eigenschaft", ""), 0)
            nach_eigenschaft[b.get("eigenschaft", "")] += 1
        if nach_eigenschaft:
            z += ["#", "# BEFUNDE NACH EIGENSCHAFT"]
            for e in sorted(nach_eigenschaft, key=_eigenschaft_rang):
                z.append(f"#   {EIGENSCHAFT_TITEL.get(e, e)[:44]:<46}"
                         f"{nach_eigenschaft[e]:>4}")
        z += ["#", f"# {mengengeruest}", _TRENNER]
        return z

    laenge = len(kopf({}))
    offsets, laufend = {}, laenge
    for nummer, _, _, block in bloecke:
        offsets[nummer] = laufend + 2   # Ueberschrift statt Leerzeile davor
        laufend += len(block)

    zeilen = kopf(offsets)
    for _, _, _, block in bloecke:
        zeilen += block
    zeilen += schluss

    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"Empfehlung geschrieben nach: {pfad}", file=sys.stderr)


def _schlussblock(luecken: dict, ohne_item: list) -> list:
    """Was gar kein Item betrifft und deshalb in keine Stufe passt:
    fehlende Klassen und Listennamen ohne Item. Anlegen kann dieses
    Werkzeug beides nicht - es arbeitet nur an bestehenden Items."""
    zeilen = ["", _TRENNER,
              "# ANHANG - LUECKEN IN WIKIDATA (nichts einzuspielen)",
              "#",
              "# Hier fehlt ein Item, nicht eine Aussage. Anlegen tut dieses",
              "# Werkzeug nichts - das ist eine bewusste Entscheidung.",
              _TRENNER]
    if luecken:
        zeilen.append("#")
        zeilen.append("# Basismetalle ohne Legierungsklasse:")
        for basis, grund in sorted(luecken.items()):
            for i, satz in enumerate(_umbrechen(f"{basis}: {grund}", BREITE)):
                zeilen.append(f"#   {satz}" if i == 0 else f"#     {satz}")
    if ohne_item:
        zeilen.append("#")
        zeilen.append(f"# Listeneintraege ohne Wikidata-Item "
                      f"({len(ohne_item)}):")
        for satz in _umbrechen(", ".join(ohne_item), BREITE):
            zeilen.append(f"#   {satz}")
    if not luecken and not ohne_item:
        zeilen.append("# (keine)")
    return zeilen


def schreibe_csv(befunde: list, pfad: str) -> None:
    felder = ["eigenschaft", "befund", "qid", "label", "ziel_qid",
              "ziel_label", "kennzahl", "quickstatements", "begruendung",
              "entscheidung"]
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        schreiber = csv.DictWriter(f, fieldnames=felder)
        schreiber.writeheader()
        # Dieselbe Ordnung wie in der Empfehlung: Eigenschaft, dann Ziel.
        # Eine Tabelle, die anders sortiert ist als die Datei daneben,
        # kostet beim Abgleich mehr Zeit, als sie spart.
        for b in sorted(befunde, key=lambda x: (_eigenschaft_rang(
                x.get("eigenschaft", "")), x["befund"], _sortierschluessel(x))):
            # Der Zeilenumbruch im zweizeiligen P31->P279-Entwurf wuerde die
            # CSV-Zeile sprengen; im Tabellenblatt ist ' | ' lesbarer.
            schreiber.writerow({**{k: b.get(k, "") for k in felder},
                                "quickstatements":
                                    (b["quickstatements"] or "")
                                    .replace("\n", " | ")})
    print(f"CSV geschrieben nach: {pfad}", file=sys.stderr)


# Befundarten, fuer die es (noch) keine verbindliche Konvention gibt und die
# deshalb nach CLAUDE.md ("Arbeitsweise", Punkt 3) als offene Frage in
# proposals/review-needed.md gehoeren statt in einen automatischen Entwurf.
# Aktuell nur Fall 3 aus periodic-table-conventions.md; weitere Arten kommen
# hierher, sobald ein anderer Fall ohne Konvention entsteht.
REVIEW_NEEDED_ARTEN = {"element-dichteklasse-review"}


def schreibe_review_needed(befunde: list, pfad: str) -> None:
    """Haengt offene Fragen ohne automatischen Entwurf an `pfad` an.

    Angehaengt, nicht ueberschrieben: die Datei ist eine fortlaufende
    Sammlung ueber mehrere Laeufe hinweg (CLAUDE.md, "Arbeitsweise" Punkt 3),
    kein Abbild des jeweils letzten Laufs wie die Empfehlungsdatei. Jeder
    Lauf schreibt einen eigenen, mit Zeitstempel ueberschriebenen Abschnitt -
    Dopplungen bei wiederholten Laeufen nimmt dieses Werkzeug bewusst in
    Kauf, das Aufraeumen bleibt beim Reviewer.
    """
    zeilen = [b for b in befunde if b["befund"] in REVIEW_NEEDED_ARTEN]
    if not zeilen or not pfad:
        return
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    neu = not os.path.exists(pfad)
    with open(pfad, "a", encoding="utf-8") as f:
        if neu:
            f.write("# Offene Fragen ohne verbindliche Konvention\n\n"
                    "Gesammelt nach .claude/rules/periodic-table-conventions.md "
                    "und CLAUDE.md (\"Arbeitsweise\", Punkt 3): hier steht "
                    "NICHTS, das dieses Projekt automatisch entscheidet.\n\n")
        f.write(f"## Lauf {dt.datetime.now():%Y-%m-%d %H:%M} "
                f"({len(zeilen)} Fund(e), Fall 3: Leicht-/Schwermetall)\n\n")
        for b in sorted(zeilen, key=lambda b: b["label"]):
            f.write(f"- **{b['label']}** ({WD}{b['qid']}): {b['begruendung']} "
                    f"Ziel waere {b['ziel_qid']} ({b['ziel_label']}), aber "
                    f"welche Property (P31/P279/P1552) dafuer richtig ist, "
                    f"steht noch nicht fest.\n")
        f.write("\n")
    print(f"{len(zeilen)} offene Frage(n) angehaengt an: {pfad}",
          file=sys.stderr)


def bericht(befunde: list, luecken: dict, ohne_item: list,
            vorsichtig: bool = False) -> None:
    """Kurzfassung auf der Konsole - nach denselben Stufen wie die Datei,
    damit beim Lesen der Datei nichts neu einsortiert werden muss."""
    kz = [b for b in befunde if b["befund"] == "kennzahl"]
    if kz:
        print()
        print("Wie P279 hier benutzt wird")
        print("-" * 60)
        for b in kz:
            print(f"  {b['label']:<44}{b['kennzahl']:>6}")

    nach_eigenschaft = {}
    for b in befunde:
        if b["befund"] != "kennzahl":
            e = b.get("eigenschaft", "")
            nach_eigenschaft[e] = nach_eigenschaft.get(e, 0) + 1
    if nach_eigenschaft:
        print()
        print("Befunde nach Eigenschaft")
        print("-" * 60)
        for e in sorted(nach_eigenschaft, key=_eigenschaft_rang):
            print(f"  {EIGENSCHAFT_TITEL.get(e, e)[:44]:<46}"
                  f"{nach_eigenschaft[e]:>6}")

    print()
    print("Befunde nach Stufe")
    print("-" * 60)
    for nummer, titel, arten, einspielbar, _, _ in STUFEN:
        teil = [b for b in befunde if b["befund"] in arten]
        entwuerfe = sum(1 for b in teil if b["quickstatements"])
        marke = ("EINSPIELBAR" if einspielbar and not vorsichtig
                 else "zur Freigabe" if entwuerfe else "nur Meldung")
        print(f"  Stufe {nummer}  {titel[:34]:<36}{len(teil):>5}   "
              f"Entwuerfe {entwuerfe:>4}   {marke}")
        for art in arten:
            anzahl = sum(1 for b in teil if b["befund"] == art)
            if anzahl:
                print(f"           {ART_TITEL.get(art, (art, ''))[0][:32]:<34}"
                      f"{anzahl:>5}")

    if luecken:
        print()
        print("Basismetalle ohne Legierungsklasse in Wikidata")
        print("-" * 60)
        for basis, grund in sorted(luecken.items()):
            print(f"  {basis:<16}{grund}")

    if ohne_item:
        print()
        print(f"{len(ohne_item)} Listeneintraege ohne Wikidata-Item: "
              f"{', '.join(ohne_item)}")
    print()


# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prueft die P279-Struktur der Werkstoffe in Wikidata und "
                    "entwirft Aenderungen als QuickStatements.")
    parser.add_argument("--population", choices=sorted(POPULATIONEN),
                        default="benannte-legierungen",
                        help="Grundgesamtheit (Default: benannte-legierungen, "
                             "die Pruefliste aus [[en:List of named alloys]])")
    parser.add_argument("--pruefungen", nargs="+", choices=PRUEFUNGEN,
                        default=None,
                        help=f"Auswahl der Pruefungen (Default: alle ausser "
                             f"{', '.join(sorted(NUR_PERIODENSYSTEM))}; die "
                             f"Grundgesamtheit 'periodensystem' bringt ihre "
                             f"eigene Auswahl mit). Moeglich: "
                             f"{', '.join(PRUEFUNGEN)}")
    parser.add_argument("--limit", type=int, default=None,
                        help="nur die ersten N Items (fuer Probelaeufe)")
    parser.add_argument("--vorsichtig", action="store_true",
                        help="auch die redundanten Kanten auskommentieren - "
                             "dann enthaelt die Datei keine ausfuehrbare Zeile")
    parser.add_argument("--min-unterbau", type=int, default=25,
                        help="Pruefung 'verkehrt': ab wie vielen Klassen im "
                             "Unterbau der Vergleich aussagekraeftig ist "
                             "(Default 25)")
    parser.add_argument("--bereichswurzel", default=None,
                        help="Pruefung 'verkehrt': Wurzel des Bereichs, dessen "
                             "Klassenbaum vollstaendig geholt und geprueft "
                             f"wird (Default {LEGIERUNG_QID}, Legierung; in "
                             f"der Grundgesamtheit 'periodensystem' "
                             f"{ELEMENT_QID}, chemisches Element). "
                             "Q214609 (material) ist zu gross - der Baum "
                             "umfasst rund 936.000 Klassen.")
    parser.add_argument("--max-umweg", type=int, default=4,
                        help="Pruefung 'redundant': laengster Ersatzpfad, der "
                             "noch als in einer Zeile pruefbar gilt (Default 4)")
    parser.add_argument("--tiefe", type=int, default=DEFAULT_TIEFE,
                        help="Pruefung 'zu-allgemein': bis zu welcher Ebene "
                             "unter den allgemeinen Wurzeln der "
                             f"Kandidatenpool geholt wird (Default "
                             f"{DEFAULT_TIEFE}). Ebene 3 findet mehr, dauert "
                             "aber deutlich laenger und raet oefter daneben.")
    parser.add_argument("--metaklasse-auch-mit-p31", action="store_true",
                        help="Pruefung 'metaklasse': die Metaklasse auch "
                             "dort entwerfen, wo das Item schon ein P31 "
                             "traegt (dann steht sie als ZWEITE P31-Aussage "
                             "daneben). Die Guideline verlangt sie auch dort, "
                             "es sind aber rund doppelt so viele Items, und "
                             "in dieser Menge sitzen die Faelle, die gar "
                             "keine Werkstoffe sind (Stahlrohr, "
                             "Markenzeichen). Default: aus. "
                             "Items, die selbst KLASSEN sind, bleiben auch "
                             "mit diesem Schalter bei der Meldung - an eine "
                             "Werkstoffklasse schreibt dieses Werkzeug kein "
                             "P31.")
    parser.add_argument("--beleg", choices=["name", "beides"], default="name",
                        help="Pruefung 'zu-allgemein': ob nur die Bezeichnung "
                             "als Beleg zaehlt (Default) oder auch die "
                             "Beschreibung. 'beides' verdreifacht die Treffer "
                             "und senkt die Trefferquote deutlich - dass in "
                             "einer Beschreibung ein Wort vorkommt, sagt "
                             "nichts ueber die Klasse.")
    parser.add_argument("--ohne-dichte", action="store_true",
                        help="Pruefung 'elementklasse': die Einteilung in "
                             "Leicht- und Schwermetall auslassen. Sie ist "
                             "die einzige der drei, die auf einer "
                             "Konvention beruht (5 g/cm3) statt auf der "
                             "Ordnungszahl.")
    parser.add_argument("--out-dir", default=PROPOSALS_DIR,
                        help="Zielordner fuer Empfehlung und --csv (Default: "
                             "proposals/ im Repo). Relative --out/--csv werden "
                             "hierunter abgelegt, so landen die Dateien im "
                             "selben Ordner wie ein 'python -m lauf'-Lauf.")
    parser.add_argument("--out", default=None,
                        help="Ziel der Empfehlung (Default: "
                             "<out-dir>/qs_class_<Population>_<Zeit>.txt)")
    parser.add_argument("--csv", default=None,
                        help="zusaetzlich eine Befund-CSV schreiben. Ohne "
                             "diese Angabe entsteht NUR die Empfehlung.")
    parser.add_argument("--review-needed",
                        default=os.path.join(PROPOSALS_DIR, "review-needed.md"),
                        help="Ziel fuer offene Fragen ohne automatischen "
                             "Entwurf (aktuell nur Fall 3 aus "
                             ".claude/rules/periodic-table-conventions.md: "
                             "Leicht-/Schwermetall). Wird angehaengt, nicht "
                             "ueberschrieben (Default: proposals/review-needed.md). "
                             "Leerer Wert schaltet das Schreiben ab.")
    args = parser.parse_args(argv)

    # Die Grundgesamtheit darf Voreinstellungen mitbringen - aber nur dort,
    # wo nichts angegeben wurde. Ein Szenario, das eine ausdrueckliche
    # Angabe ueberschreibt, waere eine Falle.
    info = POPULATIONEN[args.population]
    if args.pruefungen is None:
        args.pruefungen = info.get(
            "pruefungen", [p for p in PRUEFUNGEN if p not in NUR_PERIODENSYSTEM])
    if args.bereichswurzel is None:
        args.bereichswurzel = info.get("bereichswurzel", LEGIERUNG_QID)
    if (set(args.pruefungen) & NUR_PERIODENSYSTEM
            and args.population != "periodensystem"):
        print(f"  {', '.join(sorted(NUR_PERIODENSYSTEM))} uebersprungen: "
              f"braucht die Ordnungszahl (P1086) und ist nur fuer die "
              f"Grundgesamtheit 'periodensystem' gedacht.", file=sys.stderr)
        args.pruefungen = [p for p in args.pruefungen
                           if p not in NUR_PERIODENSYSTEM]

    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    os.makedirs(args.out_dir, exist_ok=True)

    def im_ordner(pfad: str) -> str:
        """Relative Pfade unter --out-dir, absolute bleiben unangetastet."""
        return pfad if os.path.isabs(pfad) else os.path.join(args.out_dir, pfad)

    empfehlung_pfad = im_ordner(
        args.out or f"qs_class_{args.population}_{stempel}.txt")
    csv_pfad = im_ordner(args.csv) if args.csv else None

    items, ohne_item = hole_population(args.population, args.limit)
    if not items:
        raise SystemExit("Grundgesamtheit ist leer - nichts zu pruefen.")
    qids = sorted(items)

    # Ein Graph fuer alles: die Huelle wird einmal geholt, danach laufen
    # Zyklen-, Redundanz- und Verkehrt-Pruefung lokal. Per SPARQL waere jede
    # davon eine eigene teure Abfrage.
    # Die Label-Heuristik prueft die direkten Kinder der allgemeinen Wurzeln.
    # Die gehoeren mit in die Huelle: nur so laesst sich spaeter feststellen,
    # ob ein Vorschlag laengst erfuellt ist (pruefe_zu_allgemein).
    direkt_allgemein, allgemein_baum = {}, {}
    if {"zu-allgemein", "p31-neben-p279", "zusammensetzung"} & set(args.pruefungen):
        print(f"Hole Kandidatenpool bis Tiefe {args.tiefe} unter "
              f"{', '.join(ALLGEMEINE_WURZELN)} ...", file=sys.stderr)
        allgemein_baum, ebene1 = hole_ebenen_baum(
            sorted(ALLGEMEINE_WURZELN), args.tiefe)
        # Ebene 1 sind genau die direkt Eingehaengten - die zu Pruefenden.
        direkt_allgemein = {q: allgemein_baum[q] for q in ebene1}

    # Die Elementdaten VOR der Huelle: die Gruppen- und Kategorie-Items
    # sollen mit in den Graphen, sonst laesst sich nicht feststellen, ob
    # eine Erwartung ueber einen laengeren P279-Pfad schon erfuellt ist.
    elementdaten = {}
    if "elementklasse" in args.pruefungen:
        print(f"Hole Ordnungszahl, Einordnung und Dichte fuer {len(qids)} "
              f"Elemente ...", file=sys.stderr)
        elementdaten = hole_elementdaten(qids)
        ohne_zahl = len(qids) - len(elementdaten)
        print(f"  {len(elementdaten)} Elemente mit Ordnungszahl"
              + (f", {ohne_zahl} ohne (uebersprungen)" if ohne_zahl else ""),
              file=sys.stderr)

    print("Hole P279-Huelle nach oben ...", file=sys.stderr)
    huelle_start = sorted(set(qids) | set(direkt_allgemein)
                          | (set(ELEMENTKATEGORIEN) | set(GRUPPEN_QID.values())
                             | {LEICHTMETALL_QID, SCHWERMETALL_QID}
                             if elementdaten else set()))
    kanten = hole_p279_huelle(huelle_start)
    graph = nx.DiGraph()
    graph.add_nodes_from(huelle_start)
    graph.add_edges_from(kanten)   # Richtung: Kind -> Elter
    print(f"  {graph.number_of_nodes()} Klassen, "
          f"{graph.number_of_edges()} P279-Kanten", file=sys.stderr)

    def erreichbar(ziel: str) -> set:
        """Alle Knoten mit P279*-Pfad zu `ziel` - inklusive ziel selbst."""
        if ziel not in graph:
            return set()
        return nx.ancestors(graph, ziel) | {ziel}

    unter_material = erreichbar(MATERIAL_QID)
    unter_legierung = erreichbar(LEGIERUNG_QID)
    # Die Werkstoff-Ecke: alles unter material oder Legierung, plus die
    # Grundgesamtheit selbst (die haengt nicht zwingend unter beidem - genau
    # das misst die Pruefung 'parallelzweig'). Ausserhalb davon wird nichts
    # vorgeschlagen, siehe pruefe_redundant.
    im_bereich = unter_material | unter_legierung | set(qids)

    braucht_p31 = {"instanz-als-klasse", "kennzahlen", "ohne-einordnung",
                   "p31-neben-p279", "metaklasse"}
    p31_kanten = (hole_p31_kanten(sorted(set(qids) | set(direkt_allgemein)))
                  if braucht_p31 & set(args.pruefungen) else [])
    # Ueber P31 eingeordnet zaehlt genauso: "X ist ein/e Legierung".
    ueber_p31 = {i for i, k in p31_kanten if k in unter_legierung}
    eingeordnet = (unter_legierung | ueber_p31) & set(qids)

    # 'metaklasse' und 'ohne-einordnung' stehen hier, seit sie Klasse und
    # Instanz auseinanderhalten muessen: P279 im Graphen ist das eine
    # Merkmal einer Klasse, eigene Unterklassen das andere. Ohne die
    # Kinderabfrage waere der Test halb.
    braucht_kinder = {"instanz-als-klasse", "kennzahlen", "p31-neben-p279",
                      "metaklasse", "ohne-einordnung"}
    kinder = (hole_kinder(sorted(set(qids) | set(direkt_allgemein)))
              if braucht_kinder & set(args.pruefungen) else {})

    # Wer P279 hat oder Unterklassen hat, ist eine Klasse
    # ([[Help:Basic membership properties]]). Daran haengt, was ueberhaupt
    # entworfen werden darf: kein P31 an eine Klasse, kein P279 an eine
    # Instanz. Kostet keine Abfrage - Graph und Kinder stehen schon.
    ist_klasse = {q for q in qids
                  if (q in graph and graph.out_degree(q)) or kinder.get(q)}
    p31_werte = {}
    for item, klasse in p31_kanten:
        p31_werte.setdefault(item, []).append(klasse)

    # Die Verkehrt-Pruefung braucht einen ZWEITEN Graphen: die vollstaendige
    # Huelle nach UNTEN unter der Bereichswurzel. Grund steht bei
    # verkehrt_kandidaten - in der Aufwaerts-Huelle sind die Unterbaugroessen
    # der oberen Klassen ein Artefakt der Abfrage, und das Ergebnis besteht
    # dann fast nur aus Entitaet, Objekt, Materie und Substanz.
    # Auch fuer 'redundant' und 'zu-allgemein' noetig, nicht nur fuer
    # 'verkehrt': ein Ersatzpfad ueber eine beanstandete Kante taugt nicht
    # als Nachweis (pruefe_redundant), und unter eine beanstandete Klasse
    # haengt man nichts Neues (pruefe_zu_allgemein).
    verkehrt = []
    if {"verkehrt", "redundant", "zu-allgemein"} & set(args.pruefungen):
        print(f"Hole P279-Huelle nach unten unter {args.bereichswurzel} ...",
              file=sys.stderr)
        ab_kanten = hole_p279_huelle([args.bereichswurzel], abwaerts=True)
        ab_graph = nx.DiGraph()
        ab_graph.add_nodes_from([args.bereichswurzel])
        ab_graph.add_edges_from(ab_kanten)
        # Im Bereich ist nur, was WIRKLICH unter der Wurzel haengt: die
        # Abwaerts-Huelle bringt ueber die Kanten auch Eltern ausserhalb mit,
        # und fuer die stimmt die gezaehlte Unterbaugroesse nicht.
        im_bereich = nx.ancestors(ab_graph, args.bereichswurzel) | {args.bereichswurzel}
        print(f"  {ab_graph.number_of_nodes()} Klassen, davon "
              f"{len(im_bereich)} im Bereich", file=sys.stderr)
        verkehrt = verkehrt_kandidaten(ab_graph, im_bereich, args.min_unterbau)

    # Labels erst jetzt, und nur fuer das, was gemeldet werden kann: der
    # ganze Graph waere ein Vielfaches an Abfragen fuer Klassen, die in
    # keinem Befund auftauchen. Bei der Abwaerts-Huelle waeren das ueber 3000
    # Klassen fuer eine Handvoll Treffer.
    zu_beschriften = (set(qids) | {p for _, p in kanten}
                      | {k for _, k in p31_kanten}
                      | {q for n, p, _, _ in verkehrt for q in (n, p)}
                      | set(direkt_allgemein))
    if elementdaten:
        zu_beschriften |= (set(ELEMENTKATEGORIEN) | set(GRUPPEN_QID.values())
                           | {LEICHTMETALL_QID, SCHWERMETALL_QID})
    print(f"Hole {len(zu_beschriften)} Bezeichnungen ...", file=sys.stderr)
    labels = hole_labels(sorted(zu_beschriften))

    befunde, luecken = [], {}   # luecken sammelt Basismetalle ohne Klasse
    if "kennzahlen" in args.pruefungen:
        befunde += kennzahlen(items, graph, p31_kanten, kinder,
                              unter_material, eingeordnet)
    if "zyklus" in args.pruefungen:
        befunde += pruefe_zyklen(graph, im_bereich, labels)
    if "redundant" in args.pruefungen:
        befunde += pruefe_redundant(graph, im_bereich,
                                    {(n, p) for n, p, _, _ in verkehrt},
                                    labels, args.max_umweg)
    if "verkehrt" in args.pruefungen:
        befunde += pruefe_verkehrt(verkehrt, labels)
    if "instanz-als-klasse" in args.pruefungen:
        befunde += pruefe_instanz_als_klasse(p31_kanten, kinder,
                                             unter_material | unter_legierung,
                                             labels)
    if "metaklasse" in args.pruefungen:
        # Kostet keine Abfrage: der Graph und die P31-Kanten stehen schon.
        befunde += pruefe_metaklasse(
            items, legierungs_items(graph, qids, p31_kanten), p31_kanten,
            ist_klasse, labels, args.metaklasse_auch_mit_p31)
    if "ohne-einordnung" in args.pruefungen:
        if POPULATIONEN[args.population]["pattern"] is None:
            treffer, luecken = pruefe_ohne_einordnung(
                items, eingeordnet, labels, ist_klasse, p31_werte)
            befunde += treffer
        else:
            print("  'ohne-einordnung' uebersprungen: nur fuer die Pruefliste "
                  "sinnvoll, in den SPARQL-Gruppen ist die Klassifikation "
                  "per Definition erfuellt.", file=sys.stderr)
    if "zusammensetzung" in args.pruefungen:
        print("Hole Elementbezeichnungen ...", file=sys.stderr)
        elementnamen = hole_elementnamen()
        # Erst alle Zusammensetzungen lesen, dann EINMAL die Legierungsklassen
        # zu den vorkommenden Basismetallen suchen. Andersherum waere es eine
        # SPARQL-Abfrage je Item.
        basen = set()
        for eintrag in direkt_allgemein.values():
            text = " ".join(filter(None, (eintrag.get("label_de"),
                                          eintrag.get("label_en"))))
            if "%" not in text:
                continue
            anteile, _ = lies_zusammensetzung(text, elementnamen)
            if anteile:
                basen.add(anteile[0][1])
        print(f"  {len(elementnamen)} Elementbezeichnungen, "
              f"{len(basen)} Basismetalle in den Namen", file=sys.stderr)
        if basen:
            klassen, element_luecken = finde_basisklassen(sorted(basen))
            luecken.update({b: g for b, g in element_luecken.items()})
            befunde += pruefe_zusammensetzung(direkt_allgemein, elementnamen,
                                              klassen, graph, labels)

    if "zu-allgemein" in args.pruefungen:
        elemente = hole_elemente(sorted(allgemein_baum))
        begriffe = baue_suchbegriffe(allgemein_baum, elemente)
        print(f"  {len(begriffe)} Suchbegriffe im Kandidatenpool "
              f"({len(elemente)} Elemente/Isotope ausgeschlossen), "
              f"{len(direkt_allgemein)} Items zu pruefen", file=sys.stderr)
        befunde += pruefe_zu_allgemein(
            direkt_allgemein, begriffe, graph, labels,
            {n for n, p, _, _ in verkehrt}, nur_name=args.beleg == "name")
    if "p31-neben-p279" in args.pruefungen:
        befunde += pruefe_p31_neben_p279(p31_kanten, kinder,
                                         set(direkt_allgemein), labels)
    if "parallelzweig" in args.pruefungen:
        befunde += pruefe_parallelzweig(items, unter_material, labels)
    if "elementklasse" in args.pruefungen:
        befunde += pruefe_elementklasse(items, elementdaten, labels,
                                        mit_dichte=not args.ohne_dichte)

    mengengeruest = (
        f"Mengengeruest: {len(items)} Items der Grundgesamtheit, "
        f"{graph.number_of_nodes()} Klassen, {graph.number_of_edges()} "
        f"P279-Kanten"
        + (f", {len(direkt_allgemein)} direkt unter einer allgemeinen Wurzel"
           if direkt_allgemein else "") + ".")

    bericht(befunde, luecken, ohne_item, args.vorsichtig)
    schreibe_empfehlung(befunde, empfehlung_pfad, args.population,
                        luecken, ohne_item, args.vorsichtig, mengengeruest)
    if csv_pfad:
        schreibe_csv(befunde, csv_pfad)
    schreibe_review_needed(befunde, args.review_needed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
