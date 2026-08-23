# benchmark — Wie gut sind Werkstoffe in Wikidata belegt?

Zählt für jede Property aus dem
[WikiProject Materials](https://www.wikidata.org/wiki/Wikidata:WikiProject_Materials/Properties),
wie viele Items unterhalb eines Wurzel-Items diese Aussage tatsächlich tragen.
Damit wird sichtbar, **wo sich Vorschläge aus
[materialswiki](../materialswiki/) überhaupt lohnen** — und wo das Materials
Project gar nichts liefern kann.

## Nutzung

Aus dem Repo-Wurzelverzeichnis (Installation siehe [../README.md](../README.md)):

```bash
python -m benchmark.benchmark
python -m benchmark.benchmark --root Q11426 --csv abdeckung.csv
python -m benchmark.benchmark --offline          # ohne Wiki-Abruf
```

| Option | Bedeutung |
|---|---|
| `--root` | Wurzel-Item (Standard: `Q1924900`, Metallischer Werkstoff) |
| `--sections` | Abschnitte der Projektseite (Standard: Physics, Mechanical, Thermal, Chemical, "Electric and Magnetic") |
| `--offline` | Property-Liste aus [properties_snapshot.json](properties_snapshot.json) statt live |
| `--csv` | Ergebnis zusätzlich als CSV schreiben (gitignoriert) |
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
| `in_property_map` | interner Schlüssel, falls die Property in `PROPERTY_MAP` steht |
| `mp_quelle` | `ja`, wenn dafür auch ein Feldpfad in `MP_FIELD_MAP` existiert — nur dann kann das Materials Project den Wert überhaupt liefern |

`PROPERTY_MAP` und `MP_FIELD_MAP` werden aus
[../materialswiki/cli.py](../materialswiki/cli.py) **importiert, nicht
kopiert** — die Auswertung kann also nicht veralten, wenn dort etwas ergänzt
wird.

Von den 64 Properties der Liste überschneidet sich das Materials Project mit
fünf — Dichte (`P2054`), Kristallsystem (`P556`), Kompressionsmodul
(`P5668`), Schubmodul (`P5673`) und Poissonzahl (`P5593`). Welche MP-Felder
bewusst nicht übernommen sind und warum, steht im Abschnitt „Abgedeckte
Properties" in [../materialswiki/README.md](../materialswiki/README.md).

## Vor dem Einsatz anpassen

`USER_AGENT` oben im Skript mit echtem Namen/Kontakt füllen. Zwischen den
Abfragen liegt eine Pause von 1 s.
