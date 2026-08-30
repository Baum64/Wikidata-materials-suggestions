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

## Fünf Filter auf der Aggregation

Ohne sie ist Abschnitt 1 fünfmal so lang und deutlich schlechter. Nur der
erste löscht etwas; die anderen vier verschieben die Zeile in einen
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

**Der Werkstoff ist selbst eine Klasse.** Trägt das Item kein `P31`, ist
es über `P279` in die Grundgesamtheit gekommen — es ist eine *Klasse* von
Werkstoffen („Aluminiumlegierung", „Stahl"), kein Werkstoff.
[[Help:Basic membership properties]] zieht die Grenze genau dort, und
[Material class structure/](../Material%20class%20structure/) zieht sie vor
jedem Entwurf. Hier gilt sie aus demselben Grund wie bei der Rückkante, nur
auf der anderen Seite der Aussage:

    P366 an der Instanz:  Bronze wird für Münzen verwendet.        (richtig)
    P366 an der Klasse:   JEDE Aluminiumlegierung ist Münzmetall.  (Unsinn)

Die Belege sind darum nicht falsch, sie hängen nur an den Unterklassen —
dorthin gehört die Zeile, oder an die Klasse selbst, wenn die Verwendung
wirklich für alle gilt. Also: auskommentiert in Abschnitt 5, mit den Belegen
daneben. `--auch-werkstoffklassen` schaltet die Trennung ab.

**Überdeckung.** Liefert ein Werkstoff Vorschläge für Skulptur (11 353
Belege), Statue (3168), Statuette (915) und Porträtbüste (636), dann ist die
erste Zeile die Aussage und der Rest ihr Echo. Weg kommt, wozu es eine
**allgemeinere** Kandidatenklasse mit mindestens so vielen Belegen gibt.

Bewusst nur in diese Richtung. Die naheliegende Variante — jede P279-Kette
auf ihr bestbelegtes Glied zusammenziehen — würde über kaputte Kanten hinweg
zusammenziehen, und davon gibt es hier reichlich: Wikidata führt *Münze* als
Unterklasse von *Skulptur* (siehe [Material class structure/](../Material%20class%20structure/)).
Über diese Kante fiele die Skulptur-Zeile weg, weil die Münz-Zeile mehr
Belege hat. So herum kann das nicht passieren: die bestbelegte Klasse einer
Kette fällt nie. 524 Zeilen.

Die drei letzten Filter laufen **vor** der Überdeckung, damit eine
aussortierte Klasse nie eine gute verdrängt: sonst nähme die Brücke
(Verbund, viele Belege) die Glocke mit.

## P2079: in Wikidata fast leer, in der Wikipedia nicht

Unter den 1082 Legierungen tragen **12** überhaupt ein `P2079`. In Wikidata
gibt es dafür also nichts zu aggregieren. In der Wikipedia steht die Angabe
sehr wohl — nur in Fließtext statt in einer Infobox.

### Der Weg dorthin: Wikilinks, nicht Textsuche

`[[Sintern]]` im Herstellungsabschnitt ist bereits eine aufgelöste Entität,
während eine Textsuche nach „gesintert" raten müsste. Drei Filter
hintereinander:

1. **Abschnitt** — nur Überschriften, die die Herstellung meinen
   (`Herstellung`, `Gewinnung`, `Erzeugung`, `Production`, `Smelting` …).
   *Hersteller* (Firmen), *Produktionsmengen* und *Staaten mit der größten
   Erzeugung* treffen das Muster ebenfalls und sind ausgeschlossen. Der Text
   reicht bis zur nächsten Überschrift gleicher Ebene, schließt
   Unterabschnitte also ein — ohne das bleibt bei *Stahl* und *Hartmetall*
   nichts übrig, weil dort unter „Herstellung" nur weitere Überschriften
   stehen.
2. **Auflösung** — Linkziel → QID über die Seiten-API mit `redirects=1`.
   Für den Artikel des Werkstoffs selbst gilt das Gegenteil: landet die
   Anfrage auf einem anderen Lemma, wird er verworfen. Der Sitelink von
   *Grüngold* heißt „Grüngold", die Seite leitet aber auf *Gold* weiter —
   ohne diese Prüfung wird der ganze Goldartikel ausgewertet und der
   Legierung zugeschrieben, was im ersten Lauf „Grüngold `P2079`
   Kernspaltung" ergab. 42 der 645 Sitelinks sind solche Weiterleitungen.
3. **Vokabular** — nur Items, die in Wikidata **schon als `P2079`-Wert
   benutzt werden**: 1991 verschiedene Werte in 361 825 Aussagen.

Von 645 Werkstoffen mit Artikel haben nur **108 überhaupt einen
Herstellungsabschnitt**; daraus werden 1153 Links, davon 105 im Vokabular
und am Ende 82 Vorschläge.

