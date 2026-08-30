# benchmark — Wie gut sind Werkstoffe in Wikidata belegt?

Zählt für jede Property aus dem
[WikiProject Materials](https://www.wikidata.org/wiki/Wikidata:WikiProject_Materials/Properties),
wie viele Items unterhalb eines Wurzel-Items diese Aussage tatsächlich tragen.
Damit wird sichtbar, **wo sich Vorschläge aus
[materialswiki](../materialswiki/) überhaupt lohnen** — und je Property, aus
welcher Quelle (COD, Materials Project, NIST, Wikipedia-Infobox, Ableitung)
der Wert überhaupt kommen kann.

## Nutzung

Aus dem Repo-Wurzelverzeichnis (Installation siehe [../README.md](../README.md)):

```bash
python -m benchmark.benchmark
python -m benchmark.benchmark --root Q11426 --md abdeckung.md
python -m benchmark.benchmark --offline          # ohne Wiki-Abruf
```

| Option | Bedeutung |
|---|---|
| `--root` | Wurzel-Item (Standard: `Q1924900`, Metallischer Werkstoff) |
| `--sections` | Abschnitte der Projektseite (Standard: Physics, Mechanical, Thermal, Chemical, "Electric and Magnetic") |
| `--offline` | Property-Liste aus [properties_snapshot.json](properties_snapshot.json) statt live |
| `--md` | Ergebnistabelle zusätzlich als Markdown-Datei schreiben (gitignoriert) |
| `--top` | Anzahl der am besten belegten Items in der Ausgabe (`0` = aus, Standard: 10) |

## Woher die Property-Liste kommt

Die Projektseite listet ihre Properties als
`{{List of properties with sources/Row |id=NNNN}}` — genau diese IDs werden
ausgelesen (der Platzhalter `id=new` aus der Vorlagendoku fällt raus,
Unterabschnitte gehören zum Elternabschnitt).

Die Liste wird live geholt und als Momentaufnahme in
[properties_snapshot.json](properties_snapshot.json) abgelegt. Diese Datei ist
die **einzige bewusst versionierte Ergebnisdatei** des Repos — sie hält einen
Lauf reproduzierbar und macht `--offline` möglich.

## Grundgesamtheit

Konkrete Werkstoffe sind in Wikidata überwiegend als **Unterklassen**
modelliert (Stahl ist eine Unterklasse von metallischem Werkstoff, keine
Instanz). Ausgewertet wird deshalb die Vereinigung aus

- Instanzen: `?i wdt:P31/wdt:P279* wd:Q1924900`
- Unterklassen: `?i wdt:P279* wd:Q1924900`

Beide Teilmengen werden zusätzlich einzeln ausgewiesen. Warum die
Klassenhierarchie hier so uneinheitlich ist, untersucht
[../Material class structure/](../Material%20class%20structure/).

## Ausgabe

Je Property eine Zeile mit `abschnitt`, `pid`, `label`, `datatype`,
`gefuellt`, `luecke`, `anteil_prozent` sowie zwei Spalten zum Abgleich mit
materialswiki:

| Spalte | Bedeutung |
|---|---|
| `in_property_map` | interner Schlüssel aus `PROPERTY_MAP`. Seit dem 28.08.2026 steht **jede** Property der Projektseite dort — die Spalte sagt also nur noch, wie die Property intern heißt, nicht ob sie bedient wird |
| `quellen` | **aus welchen Quellen der Wert wirklich abgefragt wird** — leer, wenn keine Stufe des Laufs diese Property liefert. Das ist die Spalte, an der man sieht, was ein Lauf leisten kann |
| `mp_quelle` | `ja`, wenn dafür auch ein Feldpfad in `MP_FIELD_MAP` existiert — nur dann kann das Materials Project den Wert überhaupt liefern |

In der Textausgabe steht dasselbe hinter dem internen Schlüssel, z. B.
`<- crystal_system [COD, MP]`; am Ende zählt eine Legende je Quelle die
Properties.

| Kürzel | Quelle | liefert |
|---|---|---|
| `COD` | Crystallography Open Database | `P9824`, `P690`, `P556`, `P589` |
| `MP` | Materials Project (DFT-Rechnung) | `P2054`, `P556`, `P5668`, `P5673`, `P5593` |
| `NIST` | NIST Chemistry WebBook | `P3078`, `P3071` |
| `WD` | aus der Raumgruppe am Item abgeleitet | `P589` |
| `(Formel)` | aus der Summenformel abgeleitet | `P2670`, `P527` |
| `WPde-El` | de `{{Infobox Chemisches Element}}` | `P2101`, `P2102`, `P2054`, `P2068`, `P2055`, `P2056`, `P2075`, `P5593`, `P1088`, `P231`, `P556` |
| `WPde-Chem` | de `{{Infobox Chemikalie}}` | `P2054`, `P2101`, `P2102`, `P231` |
| `WPde-Min` | de `{{Infobox Mineral}}` | `P2054`, `P1088` |
| `WPen-El` | en `Template:Infobox <element>` | `P2101`, `P2102`, `P2068`, `P1088`, `P2054`, `P5679`, `P556`, `P5672` |
| `WPen-Chem` | en `{{Chembox}}` | `P2101`, `P2102`, `P2054`, `P231` |

Mehrere Kürzel heißen: mehrere Stufen könnten den Wert liefern; im Lauf
gewinnt die zuerst laufende, hier werden alle ausgewiesen.

### Nicht jeder Lauf fährt jede Stufe

Die Spalte richtet sich nach `--population`, weil
[../lauf.py](../lauf.py) Grundgesamtheit und Vorschlagslauf aneinander
koppelt — sonst verspricht der Benchmark Vorschläge, die nie kommen:

| Lauf | `--population` | Stufen |
|---|---|---|
| Gruppenlauf (`--group`) | `legierungen`, `minerale`, `oxide`, `carbide`, `polymer`, `magnetwerkstoffe`, `subtree` | COD, MP, NIST, WD, (Formel) + de-Infobox + `WPen-Chem` |
| Elementlauf (`--periodic-table`) | `metalle`, `periodensystem` | COD, MP, NIST, `WPde-El`, `WPen-El` |

Der Elementlauf kennt die beiden **Ableitungen nicht** —
`build_periodic_table_proposals` ruft weder die Punktgruppen- noch die
Formelstufe auf. Im Elementlauf hängt `P589` deshalb allein an COD. Umgekehrt
gibt es `P5672` nur dort: der Längenausdehnungskoeffizient steht allein in der
englischen Elementvorlage, und die wird im Gruppenlauf gar nicht geholt (dort
kommt `en_title` → `{{Chembox}}`).

**Eingeklammert** (`(Formel)`) heißt: die Stufe ist per Default **aus** und
geht erst mit ihrem Schalter an — `--formel`, abgeschaltet, weil `P527` und
`P2670` nicht mehr vorgeschlagen werden sollen. Ohne den Schalter schlägt
kein Lauf diese beiden Properties vor.

### Welche Wikipedia-Vorlage greift

`STUFEN_PIDS["wikipedia"]` ist die Vereinigung aller vier Feldkarten —
richtig für die Frage „muss die Stufe überhaupt laufen?", aber viel zu
großzügig für „was kommt bei dieser Gruppe an". [infobox.py](../materialswiki/infobox.py)
wirft die Feldnamen einfach auf den Wikitext; welche greifen, entscheidet die
Vorlage im Artikel:

| `--population` | Vorlagen |
|---|---|
| `minerale` | `WPde-Min` |
| `oxide`, `carbide`, `polymer`, `magnetwerkstoffe` | `WPde-Chem`, `WPen-Chem` |
| `legierungen`, `benannte-legierungen` | `WPde-Chem`, `WPde-Min`, `WPen-Chem` |
| `metalle`, `periodensystem` | `WPde-El`, `WPen-El` |
| sonst (`subtree`, eigenes `--root`) | alle im Gruppenlauf erreichbaren |

`{{Infobox Mineral}}` liefert nur deshalb etwas, weil ihre Felder `Dichte`
und `Mohshärte` genauso heißen wie in der Elementinfobox — Wärmeleitfähigkeit,
CAS-Nummer und Kristallstruktur stehen dort unter anderen Namen und werden
nicht gelesen. Gemessen am Lauf vom 28.08.2026 über 650 Minerale: aus der
deutschen Wikipedia kamen genau `P2054` und `P1088`, aus der englischen
nichts.

Diese Zuordnung ist die **einzige Stelle, die nicht aus dem Code folgt** —
sie ist an den Läufen abgelesen und in `WP_JE_POPULATION`
([benchmark.py](benchmark.py)) hinterlegt. Einzelne Artikel einer Gruppe
können abweichende Vorlagen tragen.

`PROPERTY_MAP`, `MP_FIELD_MAP` und `STUFEN_PIDS` werden aus
[../materialswiki/](../materialswiki/) **importiert, nicht kopiert** — die
Auswertung kann also nicht veralten, wenn dort eine Quelle etwas dazubekommt.
Nur die Zuordnung Lauf → Stufen (`LAEUFE` in
[benchmark.py](benchmark.py)) ist von Hand gepflegt: sie steht in `cli.py`
nur als Aufrufreihenfolge, nicht als Tabelle.

`P2670` und `P527` stehen nicht auf der Projektseite und tauchen deshalb nur
in der Tabelle oben auf, nicht im Bericht.

Welche MP-Felder bewusst nicht übernommen sind und warum, steht im Abschnitt
„Abgedeckte Properties" in
[../materialswiki/README.md](../materialswiki/README.md).

## Vor dem Einsatz anpassen

`USER_AGENT` oben im Skript mit echtem Namen/Kontakt füllen. Zwischen den
Abfragen liegt eine Pause von 1 s.
