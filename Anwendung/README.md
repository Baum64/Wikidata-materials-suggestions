# Anwendungen

Wozu wird ein Werkstoff **gebraucht**? Diese Anwendung entwirft die drei
Statements, die diese Frage in Wikidata beantworten, und legt sie als
QuickStatements zur manuellen Prüfung ab:

| Property | Steht am | Bedeutet |
|---|---|---|
| `P366` (Verwendung) | Werkstoff | „Bronze wird für Glocken verwendet" |
| `P186` (Material) | Anwendungsitem | „Diese Glocke besteht aus Bronze" |
| `P2079` (Herstellungsverfahren) | Werkstoff | „Osemund entsteht im Osemundverfahren" |

Wie überall in diesem Repo wird **nichts automatisch geschrieben**. Ergebnis
sind eine CSV und ein Entwurf, in dem nur Abschnitt 1 überhaupt
QuickStatements-Syntax ist.

## Woher das Wissen kommt

Nicht aus einer handgeschriebenen Liste „Bronze → Glocke". Die wäre schnell
getippt und unbelegt. Die Quelle ist Wikidata selbst — und zwar die eine
Kante, die dort schon massenhaft gepflegt ist: `P186` an den Objekten.

Die Schieflage ist der ganze Hebel (gemessen 2026-08-22, Grundgesamtheit
`legierungen`):

| | |
|---|---|
| Legierungen insgesamt | 1082 |
| davon mit `P366` | 47 (4,3 %) |
| davon mit `P186`-Rückverweis von Objekten | 166 (15,3 %) |
| davon mit `P2079` | 12 (1,1 %) |
| **ohne jede Anwendungsangabe** | **884 (81,7 %)** |

Auf der anderen Seite nennen **142 782 Objekte** eine dieser Legierungen als
ihr Material. Dieses Wissen liegt also vor, es steht nur an der falschen
Stelle für die Frage „wozu?". Die Hauptableitung dreht es um: 21 495 Items
der Klasse *Münze* tragen `P186 → Bronze`, also ist *Münze* eine Verwendung
von Bronze. Nicht geraten, sondern aus 21 495 vorhandenen Aussagen
aggregiert — und jede Vorschlagszeile nennt ihre Belegzahl und fünf
Beleg-QIDs.

## Warum die Rückrichtung nicht symmetrisch ist

Der naheliegende Umkehrschluss — „Neusilber `P366` Münze, also Münze `P186`
Neusilber" — ist falsch, und zwar im Regelfall, nicht am Rand. Er
verwechselt zwei Quantoren:

```
P366 am Werkstoff:   MANCHE Münzen sind aus Neusilber.   richtig
P186 an der Klasse:  ALLE Münzen sind aus Neusilber.     Unsinn
```

Deshalb wird die Rückkante nur dort als einspielbar vorgeschlagen, wo das
Anwendungsitem ein **Einzelding** ist — keine Instanzen, keine Unterklassen.
Bei einer konkreten Glocke stimmt die Aussage. Steht dort eine Klasse, geht
dieselbe Zeile auskommentiert raus, mit dem Quantorenhinweis daneben (14
Einzeldinge gegen 58 Klassen im Lauf vom 2026-08-22).

Zwei Fälle fängt die Vorprüfung vorher ab:

* Der `P366`-Wert ist eine **Tätigkeit** (Schweißen, Löten, Gießen,
  Halbleitertechnik). Ein Vorgang besteht aus keinem Material — hier fehlt
  keine Rückkante, hier kann es keine geben. 20 solche Werte im Lauf.
* Der `P366`-Wert ist ein **Fertigungsverfahren**. Dann ist womöglich
  `P2079` gemeint. Das ist eine Frage, keine Aussage, und landet im
  Klärungsabschnitt.

## Vier Filter auf der Aggregation

Ohne sie ist Abschnitt 1 fünfmal so lang und deutlich schlechter. Nur der
erste löscht etwas; die anderen drei verschieben die Zeile in einen
auskommentierten Abschnitt.

**Sperrliste** (`KLASSEN_SPERRE`). Nicht theoretisch zusammengestellt,
sondern aus einem echten Lauf gezogen: die Klassen, die oben in der
Aggregation stehen und trotzdem keine Verwendung bezeichnen. Ihr gemeinsamer
Nenner ist, dass sie beschreiben, was mit dem Objekt *passiert ist* —
gefunden, unter Schutz gestellt, ins Depot gelegt, zerbrochen — oder gar
nichts sagen. Ohne den Filter wäre „Bronze wird für archäologische Funde
verwendet" ein Vorschlag mit 647 Belegen.