Filter 3 ist der eigentliche Trick. Er ersetzt eine geratene Ontologie durch
beobachteten Gebrauch. Der Versuch über Klassenwurzeln ist daran
gescheitert, dass *Prozess* (Q3249551) auch Oxidation, Glut und
„elektrischer Strom" einschließt und *Technik* (Q2695280) die
Härteprüfverfahren: von 72 Links aus sieben Artikeln hätten die Wurzeln 24
durchgelassen, das Vokabular lässt 11 durch — und die sind brauchbar. Dazu
muss der Wert eine Tätigkeit sein, denn im Vokabular stehen auch *Hochofen*
(ein Gerät) und *Kalkstein* (ein Gestein).

### Der Beleg

Jede Zeile ist fertig belegt, in derselben Form wie in materialswiki:

```
Q307036	P2079	Q131172	S143	Q48183	S4656	"https://de.wikipedia.org/w/index.php?title=Mu-Metall&oldid=266222783"	S813	+2026-08-22T00:00:00Z/11
```

`S143` = importiert aus der deutschsprachigen Wikipedia, `S4656` =
Permalink auf **die konkrete Artikelversion**, `S813` = Abrufdatum. Darunter
steht als Kommentar der Satz, in dem der Link stand.

### Warum die Zeilen trotzdem auskommentiert bleiben

Weil die Trefferquote es nicht hergibt. Ein Herstellungsabschnitt
beschreibt nicht nur, wie der Werkstoff **entsteht**, sondern auch, wie man
ihn **bearbeitet** — und beides steht in denselben Sätzen. Der Artikel
*Mu-Metall* hat einen Abschnitt schlicht namens „Herstellung" und darin den
Satz:

> Mu-Metall lässt sich stanzen, ätzen, tiefziehen, biegen, löten, schweißen,
> laserschneiden und galvanisch beschichten.

Acht Verfahren, alle korrekt verlinkt, alle im `P2079`-Vokabular — und
keines stellt Mu-Metall her. Im Probelauf waren das 8 von 9 Zeilen.

Trennen lässt sich das nicht:

* **Nicht über die Überschrift.** Die heißt hier „Herstellung", nicht
  „Herstellung und Verarbeitung".
* **Nicht über die Verfahrensart.** Die DIN-8580-Hauptgruppen wären genau
  das richtige Raster — Urformen ja, Umformen und Fügen nein —, aber sie
  sind in Wikidata zu dünn besetzt: *Walzen* hängt dort unter Urformen,
  *Sintern* nicht, *Spritzgießen* und *Schweißen* unter keiner der beiden.

Also liest ein Mensch den Satz und nimmt das `# ` weg. Die Frage dabei ist
immer dieselbe: **entsteht der Werkstoff so, oder wird er nur so
verarbeitet?**

### Vererbung entlang P279

Bleibt daneben bestehen, ebenfalls auskommentiert: dass die Unterklasse
eines Stahls wie der Stahl erzeugt wird, ist eine Behauptung und keine
Ableitung — legierter Stahl entsteht anders als Roheisen.

## Die Prüfungen

| Prüfung | Was sie findet | Wohin | Lauf 2026-08-22 |
|---|---|---|---|
| `p366-aus-p186` | ≥ `--min-belege` Objekte einer Klasse nennen den Werkstoff | **Abschnitt 1** | 294 |
| `p186-einzelding` | `P366` da, Rückkante fehlt, Anwendungsitem ist ein Einzelding | **Abschnitt 1** | 14 |
| — (`p366-ueberdeckt`) | von einer allgemeineren Klasse abgedeckt | Abschnitt 2 | 524 |
| — (`p366-verbund`) | Gegenstand besteht nur zum Teil aus dem Werkstoff | Abschnitt 3 | 331 |
| — (`p366-zu-speziell`) | Klasse in < `--min-sprachen` Wikipedias | Abschnitt 4 | 440 |
| — (`p366-nur-klasse`) | der Werkstoff trägt kein `P31`, ist also selbst eine Klasse | Abschnitt 5 | — |
| `p2079-wikipedia` | Verfahren im Herstellungsabschnitt des Artikels, belegt | Abschnitt 6 | 82 |
| `p186-klasse` | wie oben, aber das Anwendungsitem ist eine Klasse | Abschnitt 7 | 58 |
| `p2079-vererbt` | Werkstoff ohne `P2079`, eine Oberklasse hat eines | Abschnitt 8 | 77 |
| `p366-verfahren` | `P366` zeigt auf ein Fertigungsverfahren | Abschnitt 9 | 5 |

Die Zahlen stammen aus dem Lauf vom 2026-08-22, also von **vor** der
Klasse/Instanz-Trennung; ein Teil der 294 Zeilen aus Abschnitt 1 steht
seit dem 2026-08-27 in Abschnitt 5.

Was Abschnitt 1 danach enthält, sind Gebrauchsklassen: Münze, Skulptur,
Glocke, Werkzeug, Astrolabium, Leuchter, Löffel, Schnalle, Axt, Schwert,
Mikroskop, Schlüssel, Angelhaken, Weihrauchfass.

