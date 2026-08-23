# Material class structure

Zwei Werkzeuge zur **Wikidata-Klassenhierarchie der Werkstoffe** — wie
`P279` („Unterklasse von") unterhalb von `material` (Q214609) und `Legierung`
(Q37756) tatsächlich verwendet wird.

| Skript | Was es tut | Ausgabe |
|---|---|---|
| **[Vorschläge generieren.py](Vorschläge%20generieren.py)** | prüft die Struktur auf zehn Arten und schreibt **eine gestaffelte Empfehlung** — vier Stufen nach Beweiskraft | `p279_empfehlung_<Zeitstempel>.txt` |
| **[visualisierung.py](visualisierung.py)** | prüft und **zeichnet**, wie Werkstoffe an der Wurzel hängen und welche über einen parallelen Zweig laufen | `werkstoff_check.csv`, `*.png` |

Die beiden ergänzen sich: die Visualisierung beantwortet **ob und wie** ein
Werkstoff an der Wurzel hängt, die Vorschlagsgenerierung, **was daran zu
ändern wäre**. Der Befund `parallelzweig` in der Empfehlung ist genau der,
den die Visualisierung als roten Knoten zeigt.

Beide brauchen `requests`; die Visualisierung zusätzlich `networkx` und
`matplotlib` (siehe [../requirements.txt](../requirements.txt)). Gestartet
wird aus dem Repo-Wurzelverzeichnis.

---

# Vorschläge generieren.py

Prüft, wie **P279** unterhalb der Werkstoffe verwendet wird, und schreibt
**eine gestaffelte Empfehlung** zum Durchsehen am Bildschirm.

Der [Benchmark](../benchmark/) misst, welche *Messwerte* an den
Werkstoff-Items fehlen. Dieses Werkzeug misst etwas anderes: ob die Items
überhaupt richtig **eingehängt** sind — wo die Kante fehlt, wo sie doppelt
ist, wo sie verkehrt herum zeigt und wo statt P279 fälschlich P31 steht.

Hier sind zwei Ansätze zusammengeführt: die Strukturprüfungen auf dem
P279-Graphen und die Label-Heuristik aus dem früheren
`material_subclass_check.py`, das darin aufgegangen ist.

```bash
python "Material class structure/Vorschläge generieren.py"
python "Material class structure/Vorschläge generieren.py" --population legierungen
python "Material class structure/Vorschläge generieren.py" --pruefungen redundant verkehrt
python "Material class structure/Vorschläge generieren.py" --pruefungen metaklasse
python "Material class structure/Vorschläge generieren.py" --tiefe 3 --beleg beides
python "Material class structure/Vorschläge generieren.py" --vorsichtig   # nichts einspielbar
```

Es entsteht **eine** Datei: `p279_empfehlung_<Zeitstempel>.txt`. Eine
Befund-CSV gibt es nur auf Wunsch (`--csv`).

## Die Staffelung

Vier Stufen, sortiert nach **Beweiskraft** — nicht nach Wichtigkeit. Du
kannst jederzeit aufhören; das Geprüfte bleibt gültig.

| Stufe | | Was das heißt |
|---|---|---|
| **1** | MECHANISCH SICHER | Folgt allein aus dem Graphen und behauptet nichts. **Als einzige ausführbar.** |
| **2** | STRUKTURELL BEGRÜNDET | Aus dem Graphen abgeleitet, aber mit einer fachlichen Entscheidung davor. Der Graph sagt, *dass* etwas nicht stimmt — nicht, wie herum es richtig wäre. |
| **3** | HEURISTISCH | Aus Bezeichnungen geraten. Fehltreffer sind hier die Regel. Diese Entwürfe haben **zwei Zeilen, und die erste entfernt die bestehende Einordnung**. |
| **4** | NUR MELDUNG | Beschreibt die Lage, fordert nichts. Ein Teil davon ist ausdrücklich *kein* Fehler. |

### Wie man das abarbeitet

Ab Stufe 2 trägt jeder Entwurf die Marke `#!`. QuickStatements liest sie als
Kommentar. Wer eine Zeile geprüft und für richtig befunden hat, löscht die
zwei Zeichen — im Editor findet die Suche nach `#!` genau die Entwürfe.

Alle übrigen Zeilen beginnen mit `#`. Die Datei lässt sich dadurch jederzeit
**als Ganzes** nach QuickStatements kopieren, ohne dass eine ungeprüfte Zeile
zur Aussage wird.

Jeder Vorschlag hat eine durchlaufende Nummer `[0042]` und einen direkten
Wikidata-Link, das Ziel steht mit Label und Link daneben:

```
# [0043] petit bronze   https://www.wikidata.org/wiki/Q105967812
#        Ziel: bronze   https://www.wikidata.org/wiki/Q34095
#        haengt direkt unter Q37756 (Legierung), obwohl name 'bronze'
#        nennt - dafuer gibt es Q34095.
#        Pruefen: Heuristik auf Wortgrenzen. Erst pruefen, ob der
#        Treffer sachlich passt - die erste Zeile ENTFERNT die
#        bestehende Einordnung.
#!-Q105967812	P279	Q37756
#!Q105967812	P279	Q34095
```

Die Stufe-3-Vorschläge sind **nach Zielklasse gruppiert**: alle „→ bronze"
stehen beieinander. Die Entscheidung fällt einmal für die Gruppe statt
zwölfmal einzeln, und ein systematischer Fehlgriff der Heuristik fällt als
Block auf statt verstreut.

## Die elf Prüfungen

| Prüfung | Findet | Stufe |
|---|---|---|
| `kennzahlen` | wie P279 überhaupt benutzt wird: P279, P31, beides, keines; Mehrfacheltern | Kopf |
| `redundant` | Kante, die über einen anderen Elter ohnehin gilt | **1** |
| `instanz-als-klasse` | Item mit P31 auf eine Werkstoffklasse, das selbst Unterklassen hat | 2 |
| `metaklasse` | Legierung ohne chemische Metaklasse (`P31 = Q119892838`) | 2 |
| `verkehrt` | Kante `n → p`, obwohl unter `n` mehr hängt als unter `p` ohne `n` | 2 |
| `zyklus` | eine Klasse ist über P279 ihre eigene Oberklasse | 2 |
| `zusammensetzung` | der Name nennt die Zusammensetzung — das Element mit dem größten Anteil ist das Basismetall | 3 |
| `zu-allgemein` | Item hängt direkt unter einer sehr allgemeinen Klasse, obwohl seine Bezeichnung eine speziellere nennt | 3 |
| `ohne-einordnung` | benannte Legierung ohne jeden Pfad zu `Legierung` (Q37756) | 3 |
| `p31-neben-p279` | Item direkt unter einer allgemeinen Klasse, zusätzlich mit P31 | 4 |
| `parallelzweig` | Item ohne P279\*-Pfad zu `material` (Q214609) — **kein Fehler** | 4 |

Alle Prüfungen bleiben in der **Werkstoff-Ecke** (unter `material` oder
`Legierung`, plus die Grundgesamtheit selbst). Das ist keine Bequemlichkeit:
die P279-Hülle nach oben endet zwangsläufig in der obersten Ontologie, und
dort finden dieselben Prüfungen dieselben Fehler bei „Begriff", „Typ" oder
„Kunstgewerbe". Die Befunde wären richtig und trotzdem nicht unsere Sache —
eine dort eingespielte Änderung trifft hunderttausende Items ohne jeden
Werkstoffbezug.

## Drei Sperren gegen den eigenen Unsinn

Die Prüfungen widersprechen sich, wenn man sie einzeln laufen lässt. Beim
Bauen fällt das nicht auf, beim Einspielen schon:

1. **Eine Redundanz, deren Ersatzpfad über eine beanstandete Kante läuft,
   ist keine.** `Ferrolegierung P279 Legierung` sieht redundant aus, weil es
   über *ferrous metal → Metalle → Legierung* auch so geht — aber der letzte
   Schritt ist die falsch modellierte Kante. Wer die direkte entfernt und
   später die falsche repariert, hat Ferrolegierung aus dem Legierungsbaum
   geworfen. Solche Befunde heißen `redundant-unsicher` und rutschen in
   Stufe 2. Gibt es einen *zweiten*, unbelasteten Ersatzpfad, gewinnt der.
2. **Eine beanstandete Klasse taugt nicht als Ziel einer Umhängung.** Sonst
   schlägt dasselbe Skript vor, „Orgelmetall" unter Q11426 zu hängen —
   ausgerechnet die Klasse, deren Platz Stufe 2 in Frage stellt.
3. **Chemische Elemente (P1086) taugen nie als Ziel.** Ein Werkstoff ist
   keine Unterklasse des *Elements* Kupfer. Sie stehen nur wegen der
   falschen Metall/Legierung-Kante im Kandidatenpool — ohne diesen Filter
   zielten 32 % der Heuristik-Vorschläge auf copper, aluminium oder nickel.

## Die schiefe Kante Metall → Legierung

Wikidata führt „Metall" (Q11426) als **Unterklasse von** „Legierung"
(Q37756) — fachlich verkehrt herum. Dadurch hängt jedes Metall samt Isotopen
unter „Legierung"; [materialswiki](../materialswiki/) gleicht das mit einem
Filter aus (`LEGIERUNG_OHNE_ELEMENTE`). Der Filter kuriert das Symptom, die
Kante bleibt.

Die Prüfung `verkehrt` findet sie generisch. Die naive Messung „Unterbau von
`n` größer als Unterbau von `p`" kann nie ausschlagen — die Kante `n → p`
macht alles unter `n` automatisch auch zu etwas unter `p`. Gemessen wird
deshalb der **eigene** Unterbau von `p`, also ohne den Teil, den `p` nur über
`n` hat. Bei Metall/Legierung fällt das drastisch aus: **3005 zu 237**.

Dafür wird der Klassenbaum unter `--bereichswurzel` (Vorgabe: Q37756)
vollständig nach unten geholt. Nur dort stimmen die gezählten
Unterbaugrößen mit den echten überein. `material` (Q214609) taugt nicht als
Bereichswurzel: darunter hängen rund 936.000 Klassen.

## Basismetall aus der Zusammensetzung (`zusammensetzung`)

Viele Items tragen ihre Zusammensetzung im Namen:

> Nickel brass **(70% Copper, 18% Zinc, 12% Nickel)**

Daraus folgt das Basismetall zwingend — es ist das Element mit dem größten
Anteil — und damit die Legierungsklasse: hier *Kupferlegierung* (Q518350).
Das ist die belastbarste Namensauswertung im Skript: sie **rechnet**, statt
zu raten. Deshalb steht sie in Stufe 3 vor der Namensähnlichkeit, mit eigenem
Gruppenkopf.

Erkannt werden beide Schreibweisen — `90% Copper` und `Aluminium 98%` —
Dezimalpunkt wie -komma, Groß- und Kleinschreibung. Die Elementnamen kommen
**aus Wikidata**, samt Aliassen und Symbolen; eine handgepflegte Liste im
Quelltext wäre eine zweite Wahrheit neben der Datenbank. Ohne die Aliasse
fiele jedes US-`Aluminum` durch.

Drei Fälle bekommen **keinen** Vorschlag, nur eine Meldung:

| Fall | Beispiel | Warum |
|---|---|---|
| `Plating:` | `Brass plated steel (Plating: 72.5% Copper, 27.5% Zinc)` | Die Prozente gelten der **Auflage**, nicht dem Item. Das ist Stahl mit Messingauflage, kein Kupferwerkstoff. |
| Kein klarer Sieger | `Copper clad aluminium (48% Copper, 52% Aluminium)` | 4 Prozentpunkte Abstand — da entscheidet eine Nachkommastelle. Schwelle: `MIN_ABSTAND_PROZENT` |
| Keine Klasse | Basismetall Eisen | *Ferrous alloy* existiert in Wikidata nicht (siehe unten). |

Ein vierter Fall bekommt einen Vorschlag **mit Warnung**: Schichtverbunde
(`plated`, `clad`, `centre in … ring`). Die Prozente stimmen dort für den
Körper, aber ein Verbund ist keine Legierung.

Bestandteile, die keine chemischen Elemente sind — `27.5% Steel`,
`Other Metals 2%` — gehen nicht als Basismetall durch, verschwinden aber
auch nicht: sie stehen als „Nicht zugeordnet" in der Begründung.

## Chemische Metaklasse (P31) für Legierungen

*Diese Prüfung stand bis 2026-08-23 in [materialswiki](../materialswiki/) und
ist hierher gewandert: sie folgt aus dem Klassengraphen, den dieses Skript
ohnehin im Speicher hält — dort kostet sie **keine einzige zusätzliche
Abfrage**, während materialswiki sich eine eigene SPARQL-Runde je Charge
erkaufen musste.*

[[Wikidata:WikiProject Chemistry/Guidelines/Basic metaclasses and relations]]
verlangt an **jedem** Item einer chemischen Entität genau **eine** Metaklasse
über `P31` — und für Gemische ausdrücklich eine eigene, nicht die der reinen
Stoffe:

> For mixtures and parts of chemical entities, other metaclasses are used.

Eine Legierung *ist* ein Gemisch (`Q37756`: „mixture or metallic solid
solution"). Die Metaklasse ist damit bestimmt und muss nicht geraten werden:
**`Q119892838`** („definiertes Gemisch chemischer Substanzen" / *type of
mixture of chemical entities*). Sie ist im Bestand etabliert — 189 Items
tragen sie, darunter Salzsäure, Backpulver und Terpentin. `Q119896085` ist
ihre einzige Untermetaklasse und meint Polymere, für Legierungen also nichts.

Was die Prüfung **nicht** tut: eine *inhaltliche* Einordnung vorschlagen
(„Kupferlegierung", „Werkzeugstahl"). Die bleibt eine fachliche Entscheidung
und fällt in `ohne-einordnung` und `zusammensetzung`.

Am Bestand gemessen (2026-08-21, 1082 Items der Gruppe `legierungen`):

| Fall | Items | Ergebnis |
|---|---|---|
| Legierung ohne jedes `P31` | 313 | Entwurf `metaklasse` |
| trägt schon `P31`, aber keine Metaklasse | 565 | nichts — siehe unten |
| trägt eine **andere** Chemie-Metaklasse | 10 | Meldung `metaklasse-konflikt` |
| trägt `Q119892838` bereits | 3 | nichts |
| gar keine Legierung, nur über `Q11426` eingehängt | 181 | nichts |
| Mineralart | 9 | nichts |

**Warum die 565 standardmäßig ausbleiben.** Dort steht meist eine richtige
Klassenzugehörigkeit (`P31 = Legierung`, `P31 = Aluminiumlegierung`); die
Metaklasse käme als **zweite** `P31`-Aussage daneben. Die Guideline will das,
aber es ist eine Massenänderung — und in genau dieser Menge sitzen die Fälle,
die gar keine Werkstoffe sind: `Q26709` Stahlrohr (ein Rohr), `Q898562`
Inconel und `Q734159` Glidcop (als Markenzeichen modelliert).
`--metaklasse-auch-mit-p31` nimmt sie dazu, dann sind es 878 Entwürfe. Wie
viele der Standardlauf so ausspart, meldet er auf stderr.

**Die falsche Metaklasse wird nicht überschrieben.** Zehn Legierungen tragen
`Q113145171` („definierte chemische Substanz"), darunter **Messing**,
Aluminiumbronze und Siliciumgermanium. Für ein Gemisch ist das die falsche,
und die Guideline lässt nur eine zu — die bestehende müsste also weichen. Zu
*entfernen* ist Handarbeit; der Befund `metaklasse-konflikt` geht deshalb ohne
Entwurf raus, mit der vorhandenen Metaklasse in der Begründung.

**„Metalle" (`Q11426`) bekommt nichts.** Es ist der Ausgangspunkt des
Modellierungsfehlers (siehe [Die schiefe Kante Metall →
Legierung](#die-schiefe-kante-metall--legierung)) und hängt nur über die
defekte Kante unter der Legierung. Ebenso bleiben die 181 Sammelbegriffe außen
vor, die dieselbe Kante hereinspült — Alkalimetalle, Übergangsmetalle, „metals
of antiquity". Geprüft wird, ob das Item die Legierung **ohne den Umweg über
`Q11426`** erreicht: der Knoten wird aus dem Graphen genommen, dann zählt, was
`Q37756` noch erreicht. Ein simples „hat gar keinen Metall-Weg" reicht nicht:
Stahl hat einen, kommt aber außerdem über Ferrolegierung an die Legierung
heran.

**Mineralarten bleiben außen vor.** Gediegene Metalle und Amalgame (Taenit,
Kolymit, Bleiamalgam …) sind über die IMA modelliert (`P31 = Q12089225`). Ob
dort zusätzlich eine Chemie-Metaklasse hingehört, entscheidet das
Mineralprojekt, nicht dieses Werkzeug.

**Warum Stufe 2 und nicht Stufe 1.** Die Metaklasse folgt zwar zwingend aus
der Klassenzugehörigkeit — aber ob das Item *wirklich* eine Legierung ist,
sagt der Graph nicht. Genau daran hängt der ganze Befund, und genau dort steckt
der Schrott (siehe die 565 oben). Also: Entwurf mit `#!`, Freigabe von Hand.

**Die reinen Stoffe bleiben offen.** Für sie widerspricht sich die Guideline
mit der Projektseite; siehe [Bewusst offen: die Metaklasse der reinen
Stoffe](../materialswiki/README.md#bewusst-offen-die-metaklasse-der-reinen-stoffe).

## Die Label-Heuristik (`zu-allgemein`)

Die Idee aus `material_subclass_check.py`: ein Item, das direkt unter einer
sehr allgemeinen Klasse hängt, trägt seine eigentliche Oberklasse oft im
Namen — „Formgedächtnis**keramik**" unter *Material*, obwohl es *Keramik*
gibt.

Die Idee trägt, aber nur mit Filtern. Gemessen an 325 Vorschlägen der
Vorlage (2026-08-23):

* **42 %** zielten auf Q16829513, ein *zweites* Item namens „material", das
  selbst unter Q214609 hängt — ein Synonym, keine Spezialisierung.
  → `ALLGEMEINE_BEZEICHNUNGEN`
* **60 %** stützten sich allein auf die Beschreibung. Dass dort das Wort
  „material" vorkommt, sagt nichts über die Klasse. → `--beleg` (Vorgabe:
  nur der Name)
* Reine Substring-Zufälle: „Mater" traf in „**Mater**ial", „compo" in
  „**compo**site", „Stoff" in „Inhalts**stoff**". → Suche auf **Wortgrenzen**

Was auch mit Filtern nicht geht: „brass plated steel" ist kein *Messing*,
sondern Stahl mit Messingauflage. Solche Verbundbezeichnungen kann eine
Namensheuristik nicht auflösen — dafür ist Stufe 3 als Ganzes gekennzeichnet.

**Kandidatenpool:** bis zur Ebene `--tiefe` (Vorgabe 2) unter den allgemeinen
Wurzeln. Größenordnung unter `material`: Ebene 1 → 392, Ebene 2 → 5.787,
Ebene 3 → 14.974. Der volle Baum hat 936.891 Items, ist in einer Abfrage
nicht holbar — daran ist die Vorlage mit *502 Bad Gateway* abgebrochen — und
wäre als Pool auch nicht sinnvoll: weiter unten stehen einzelne Mineralien
und Handelsprodukte, ein Treffer gegen die wäre fast immer Zufall.

## Grundgesamtheiten (`--population`)

| Name | Menge |
|---|---|
| `benannte-legierungen` (Vorgabe) | die Prüfliste aus [[en:List of named alloys]] |
| `legierungen` | Legierungen unter Q37756, ohne Elemente und Isotope |
| `metallischer-werkstoff` | unterhalb von Q1924900 |
| `material` | unterhalb von Q214609 |

Die Muster kommen aus [materialswiki/cli.py](../materialswiki/cli.py) — sie
werden importiert, nicht kopiert, damit dieses Werkzeug und der
Vorschlagslauf garantiert dieselbe Menge meinen.

### Die Prüfliste löst Weiterleitungen auf

Die Zuordnung Listentitel → Item läuft über die enwiki-Seiten-API **mit
`redirects=1`**, nicht über den rohen Titel. Der Unterschied ist groß: die
Liste verlinkt Weiterleitungen — *Nitinol → Nickel titanium*, *German silver
→ Nickel silver*, *Heusler alloy → Heusler compound*, *Lockalloy →
Beryllium-aluminium alloy*. Ohne Auflösung gelten deren Items als „nicht
vorhanden"; so entstand der frühere Befund von 25 angeblich itemlosen Namen.
Tatsächlich sind es drei.

Ein Labelabgleich wäre die falsche Alternative — bei „Mulberry" oder
„Elektron" greift der munter daneben.

### Basismetall → Legierungsklasse

Für `ohne-einordnung` wird zu jedem Basismetall der Liste die passende
Klasse **gesucht, nicht geraten**: über die englische Bezeichnung nach
mehreren Mustern (`zinc alloy`, `nickel-based alloy` …), und es zählt nur,
was selbst unter Q37756 hängt.

Wo keine existiert, wird das als Lücke gemeldet statt als Fehler — anlegen
kann dieses Werkzeug nichts. Prominentester Fall ist **Iron**:
[[Wikidata:WikiProject Materials]] nennt *Ferrous alloy* als Beispiel für die
gewünschte Zwischenklasse, in Wikidata existiert sie nicht. Q907347
*ferroalloy* ist **nicht** dasselbe — das sind Vorlegierungen für die
Stahlherstellung (Ferrochrom, Ferromangan), nicht die Oberklasse aller
Eisenwerkstoffe.

## Grenzen

* Es wird **nie** nach Wikidata geschrieben. Das Werkzeug erzeugt eine
  Empfehlung, sonst nichts.
* Es legt **keine Items an**. Fehlende Klassen und Listeneinträge ohne Item
  stehen im Anhang der Empfehlung.
* Ein Teil der Meldungen aus `ohne-einordnung` ist zu Recht keine Legierung:
  Titannitrid, Titancarbid und Uranhydrid sind Verbindungen.
* Der vollständige Abwärts-Baum unter Q37756 umfasst rund 3.400 Klassen und
  wird rundenweise geholt — ein Lauf dauert dadurch einige Minuten.

---

# visualisierung.py

Prüft und zeichnet, wie Werkstoffe in der Wikidata-Klassenhierarchie unter
`material` (Q214609) hängen — und macht sichtbar, welche stattdessen über
einen **parallelen Zweig** laufen.

## Der strukturelle Befund

Aus den Constraint-Definitionen von `P186` „made from material" abgeleitet:

> Wikidata modelliert `material` (Q214609) **nicht** als gemeinsame Oberklasse
> aller Werkstoffe. `P186` erlaubt mehrere **gleichrangige** Werttypen
> nebeneinander: material (Q214609), alloy (Q37756), chemical compound
> (Q11173), chemical element (Q11344), substance (Q10683158), building
> material (Q206615), food (Q2095), physical object (Q223557) …

Eine Legierung (Edelstahl) oder eine chemische Verbindung (Siliciumcarbid)
braucht also **keinen** `P279*`-Pfad bis Q214609, um korrekt eingeordnet zu
sein — sie hängt an einer parallelen Klassenhierarchie. Ein „kein Pfad"-Befund
ist deshalb nicht automatisch ein Fehler, aber für eine materialorientierte
Auswertung überraschend. Genau das prüft dieses Skript empirisch.

Das ist auch die Begründung dafür, dass `parallelzweig` in der Empfehlung
nebenan in **Stufe 4** steht: gemeldet, aber ohne Entwurf.

Praktische Folge für [../benchmark/](../benchmark/): dessen Grundgesamtheit
muss Instanzen **und** Unterklassen vereinigen, sonst zählt sie an den
tatsächlich modellierten Werkstoffen vorbei.

## Nutzung

```bash
# Standardlauf: Werkstoff-Check der Default-Liste + Trace-Matrix
python "Material class structure/visualisierung.py"

# eigene Werkstoffliste
python "Material class structure/visualisierung.py" \
    --materials Stahl Titan Beton Diamant PVC

# Pfade einzelner QIDs nach oben verfolgen, alle in einem Graphen
python "Material class structure/visualisierung.py" \
    --trace Q11427 Q39782 --trace-out trace_werkstoffe_material.png
```

Die vier `trace_<gruppe>_<achse>.png` erzeugt der **Standardlauf** mit, aus
`TRACE_GROUPS` × `TRACE_ROOTS` oben im Skript. Vorher entstanden sie nur aus
Hand-Aufrufen von `--trace`, deren QID-Listen nirgends festgehalten waren —
dadurch veralteten die Bilder still, sobald jemand nur den Standardlauf
startete. `--skip-traces` schaltet sie ab, `--trace` bleibt für Einzelfälle.

| Gruppe \ Achse | `material` (Q214609) | `chemie` (Q79529) |
|---|---|---|
| `werkstoffe` (12 QIDs) | `trace_werkstoffe_material.png` | `trace_werkstoffe_chemie.png` |
| `elemente` (10 QIDs) | `trace_elemente_material.png` | `trace_elemente_chemie.png` |

Beide Achsen nebeneinander zu fahren ist der eigentliche Zweck: erst der
Vergleich zeigt, ob ein fehlender Pfad ein Modellierungsloch ist oder bloß
der andere der beiden gleichrangigen Zweige.

| Option | Bedeutung |
|---|---|
| `--materials` | zu prüfende Werkstoffe (Standard: 22 Stück — Stahl, Edelstahl, Titan, Aluminium, Beton, Glas, Diamant, Polyethylen, PVC, Siliciumcarbid, Holz, Kupfer, Messing, Bronze, Gusseisen, Keramik, Graphit, Magnesium, Wolframcarbid, Polyamid, Epoxidharz, Naturkautschuk) |
| `--tree` | zusätzlich `subclass_tree_material.png` zeichnen (standardmäßig **aus**, siehe unten) |
| `--skip-traces` | die `trace_<gruppe>_<achse>.png`-Matrix überspringen |
| `--depth` | Tiefe des Subclass-Baums (Standard 1 = die 413 direkten Subklassen, vollständig) |
| `--max-nodes` | Obergrenze für Knoten im Baum (Standard 500) |
| `--trace` | statt des Standardlaufs: die Pfade einer oder mehrerer QIDs hinauf zur Wurzel zeigen |
| `--trace-root` | Zielwurzel für `--trace` (Standard `Q214609` material; z.B. `Q79529` für die chemische Achse) |
| `--trace-out` | Ausgabedatei für den Trace-Graphen (Standard `trace_graph.png`) |

**QIDs direkt angeben**, wo es auf Genauigkeit ankommt: die Labelsuche löst
z.B. „Stahl" auf `Q1236029` (Familienname) auf statt auf den Werkstoff
`Q11427`. Genau dieser Fall steht als `AUFFAELLIG` in der Beispiel-CSV.

Der volle Baum unter Q214609 umfasst rund **936.000 Klassen** — weder in einer
Abfrage holbar noch als Bild lesbar. Ab `--depth 2` liefert `--max-nodes`
zwangsläufig einen Ausschnitt, und der ist willkürlich: er beantwortet die
eigentliche Frage nicht, wie ein *bestimmter* Werkstoff an der Wurzel hängt —
dafür sind die Trace-Graphen da. Deshalb ist `subclass_tree_material.png`
seit jeher optional und wird nur noch mit `--tree` gezeichnet.

## Ausgabedateien

Alle sind gitignoriert. `werkstoff_check.csv`, `werkstoff_graph.png` und (mit
`--tree`) `subclass_tree_material.png` landen wie im übrigen Repo im
**aktuellen Arbeitsverzeichnis**; die `trace_*.png` der Matrix schreibt der
Standardlauf dagegen **neben das Skript**, damit genau die Dateien
überschrieben werden, die dort schon liegen — sonst veralten sie wieder,
sobald jemand aus dem Repo-Wurzelverzeichnis startet. `--trace` folgt
weiterhin `--trace-out`.

| Datei | Inhalt |
|---|---|
| `werkstoff_check.csv` | eine Zeile je geprüftem Werkstoff: `input`, `qid`, `label`, `status`, `via_subclass_of`, `via_instance_of`, `direct_instance_of`, `direct_subclass_of` |
| `werkstoff_graph.png` | die geprüften Werkstoffe mit ihrer tatsächlichen Anbindung (rot = kein Pfad zu Q214609, grün = Pfad vorhanden) |
| `subclass_tree_material.png` | nur mit `--tree`: Subclass-Hierarchie unter Q214609, begrenzt durch `--depth` / `--max-nodes` |
| `trace_<gruppe>_<achse>.png` | Pfad-Graphen der Matrix `TRACE_GROUPS` × `TRACE_ROOTS` (Standardlauf) |
| `trace_graph.png` | Pfad-Graph eines Einzelaufrufs mit `--trace` (Name über `--trace-out`) |

Status in der CSV ist entweder `OK (Pfad zu material vorhanden)`,
`AUFFAELLIG (kein Pfad zu material)` oder `NICHT_GEFUNDEN`, wenn die
Labelsuche nichts liefert.
