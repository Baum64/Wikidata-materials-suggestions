# P279-Struktur

Prüft, wie **P279 („Unterklasse von")** unterhalb der Werkstoffe verwendet
wird, und entwirft Änderungen als QuickStatements.

Der [Benchmark](../benchmark/) misst, welche *Messwerte* an den
Werkstoff-Items fehlen. Dieses Werkzeug misst etwas anderes: ob die Items
überhaupt richtig **eingehängt** sind — wo die Kante fehlt, wo sie doppelt
ist, wo sie verkehrt herum zeigt und wo statt P279 fälschlich P31 steht.

```bash
python "P279-structure/P279benchmark.py"
python "P279-structure/P279benchmark.py" --population legierungen
python "P279-structure/P279benchmark.py" --pruefungen redundant verkehrt
python "P279-structure/P279benchmark.py" --vorsichtig      # nichts einspielbar
```

## Was einspielbar ist — und warum so wenig

Das ist die eigentliche Entwurfsentscheidung des Werkzeugs:

> **Einspielbar ist nur, was mechanisch aus dem Graphen folgt und dabei
> nichts behauptet.** Jede Aussage darüber, wo ein Werkstoff *hingehört*,
> ist fachlich und geht auskommentiert raus.

Konkret heißt das: ausführbar ist allein das **Entfernen redundanter
Kanten**. Hat ein Item P279 auf A *und* auf B, und landet A über P279
ohnehin bei B, dann sagt die Kante nach B nichts, was der Graph nicht schon
weiß. Nach dem Entfernen gilt dieselbe Klassenzugehörigkeit, nur abgeleitet
statt doppelt notiert — reversibel und ohne fachliche Behauptung.

Alles andere — die Einordnung einer Legierung unter ihr Basismetall, das
Umdrehen einer verkehrten Kante, die Umstellung von P31 auf P279 — steht in
auskommentierten Abschnitten. Die Datei lässt sich komplett nach
QuickStatements kopieren, ohne dass daraus versehentlich eine Aussage wird:
außerhalb von Abschnitt 1 beginnt jede Zeile mit `#`.

## Die sieben Prüfungen

| Prüfung | Findet | Entwurf |
|---|---|---|
| `kennzahlen` | wie P279 in der Grundgesamtheit überhaupt benutzt wird: P279, P31, beides, keines; Mehrfacheltern; Abstand zu `material` | — |
| `zyklus` | eine Klasse ist über P279 ihre eigene Oberklasse | keiner: der Zyklus sagt nicht, welche Kante der Kette ihn verursacht |
| `redundant` | Kante, die über einen anderen Elter ohnehin gilt | **einspielbar** |
| `verkehrt` | Kante `n → p`, obwohl unter `n` mehr hängt als unter `p` ohne `n` — die weitere Klasse hängt unter der engeren | auskommentiert |
| `instanz-als-klasse` | Item mit P31 auf eine Werkstoffklasse, das selbst Unterklassen hat | auskommentiert |
| `ohne-einordnung` | benannte Legierung ohne jeden Pfad zu `Legierung` (Q37756) | auskommentiert, wo es für das Basismetall eine Klasse gibt |
| `parallelzweig` | Item ohne P279\*-Pfad zu `material` (Q214609) | keiner — **kein Fehler**, siehe [Kategorie Hirachie](../Kategorie%20Hirachie/) |

Alle Prüfungen bleiben in der **Werkstoff-Ecke** (unter `material` oder
`Legierung`, plus die Grundgesamtheit selbst). Das ist keine Bequemlichkeit:
die P279-Hülle nach oben endet zwangsläufig in der obersten Ontologie, und
dort finden dieselben Prüfungen dieselben Fehler bei „Begriff", „Typ" oder
„Kunstgewerbe". Die Befunde wären richtig und trotzdem nicht unsere Sache —
eine dort eingespielte Änderung trifft hunderttausende Items ohne jeden
Werkstoffbezug.

### Wenn der Ersatzpfad selbst nicht hält

Redundanz ist nur so belastbar wie der Pfad, der sie begründet. Genau das
ist hier oft das Problem: `Ferrolegierung P279 Legierung` sieht redundant
aus, weil es über *ferrous metal → Metalle → Legierung* auch so geht — aber
der letzte Schritt ist die falsch modellierte Kante (siehe unten). Wer die
direkte Kante entfernt und später die falsche repariert, hat Ferrolegierung
aus dem Legierungsbaum geworfen.

Solche Befunde bekommen deshalb die Art `redundant-unsicher` und bleiben
auskommentiert. Gibt es einen *zweiten*, unbelasteten Ersatzpfad, gewinnt
der — dann bleibt der Befund einspielbar.

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
Unterbaugrößen mit den echten überein — in der Hülle nach oben wären sie ein
Artefakt der Abfrage, und das Ergebnis bestünde fast nur aus „Entität",
„Objekt", „Materie" und „Substanz". `material` (Q214609) taugt nicht als
Bereichswurzel: darunter hängen rund 936.000 Klassen.

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

## Ausgabedateien

| Datei | Inhalt |
|---|---|
| `p279_befunde_<Zeitstempel>.csv` | alle Befunde, eine Zeile je Befund |
| `quickstatements_p279_<Zeitstempel>.txt` | Entwurf; nur Abschnitt 1 ist ausführbar |

Beide stehen in [.gitignore](../.gitignore) — sie sind Momentaufnahmen eines
Laufs.

## Grenzen

* Es wird **nie** nach Wikidata geschrieben. Das Werkzeug erzeugt
  Vorschlagslisten, sonst nichts.
* Es legt **keine Items an**. Fehlende Klassen und Listeneinträge ohne Item
  stehen im Protokoll.
* Ein Teil der Meldungen aus `ohne-einordnung` ist zu Recht keine Legierung:
  Titannitrid, Titancarbid und Uranhydrid sind Verbindungen. Auch das
  entscheidet hier niemand automatisch.
* Der vollständige Abwärts-Baum unter Q37756 umfasst rund 3.200 Klassen und
  wird rundenweise geholt — ein Lauf dauert dadurch einige Minuten.