## Aufruf

Aus dem Repo-Wurzelverzeichnis:

```bash
python "Anwendung/Anwendung.py"
python "Anwendung/Anwendung.py" --population metallischer-werkstoff
python "Anwendung/Anwendung.py" --min-belege 5 --pruefungen p366-aus-p186
python "Anwendung/Anwendung.py" --pruefungen p2079-wikipedia --sprachen de
python "Anwendung/Anwendung.py" --auch-werkstoffklassen
python "Anwendung/Anwendung.py" --vorsichtig    # nichts einspielbar
```

| Option | Bedeutung |
|---|---|
| `--population` | `legierungen` (Vorgabe), `metallischer-werkstoff`, `material` |
| `--pruefungen` | Auswahl aus der Tabelle oben (Vorgabe: alle) |
| `--min-belege` | Belegschwelle für `P366` (Vorgabe 3). Kleiner heißt mehr Vorschläge und mehr Zufallstreffer. |
| `--min-sprachen` | wie viele Wikipedia-Sprachversionen die Klasse haben muss (Vorgabe 10). `0` schaltet den Filter ab. Über 10 trifft er gute Verwendungen. |
| `--sprachen` | welche Wikipedias nach einem Herstellungsabschnitt durchsucht werden (Vorgabe `de en`). Der teuerste Teil des Laufs: ein Artikelabruf je Werkstoff und Sprache bei einer Anfrage pro Sekunde — 317 deutsche und 539 englische Artikel. |
| `--auch-werkstoffklassen` | auch für Items ohne `P31` entwerfen. Ohne den Schalter bekommen nur Instanzen einen einspielbaren Vorschlag. |
| `--limit` | nur die ersten N Werkstoffe, für Probeläufe |
| `--vorsichtig` | auch die abgeleiteten Zeilen auskommentieren — dann enthält die Datei keine ausführbare Zeile |
| `--csv`, `--qs-out` | Ziel und Namen der Ausgabedateien |

Die Grundgesamtheiten kommen per Import aus
[materialswiki/cli.py](../materialswiki/cli.py) — nicht kopiert, damit die
Werkzeuge nicht irgendwann verschiedene Mengen meinen. `--population
legierungen` enthält deshalb auch hier „Metalle" (Q11426), weil Wikidata
Metall unter Legierung führt; das ist der in
[Material class structure/](../Material%20class%20structure/) dokumentierte Befund und keine
Eigenheit dieser Anwendung.

## Ausgabe

```
anwendungen_befunde_<Zeitstempel>.csv          alle Befunde, eine Zeile je Befund
qs_anwendungen_<Zeitstempel>.txt  Entwurf, nur Abschnitt 1 einspielbar
```

Die `P2079`-Zeilen aus der Wikipedia tragen einen Beleg (`S143`+`S4656`,
siehe oben). Die `P366`- und `P186`-Zeilen tragen keinen: sie sind aus
Wikidata selbst abgeleitet, und ein Import kann sich nicht auf sich selbst
berufen. Ihr Kommentar nennt stattdessen die Items, die sie tragen — damit
ist jede Zeile in einer Minute nachprüfbar.

## Grenzen

* Die Aggregation sieht nur, was schon in Wikidata steht. Ein Werkstoff ohne
  einen einzigen `P186`-Rückverweis bekommt hier nichts — das sind 884 der
  1082 Legierungen. Fachliteratur ersetzt dieses Werkzeug nicht.
* Sie sieht damit auch die **Sammelschwerpunkte** der Datenbasis: Bronze
  führt, weil Museen Bronzeskulpturen katalogisieren, nicht weil Bronze
  hauptsächlich für Skulpturen verwendet würde. Für `P366` („eine
  Verwendung") ist das richtig, für „die Hauptverwendung" wäre es falsch.
* Die Grundgesamtheit `legierungen` enthält auch Elementgruppen
  (*Alkalimetalle*, *2. Hauptgruppe des Periodensystems*) — sie tragen
  selbst keine Ordnungszahl und rutschen deshalb durch den Elementfilter.
  Bekannte Eigenheit der Grundgesamtheit, siehe
  [Material class structure/](../Material%20class%20structure/).
* Der Anteil, zu dem ein Gegenstand aus dem Werkstoff besteht, ist in
  Wikidata nicht erfasst (`P518`: 0 von 127 000). Der Verbund-Filter ersetzt
  ihn durch eine Klassenaussage — das ist gröber und liegt bei *Flurkreuz*
  daneben, das Wikidata unter „Gebäude" führt. Die Zeile ist dort nicht
  gelöscht, nur auskommentiert.
* `--min-belege 3` und `--min-sprachen 10` sind Setzungen, keine Messungen. Sie hält die Zahl der
  Zufallstreffer klein und ist der Regler, an dem sich die Länge von
  Abschnitt 1 einstellen lässt.
