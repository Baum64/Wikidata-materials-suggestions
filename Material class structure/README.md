# Material class structure

Zwei Werkzeuge zur **Wikidata-Klassenhierarchie der Werkstoffe** — wie
`P279` („Unterklasse von") unterhalb von `material` (Q214609) und `Legierung`
(Q37756) tatsächlich verwendet wird.

| Skript | Was es tut | Ausgabe |
|---|---|---|
| **[ClassCheck.py](ClassCheck.py)** | prüft die Struktur auf zwölf Arten und schreibt **eine gestaffelte Empfehlung** — vier Stufen nach Beweiskraft | `proposals/qs_class_<Population>_<Zeitstempel>.txt` |
| **[visualisierung.py](visualisierung.py)** | prüft und **zeichnet**, wie Werkstoffe an der Wurzel hängen und welche über einen parallelen Zweig laufen; mit `--szenario` zusätzlich Periodensystem, Legierungen und Minerale | `werkstoff_check.csv`, `*.png` |

Die beiden ergänzen sich: die Visualisierung beantwortet **ob und wie** ein
Werkstoff an der Wurzel hängt, die Vorschlagsgenerierung, **was daran zu
ändern wäre**. Der Befund `parallelzweig` in der Empfehlung ist genau der,
den die Visualisierung als roten Knoten zeigt.

Beide brauchen `requests`; die Visualisierung zusätzlich `networkx` und
`matplotlib` (siehe [../requirements.txt](../requirements.txt)). Gestartet
wird aus dem Repo-Wurzelverzeichnis.

---

# ClassCheck.py

Prüft, wie **P279** unterhalb der Werkstoffe verwendet wird, und schreibt
**eine gestaffelte Empfehlung** zum Durchsehen am Bildschirm.

Der [Benchmark](../benchmark/) misst, welche *Messwerte* an den
Werkstoff-Items fehlen. Dieses Werkzeug misst etwas anderes: ob die Items
überhaupt richtig **eingehängt** sind — wo die Kante fehlt, wo sie doppelt
ist, wo sie verkehrt herum zeigt und wo statt P279 fälschlich P31 steht.

Hier sind zwei Ansätze zusammengeführt: die Strukturprüfungen auf dem
P279-Graphen und die Label-Heuristik aus dem früheren
`material_subclass_check.py`, das darin aufgegangen ist.

Kurz über den Sammelbefehl (`python -m lauf`) — deckt jede Grundgesamtheit ab
und schreibt nach `proposals/`:

```bash
python -m lauf struktur benannte-legierungen
python -m lauf struktur material --limit 500
python -m lauf struktur periodensystem -- --ohne-dichte
```

Direkt:

```bash
python "Material class structure/ClassCheck.py"
python "Material class structure/ClassCheck.py" --population legierungen
python "Material class structure/ClassCheck.py" --pruefungen redundant verkehrt
python "Material class structure/ClassCheck.py" --pruefungen metaklasse
python "Material class structure/ClassCheck.py" --tiefe 3 --beleg beides
python "Material class structure/ClassCheck.py" --vorsichtig   # nichts einspielbar
```

Es entsteht **eine** Datei: `proposals/qs_class_<Population>_<Zeitstempel>.txt`. Eine
Befund-CSV gibt es nur auf Wunsch (`--csv`).

## Die Staffelung

Vier Stufen, sortiert nach **Beweiskraft** — nicht nach Wichtigkeit. Du
kannst jederzeit aufhören; das Geprüfte bleibt gültig.

| Stufe | | Was das heißt |
|---|---|---|
| **1** | MECHANISCH SICHER | Folgt allein aus dem Graphen und behauptet nichts. **Als einzige ausführbar.** |
| **2** | STRUKTURELL BEGRÜNDET | Aus dem Graphen abgeleitet, aber mit einer fachlichen Entscheidung davor. Der Graph sagt, *dass* etwas nicht stimmt — nicht, wie herum es richtig wäre. |
| **3** | GERECHNET ODER GERATEN | Aus einer Bezeichnung oder einem Messwert gegen eine Konvention. Fehltreffer sind hier die Regel. Was aus einer Bezeichnung kommt, hat **zwei Zeilen, und die erste entfernt die bestehende Einordnung**. |
| **4** | NUR MELDUNG | Beschreibt die Lage, fordert nichts. Ein Teil davon ist ausdrücklich *kein* Fehler. |

### Wie man das abarbeitet

**Freigeben heißt: ein Zeichen löschen.** Ab Stufe 2 steht jeder Entwurf als
`#Q123<TAB>P279<TAB>Q456` da — ein einzelnes `#` davor, **ohne Leerzeichen**.
QuickStatements liest es als Kommentar; wer die Zeile geprüft und für richtig
befunden hat, löscht genau dieses eine Zeichen.

Fließtext trägt dagegen immer `# ` **mit** Leerzeichen. Im Editor findet die
Suche nach `#Q` und `#-Q` deshalb trotzdem genau die Entwürfe — und die Datei
lässt sich jederzeit **als Ganzes** nach QuickStatements kopieren, ohne dass
eine ungeprüfte Zeile zur Aussage wird.

Ein Vorschlag ist in der Regel **zwei Zeilen**: eine Kopfzeile mit
durchlaufender Nummer `[0042]`, Bezeichnung, Wikidata-Link und Begründung,
darunter der Entwurf. Zielklasse, Ziellink und Prüfanweisung stehen einmal im
Gruppenkopf, nicht in jedem Eintrag:

```
#   -> ZIEL bronze  https://www.wikidata.org/wiki/Q34095   (12 Items)
#      Pruefen (alle 12): Heuristik auf Wortgrenzen. Erst pruefen, ob der
#      Treffer sachlich passt - die erste Zeile ENTFERNT die bestehende
#      Einordnung.
# [0043] petit bronze https://www.wikidata.org/wiki/Q105967812 | haengt direkt
#        unter Q37756 (Legierung), obwohl der Name 'bronze' nennt.
#-Q105967812	P279	Q37756
#Q105967812	P279	Q34095
```

Für die 118 Elemente sind das rund **600 Zeilen statt rund 1130**.

### Gegliedert nach Eigenschaft, nicht nach Item

Innerhalb einer Stufe steht die **Eigenschaft** ganz oben, darunter die
Befundart, darunter das **Ziel**:

```
# ====================================================================
# EIGENSCHAFT P279 - Unterklasse von  (51)
# ====================================================================

# --- Elementkategorie fehlt (48) - NACHGERECHNET: ... ---
#
#   -> Uebergangsmetalle (Q19588): 12 Item(s)
#      Pruefen (gilt fuer alle 12): Die Zuordnung folgt aus der
#      Ordnungszahl und ist nachrechenbar. ...
```

Der Grund ist der Arbeitsablauf. Nach Item sortiert steht dieselbe
Überlegung hundertmal neu da; nach Eigenschaft und Ziel sortiert steht
einmal „diese 12 Items werden Übergangsmetalle" — die Entscheidung fällt
einmal für die Gruppe, und ein systematischer Fehlgriff fällt als Block auf
statt verstreut. Die Eigenschaft steht deshalb ganz oben, weil sie bestimmt,
*was beim Freigeben passiert*: eine P279-Zeile hängt um, eine P31-Zeile
klassifiziert, eine P361-Zeile ordnet ein Teil einem Ganzen zu.

Trägt jeder Vorschlag einer Zielgruppe dieselbe Prüfanweisung, steht sie
einmal im Gruppenkopf statt in jedem Eintrag. Der Kopf der Datei zählt die
Befunde zusätzlich nach Eigenschaft auf, die `--csv` ist ebenso sortiert.

## Die zwölf Prüfungen

| Prüfung | Findet | Stufe |
|---|---|---|
| `kennzahlen` | wie P279 überhaupt benutzt wird: P279, P31, beides, keines; Mehrfacheltern | Kopf |
| `redundant` | Kante, die über einen anderen Elter ohnehin gilt | **1** |
| `instanz-als-klasse` | Item mit P31 auf eine Werkstoffklasse, das selbst Unterklassen hat | 2 |
| `metaklasse` | Legierung ohne chemische Metaklasse (`P31 = Q119892838`) — Entwurf nur, wenn das Item **keine** Klasse ist | 2 / 4 |
| `verkehrt` | Kante `n → p`, obwohl unter `n` mehr hängt als unter `p` ohne `n` | 2 |
| `zyklus` | eine Klasse ist über P279 ihre eigene Oberklasse | 2 |
| `zusammensetzung` | der Name nennt die Zusammensetzung — das Element mit dem größten Anteil ist das Basismetall | 3 |
| `zu-allgemein` | Item hängt direkt unter einer sehr allgemeinen Klasse, obwohl seine Bezeichnung eine speziellere nennt | 3 |
| `ohne-einordnung` | benannte Legierung ohne jeden Pfad zu `Legierung` (Q37756) — Entwurf nur, wenn das Item **keine** reine Instanz ist | 3 / 4 |
| `p31-neben-p279` | Item direkt unter einer allgemeinen Klasse, zusätzlich mit P31 | 4 |
| `parallelzweig` | Item ohne P279\*-Pfad zu `material` (Q214609) — **kein Fehler** | 4 |
| `elementklasse` | nur im Szenario `periodensystem`: fehlende Elementkategorie, fehlende Gruppe, Leicht-/Schwermetall aus der Dichte | 2 / 3 / 4 |

Alle Prüfungen bleiben in der **Werkstoff-Ecke** (unter `material` oder
`Legierung`, plus die Grundgesamtheit selbst). Das ist keine Bequemlichkeit:
die P279-Hülle nach oben endet zwangsläufig in der obersten Ontologie, und
dort finden dieselben Prüfungen dieselben Fehler bei „Begriff", „Typ" oder
„Kunstgewerbe". Die Befunde wären richtig und trotzdem nicht unsere Sache —
eine dort eingespielte Änderung trifft hunderttausende Items ohne jeden
Werkstoffbezug.

## Vier Sperren gegen den eigenen Unsinn

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
4. **Klasse und Instanz werden vor jedem Entwurf getrennt.**
   [[Help:Basic membership properties]] sagt, woran eine Klasse zu erkennen
   ist: sie hat `P279` oder eigene Unterklassen. Daraus folgt beides —
   **an eine Werkstoffklasse schreibt dieses Werkzeug kein `P31`**, und
   **an eine Instanz kein `P279`**. Wo der Graph die Klassenzugehörigkeit
   nicht hergibt, entsteht eine Meldung statt eines Entwurfs. Das kostet
   `metaklasse` und `ohne-einordnung` ihre Massenentwürfe — siehe
   [Chemische Metaklasse](#chemische-metaklasse-p31-für-legierungen).

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
| Legierung ohne jedes `P31` (also über `P279` drin → **Klasse**) | 313 | Meldung `metaklasse-klasse`, **kein Entwurf** |
| trägt schon `P31`, aber keine Metaklasse | 565 | nichts — siehe unten |
| trägt eine **andere** Chemie-Metaklasse | 10 | Meldung `metaklasse-konflikt` |
| trägt `Q119892838` bereits | 3 | nichts |
| gar keine Legierung, nur über `Q11426` eingehängt | 181 | nichts |
| Mineralart | 9 | nichts |

**Kein `P31` an eine Werkstoffklasse.** Das ist die schärfste Regel dieser
Prüfung, und sie kostet sie ihre Entwürfe. [[Help:Basic membership
properties]] sagt, woran eine Klasse zu erkennen ist: sie hat `P279` oder
eigene Unterklassen. Genau so sind die 313 oben in die Gruppe gekommen — über
`P279`. Ein `P31` würde ihnen anhängen, dass das *Ding selbst* ein definiertes
Gemisch chemischer Substanzen **ist**; belegt ist aus dem Graphen aber nur,
dass es irgendwo unter `Q37756` hängt. Und dort ist die Kante schief (siehe
[Die schiefe Kante](#die-schiefe-kante-metall--legierung)): ein falsches
`P279` fällt später als schiefe Kante auf, ein falsches `P31` auf eine
Metaklasse liest niemand mehr nach. Also: Meldung, kein Entwurf.

Entworfen wird nur noch, wo das Item **keine** Klasse ist — weder `P279` noch
Unterklassen. Wer das erfüllt, ist über `P31` in die Gruppe gekommen und trägt
also bereits eines; die Entwürfe liegen damit vollständig hinter
`--metaklasse-auch-mit-p31`. Ohne den Schalter ist `metaklasse` seit
2026-08-24 **eine reine Meldung** und steht in Stufe 4.

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

**Warum die Entwürfe nie Stufe 1 erreichen.** Die Metaklasse folgt zwar
zwingend aus der Klassenzugehörigkeit — aber ob das Item *wirklich* eine
Legierung ist, sagt der Graph nicht. Genau daran hängt der ganze Befund, und
genau dort steckt der Schrott (siehe die 565 oben). Also: Entwurf mit `#`,
Freigabe von Hand — und für Klassen gar keiner.

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
| `metallischer-werkstoff` | Klassen unterhalb von Q1924900 — **braucht `--limit N`** (die Abfrage läuft sonst ins Timeout) |
| `material` | Klassen unterhalb von Q214609 — **braucht `--limit N`**; der volle Baum hat rund 936.000 Klassen, in einer Abfrage nicht holbar. Beide Wurzeln liefern nur die *Klassen* (`P279*`), nicht zusätzlich jede Instanz jeder Unterklasse |
| `oxide` | Oxide mit Summenformel unter Q50690 — dieselbe Menge wie `python -m lauf oxide` und der Benchmark (`OXID_PATTERN` importiert, nicht kopiert). Bringt eine eigene Prüfungsauswahl mit (`kennzahlen`, `redundant`, `verkehrt`, `instanz-als-klasse`, `zyklus`, `parallelzweig`) und `--bereichswurzel Q50690` |
| `periodensystem` | die 118 chemischen Elemente (`P31 = Q11344`, Ordnungszahl ≤ 118) |
| `polymer` | **Klassen** der Polymere/Kunststoffe unter Q11474 (`P279*`, ~206) — dieselbe Wurzel wie `python -m lauf polymer` und der Benchmark, dort aber mitsamt Instanzen. Für die Strukturprüfung nur die Klassen, sonst meldet `parallelzweig` massenhaft „kein `P279*`-Pfad zu material" für konkrete Kunststoffsorten. Reduzierte Prüfungsauswahl wie `oxide`, `--bereichswurzel Q11474` |
| `magnetwerkstoffe` | Magnetwerkstoffe unter Q949573, **ohne Isotope** (`FILTER NOT EXISTS { ?i wdt:P1086 ?z }`) — sonst zieht ein schiefer Instanzpfad über Nickel (Q744) ~40 Nickel-Isotope herein. Winzig (~10 Klassen), `MAGNET_PATTERN` mit dem Benchmark identisch, `--bereichswurzel Q949573` |

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

## Das Szenario `periodensystem`

```bash
python "Material class structure/ClassCheck.py" --population periodensystem
```

Prüft **nur** die 118 chemischen Elemente und bringt seine eigene
Prüfungsauswahl mit (`kennzahlen`, `elementklasse`, `redundant`, `zyklus`) —
`--pruefungen` überschreibt sie, `--bereichswurzel` steht hier auf Q11344
(chemisches Element) statt auf Q37756.

Es ist der einzige Fall in diesem Werkzeug, in dem die Grundgesamtheit
**abgeschlossen** und der **Maßstab bekannt** ist: aus der Ordnungszahl
(P1086) folgt die Stellung im Periodensystem, damit die Kategorie und die
Gruppe. Hier wird nichts aus Bezeichnungen geraten, hier wird nachgerechnet.
Die Soll-Tabelle steht deshalb ausnahmsweise **im Quelltext** und wird nicht
aus Wikidata geholt — sie ist der Maßstab, gegen den Wikidata geprüft wird.

### Was `elementklasse` prüft

| Befund | Herkunft | Eigenschaft | Stufe |
|---|---|---|---|
| `element-kategorie` | Ordnungszahl → Alkalimetalle, Erdalkalimetalle, Übergangsmetalle, Lanthanoide, Actinoide, Metalle des p-Blocks, Halbmetalle, Nichtmetalle, Halogene, Edelgase | P279 | 2 |
| `element-gruppe` | Ordnungszahl → Gruppe des Periodensystems | P361 | 2 |
| `element-dichteklasse` | P2054 gegen die 5-g/cm³-Grenze → Leicht- oder Schwermetall | P279 | 3 |
| `element-kategorie-konflikt` | am Item steht eine andere Kategorie | P279 | 4 |
| `element-kategorie-umstritten` | die Literatur ist uneinig | P279 | 4 |
| `element-gruppe-als-p279` | die Gruppe steht als P279 statt als P361 | P279 | 4 |

### Der Ist-Zustand (gemessen 2026-08-29, alle 118 Elemente)

Ein voller Lauf meldet **48 fehlende Elementkategorien**, **69 fehlende
Dichteklassen**, **0 fehlende Gruppen** und **19 Meldungen ohne Entwurf**
(dazu 5 doppelte Kanten in Stufe 1 und 3 unsichere in Stufe 2).

* Nur **17 der 38 Übergangsmetalle** tragen Q19588 direkt — Chrom, Mangan,
  Eisen, Cobalt, Nickel, Kupfer, Tantal, Rhenium und Gold nicht. (Ruthenium
  bis Platin erreichen die Kategorie über *Platinmetalle*; solche Pfade
  zählen als erfüllt, deshalb bleiben 12 Vorschläge übrig.)
* **Leichtmetalle** (Q428766) steht an genau *einem* Element (Titan),
  **Schwermetalle** (Q105789) an genau einem (Wolfram) — daher die 69.
* Die **15 Lanthanoide** und **14 der 15 Actinoide** tragen **kein
  einziges** P279 auf ihre Kategorie.
* Die **Gruppen** dagegen sind über P361 lückenlos gepflegt, alle 18 sind
  besetzt — deshalb null Vorschläge. An einzelnen Elementen steht die Gruppe
  aber *zusätzlich* als P279 (Sauerstoff, Schwefel, Selen, Tellur, Polonium,
  Livermorium): das sind die sechs `element-gruppe-als-p279`-Meldungen.

### Wo bewusst nichts vorgeschlagen wird

* **Die 12. Gruppe** (Zink, Cadmium, Quecksilber, Copernicium): bei der IUPAC
  keine Übergangsmetalle, in vielen Lehrbüchern schon.
* **Selen, Polonium, Astat**: Halbmetall oder nicht — die Quellen sind
  uneinig.
* **Alles ab Ordnungszahl 113**: die Eigenschaften sind berechnet, nicht
  gemessen.
* **f-Block und Gruppe**: Cer bis Lutetium und Thorium bis Lawrencium stehen
  in *keiner* Gruppe. Sie auf Gruppe 3 zu setzen wäre genau die Behauptung,
  um die seit Jahrzehnten gestritten wird (La/Ac gegen Lu/Lr). Lanthan und
  Actinium bleiben in Gruppe 3 — so hält es Wikidata bereits.
* **Die 2., 17. und 18. Gruppe als P279**: diese drei Gruppen-Items *sind*
  zugleich die Kategorie-Items (Erdalkalimetalle, Halogene, Edelgase). Ein
  P279 darauf ist dort die Kategoriezuordnung und kein verrutschtes P361.
* **Dichte nahe der Grenze**: die 5-g/cm³-Schwelle zwischen Leicht- und
  Schwermetall ist Konvention, nicht Physik (andere Quellen nennen 4,5).
  Deshalb bleibt ein Graubereich von ±0,5 g/cm³ vorschlagsfrei, und ein
  Element muss mit *allen* seinen P2054-Werten auf derselben Seite liegen.
  `--ohne-dichte` lässt die Prüfung ganz weg.

P2054 steht an den Elementen in **zwei Einheiten nebeneinander** (56 Werte in
kg/m³, 45 in g/cm³). Gerechnet wird deshalb nur mit Werten, deren Einheit
bekannt ist — wer den rohen Zahlenwert nimmt, hält Natrium (1033 kg/m³) für
ein Schwermetall.

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

## Szenarien (`--szenario`)

Drei feste Ausschnitte der Klassenhierarchie, jeder einzeln aufrufbar. Sie
beantworten dieselbe Frage wie die Trace-Graphen — *wie hängt das an der
Wurzel?* —, nur für Gruppen, bei denen die Antwort nicht am Pfad, sondern an
der **Klassenvergabe selbst** hängt.

```bash
python "Material class structure/visualisierung.py" --szenario periodensystem
python "Material class structure/visualisierung.py" --szenario legierungen minerale
python "Material class structure/visualisierung.py" --szenario alle
```

| Szenario | Was gezeichnet wird | Dateien |
|---|---|---|
| `periodensystem` | alle 118 Elemente im PSE-Raster. **Füllung** = die aus der Ordnungszahl folgende Elementkategorie; **Rand** = ob deren Zugehörigkeit als `part of` (P361, grün — so will es [periodic-table-conventions.md](../.claude/rules/periodic-table-conventions.md) Fall 2), als `P279`/`P31` (dick rot — falsche Property) oder gar nicht (rot gestrichelt) hängt. Unten in jeder Zelle das Gruppen-Ergebnis (`G8 ✓/!/–`). Die Kategorie/Gruppen-QIDs und die Soll-Tabelle kommen aus `ClassCheck.py` (importiert, nicht kopiert) | `szenario_periodensystem.png`, `szenario_periodensystem.csv` |
| `legierungen` | 10 Legierungsklassen (Stahl, rostfreier Stahl, Bronze, Messing, Gusseisen, Kupfer-, Aluminium-, Nickelbasis-, Titanlegierung, Superlegierung) mit ihren **direkten Subklassen** — der Blick nach unten statt nach oben | `szenario_legierungen.png` |
| `minerale` | 10 Mineralarten (Quarz, Calcit, Pyrit, Hämatit, Magnetit, Halit, Gips, Korund, Fluorit, Diamant) mit ihren Pfaden hinauf zu `Mineral` (Q7946) | `szenario_minerale.png` |

Was die drei Bilder zeigen (Stand 29.08.2026):

* **Periodensystem.** Die *Gruppen* sind über `P361` lückenlos gepflegt (alle
  118 Elemente ✓). Die *Kategorien* nicht: rund 50 Elemente führen sie korrekt
  als `P361`, aber ~46 hängen sie an `P279`/`P31` (fast alle Übergangs- und
  p-Block-Metalle, dazu H und B) und 9 tragen gar keine (C, P, S und die
  Platinmetalle Ru–Pt). 13 Zellen sind grau — Ordnungszahlen ohne eindeutige
  Kategorie (12. Gruppe, Se/Po/At, alles ab 113). Das sind exakt die
  `element-kategorie-falsche-property`- und `element-kategorie-fehlt`-Befunde,
  die `ClassCheck.py --population periodensystem` als QuickStatements ausgibt.
* **Legierungen.** Die Beispiele unterscheiden sich um zwei Größenordnungen
  (Stahl 72 Subklassen, Titanlegierung 6); `--max-subklassen` deckelt die
  gezeichneten Kinder (Standard 8), die Gesamtzahl steht am Knoten. Querkanten
  markieren Subklassen, die unter mehreren Beispielen hängen (Alumel unter
  Aluminium- *und* Nickelbasislegierung, Inconel unter Nickelbasis- *und*
  Superlegierung). Unter Titanlegierung stehen mit Titancarbid, Titannitrid
  und Titandihydrid drei Verbindungen — derselbe Befund wie in der
  Empfehlung nebenan.
* **Minerale.** Alle zehn erreichen Q7946, aber **nicht** über `P31`
  „Mineralart" (das ist ein Sackgassen-Zweig), sondern über `P279` in die
  Mineralklassen (Silicate, Halogenide, Oxide und Hydroxide …). Auffällig:
  Gips läuft über `gypsum mineral group` → **Phosphatmineral**, obwohl es ein
  Sulfat ist; Diamant hängt zusätzlich unter `Schmuckstein`.

Die QID-Listen stehen als `SZENARIO_LEGIERUNGEN` / `SZENARIO_MINERALE` oben im
Skript — bewusst QIDs, nicht Labels: die Labelsuche löst „Diamant" auf ein
Schiff und „Gips" auf einen Familiennamen auf.

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
| `--szenario` | statt des Standardlaufs ein oder mehrere Szenarien zeichnen: `periodensystem`, `legierungen`, `minerale` oder `alle` |
| `--szenario-out` | Zielverzeichnis der Szenario-Dateien (Standard: neben dem Skript) |
| `--max-subklassen` | nur mit `--szenario legierungen`: höchstens N Subklassen je Beispiel (Standard 8; Kupferlegierung allein hat 44) |

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
weiterhin `--trace-out`. Die `szenario_*`-Dateien schreibt das Skript aus
demselben Grund ebenfalls neben sich, `--szenario-out` verlegt sie.

| Datei | Inhalt |
|---|---|
| `werkstoff_check.csv` | eine Zeile je geprüftem Werkstoff: `input`, `qid`, `label`, `status`, `via_subclass_of`, `via_instance_of`, `direct_instance_of`, `direct_subclass_of` |
| `werkstoff_graph.png` | die geprüften Werkstoffe mit ihrer tatsächlichen Anbindung (rot = kein Pfad zu Q214609, grün = Pfad vorhanden) |
| `subclass_tree_material.png` | nur mit `--tree`: Subclass-Hierarchie unter Q214609, begrenzt durch `--depth` / `--max-nodes` |
| `trace_<gruppe>_<achse>.png` | Pfad-Graphen der Matrix `TRACE_GROUPS` × `TRACE_ROOTS` (Standardlauf) |
| `trace_graph.png` | Pfad-Graph eines Einzelaufrufs mit `--trace` (Name über `--trace-out`) |
| `szenario_periodensystem.png` | nur mit `--szenario`: PSE-Raster, Füllung = Kategorie aus der Ordnungszahl, Rand = P361-Zustand (siehe oben) |
| `szenario_periodensystem.csv` | nur mit `--szenario`: je Element `ordnungszahl`, `symbol`, `label`, `qid`, `soll_kategorie`, `kategorie_status` (ok/falsch/fehlt/strittig), `kategorie_property` (P361 bzw. P279→P361), `soll_gruppe`, `gruppe_status` |
| `szenario_legierungen.png` | nur mit `--szenario`: 10 Legierungsklassen mit ihren direkten Subklassen |
| `szenario_minerale.png` | nur mit `--szenario`: 10 Mineralarten mit ihren Pfaden zu Q7946 |

Status in der CSV ist entweder `OK (Pfad zu material vorhanden)`,
`AUFFAELLIG (kein Pfad zu material)` oder `NICHT_GEFUNDEN`, wenn die
Labelsuche nichts liefert.