**Verbundgegenstand.** Ein Wolkenkratzer besteht nicht aus Stahl, er hat
ein Stahlskelett; ein Kameragehäuse hat eine Magnesiumschale. Solche Zeilen
behaupten mehr, als der Gegenstand hergibt.

Warum nicht am gemessenen Anteil? Weil der in Wikidata nirgends steht. Von
den rund 127 000 `P186`-Aussagen an diesen Werkstoffen trägt **keine
einzige** den Qualifikator `P518` („bezogen auf"), und die Zahl der
Materialien am Objekt trennt auch nicht: 92 bis 99 % der Objekte nennen
höchstens drei. Ein Wolkenkratzer steht dort mit „Stahl" allein, genau wie
eine Münze mit „Bronze". Die Unterscheidung muss also an der Klasse hängen.

Die Wurzeln sind eng gewählt und gegengeprüft: *Bauwerk* (Q811979) als
Wurzel fängt Gedenktafel, Flurkreuz und Zierbrunnen mit — die sind
vollständig aus dem Werkstoff. **Gebäude, Brücke, Turm, Fahrzeug, Maschine**
trennen sauber (Wolkenkratzer, Leuchtturm, Straßenbrücke, U-Boot, Torpedo
ja; Münze, Glocke, Skulptur, Astrolabium, Leuchter, Tisch nein). *Bauwerk*
selbst wird exakt verglichen, weil es über den Wurzeln hängt statt unter
ihnen. Dazu zwei kuratierte Fälle, die keine Hierarchie fängt: *Gemälde*
(das Metall ist Bildträger, Pigment oder Rahmen) und *Kleidung* (das Metall
sitzt an Knöpfen und Reißverschlüssen). 331 Zeilen.

**Zu speziell.** Die Klasse existiert in weniger als `--min-sprachen`
Wikipedias. Als Verwendung eines Werkstoffs ist das zu eng gefasst —
„Bronze für Carteluhren" (4 Sprachversionen) beschreibt einen Einzelfall,
„National Historical Commission of the Philippines historical marker" (3)
ein Regionalprogramm. Das Maß ist grob, aber trennscharf: Münze 129, Brücke
202, Werkzeug 137 gegen Digitalkamera-Modell 0, Skulpturenserie 0,
Fahrzeugteil 0.

Die Schwäche steht hier, nicht im Kleingedruckten: **Skulptur hat nur 26.**
Eine Schwelle über 10 fängt an, gute Verwendungen zu treffen. 440 Zeilen.

**Überdeckung.** Liefert ein Werkstoff Vorschläge für Skulptur (11 353
Belege), Statue (3168), Statuette (915) und Porträtbüste (636), dann ist die
erste Zeile die Aussage und der Rest ihr Echo. Weg kommt, wozu es eine
**allgemeinere** Kandidatenklasse mit mindestens so vielen Belegen gibt.

Bewusst nur in diese Richtung. Die naheliegende Variante — jede P279-Kette
auf ihr bestbelegtes Glied zusammenziehen — würde über kaputte Kanten hinweg
zusammenziehen, und davon gibt es hier reichlich: Wikidata führt *Münze* als
Unterklasse von *Skulptur* (siehe [P279-structure/](../P279-structure/)).
Über diese Kante fiele die Skulptur-Zeile weg, weil die Münz-Zeile mehr
Belege hat. So herum kann das nicht passieren: die bestbelegte Klasse einer
Kette fällt nie. 524 Zeilen.

Die drei letzten Filter laufen **vor** der Überdeckung, damit eine
aussortierte Klasse nie eine gute verdrängt: sonst nähme die Brücke
(Verbund, viele Belege) die Glocke mit.

## P2079 ist fast leer — und das ist das Ergebnis

Unter den 1082 Legierungen tragen **12** überhaupt ein `P2079`. Damit gibt
es für diese Property keine Datenbasis, aus der sich etwas aggregieren
ließe. Bleibt die Vererbung entlang `P279` (die Unterklasse eines Stahls
wird wie der Stahl erzeugt) — und die ist eine Behauptung, keine Ableitung:
legierter Stahl entsteht anders als Roheisen. Sie geht deshalb vollständig
auskommentiert raus (77 Zeilen).

Für `P2079` ist die Zahl selbst das Ergebnis: hier fehlt nicht ein
Vorschlag, hier fehlt die Grundgesamtheit.

## Die Prüfungen

| Prüfung | Was sie findet | Wohin | Lauf 2026-08-22 |
|---|---|---|---|
| `p366-aus-p186` | ≥ `--min-belege` Objekte einer Klasse nennen den Werkstoff | **Abschnitt 1** | 294 |
| `p186-einzelding` | `P366` da, Rückkante fehlt, Anwendungsitem ist ein Einzelding | **Abschnitt 1** | 14 |
| — (`p366-ueberdeckt`) | von einer allgemeineren Klasse abgedeckt | Abschnitt 2 | 524 |
| — (`p366-verbund`) | Gegenstand besteht nur zum Teil aus dem Werkstoff | Abschnitt 3 | 331 |
| — (`p366-zu-speziell`) | Klasse in < `--min-sprachen` Wikipedias | Abschnitt 4 | 440 |
| `p186-klasse` | wie oben, aber das Anwendungsitem ist eine Klasse | Abschnitt 5 | 58 |
| `p2079-vererbt` | Werkstoff ohne `P2079`, eine Oberklasse hat eines | Abschnitt 6 | 77 |
| `p366-verfahren` | `P366` zeigt auf ein Fertigungsverfahren | Abschnitt 7 | 5 |

Was Abschnitt 1 danach enthält, sind Gebrauchsklassen: Münze, Skulptur,
Glocke, Werkzeug, Astrolabium, Leuchter, Löffel, Schnalle, Axt, Schwert,
Mikroskop, Schlüssel, Angelhaken, Weihrauchfass.

## Aufruf

Aus dem Repo-Wurzelverzeichnis:

```bash
python "Anwendung/Anwendung.py"
python "Anwendung/Anwendung.py" --population metallischer-werkstoff
python "Anwendung/Anwendung.py" --min-belege 5 --pruefungen p366-aus-p186
python "Anwendung/Anwendung.py" --vorsichtig    # nichts einspielbar
```

| Option | Bedeutung |
|---|---|
| `--population` | `legierungen` (Vorgabe), `metallischer-werkstoff`, `material` |
| `--pruefungen` | Auswahl aus der Tabelle oben (Vorgabe: alle) |
| `--min-belege` | Belegschwelle für `P366` (Vorgabe 3). Kleiner heißt mehr Vorschläge und mehr Zufallstreffer. |
| `--min-sprachen` | wie viele Wikipedia-Sprachversionen die Klasse haben muss (Vorgabe 10). `0` schaltet den Filter ab. Über 10 trifft er gute Verwendungen. |
| `--limit` | nur die ersten N Werkstoffe, für Probeläufe |
| `--vorsichtig` | auch die abgeleiteten Zeilen auskommentieren — dann enthält die Datei keine ausführbare Zeile |
| `--csv`, `--qs-out` | Ziel und Namen der Ausgabedateien |

Die Grundgesamtheiten kommen per Import aus
[materialswiki/cli.py](../materialswiki/cli.py) — nicht kopiert, damit die
Werkzeuge nicht irgendwann verschiedene Mengen meinen. `--population
legierungen` enthält deshalb auch hier „Metalle" (Q11426), weil Wikidata
Metall unter Legierung führt; das ist der in
[P279-structure/](../P279-structure/) dokumentierte Befund und keine
Eigenheit dieser Anwendung.

## Ausgabe

```
anwendungen_befunde_<Zeitstempel>.csv          alle Befunde, eine Zeile je Befund
quickstatements_anwendungen_<Zeitstempel>.txt  Entwurf, nur Abschnitt 1 einspielbar
```

Keine Zeile trägt einen Beleg (`S…`). Alle Aussagen sind aus Wikidata selbst
abgeleitet, und ein Import kann sich nicht auf sich selbst berufen. Der
Kommentar unter jeder Zeile nennt stattdessen die Items, die sie tragen —
damit ist jede Zeile in einer Minute nachprüfbar.

## Grenzen

* Die Aggregation sieht nur, was schon in Wikidata steht. Ein Werkstoff ohne
  einen einzigen `P186`-Rückverweis bekommt hier nichts — das sind 884 der
  1082 Legierungen. Fachliteratur ersetzt dieses Werkzeug nicht.
* Sie sieht damit auch die **Sammelschwerpunkte** der Datenbasis: Bronze
  führt, weil Museen Bronzeskulpturen katalogisieren, nicht weil Bronze
  hauptsächlich für Skulpturen verwendet würde. Für `P366` („eine
  Verwendung") ist das richtig, für „die Hauptverwendung" wäre es falsch.
* Der Anteil, zu dem ein Gegenstand aus dem Werkstoff besteht, ist in
  Wikidata nicht erfasst (`P518`: 0 von 127 000). Der Verbund-Filter ersetzt
  ihn durch eine Klassenaussage — das ist gröber und liegt bei *Flurkreuz*
  daneben, das Wikidata unter „Gebäude" führt. Die Zeile ist dort nicht
  gelöscht, nur auskommentiert.
* `--min-belege 3` und `--min-sprachen 10` sind Setzungen, keine Messungen. Sie hält die Zahl der
  Zufallstreffer klein und ist der Regler, an dem sich die Länge von
  Abschnitt 1 einstellen lässt.
