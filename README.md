# WikiKnowledgeGraph

Werkzeuge rund um die Frage: **Welches Wissen fehlt in Wikidata noch als
strukturierte Aussage?** Alle erzeugen ausschließlich Vorschlagslisten,
Auswertungen und Graphen zur manuellen Prüfung — es wird nie automatisch nach
Wikidata geschrieben.

| Anwendung | Verzeichnis | Was sie macht |
|---|---|---|
| **Wikidata Knowledge Graph** | [wikikg/](wikikg/) | Vergleicht die ausgehenden Links eines Wikipedia-Artikels mit den Statements des zugehörigen Wikidata-Items und zeigt fehlende Beziehungen. Enthält zusätzlich den browserbasierten *Wortfeld-Explorer*. |
| **Materials Wiki** | [materialswiki/](materialswiki/) | Holt Strukturdaten aus der Crystallography Open Database, kuratierte Materialdaten aus dem Materials Project und, für alles Fehlende, aus den Wikipedia-Infoboxen; schlägt daraus Wikidata-Statements für bereits existierende Items vor (CSV + QuickStatements-Entwurf). **Braucht einen API-Schlüssel** (nur für das Materials Project, COD ist frei zugänglich). |
| **Benchmark** | [benchmark/](benchmark/) | Misst, wie gut metallische Werkstoffe in Wikidata belegt sind — je Property aus dem WikiProject Materials. Zeigt, wo Vorschläge sich überhaupt lohnen. |
| **Material class structure** | [Material%20class%20structure/](Material%20class%20structure/) | Zwei Werkzeuge zur Klassenhierarchie der Werkstoffe. *ClassCheck* prüft auf zwölf Arten, wie `P279` („Unterklasse von") verwendet wird — fehlende, doppelte, verkehrte und mit `P31` verwechselte Kanten, dazu die fehlende chemische Metaklasse der Legierungen — und schreibt **eine gestaffelte Empfehlung**: vier Stufen nach Beweiskraft, ausführbar ist nur die erste. *visualisierung* zeichnet, wie Werkstoffe unter `material` (Q214609) hängen und welche über einen parallelen Zweig laufen. |
| **Anwendungen** | [Anwendung/](Anwendung/) | Leitet ab, **wozu** ein Werkstoff gebraucht wird: aggregiert die `P186`-Rückverweise der Objekte (21495 Items der Klasse „Münze" nennen Bronze) zu `P366`-Vorschlägen am Werkstoff und entwirft, wo es ohne Quantorensprung geht, die Rückkante `P186` am Anwendungsitem. Filtert dabei Verbundgegenstände (Wolkenkratzer, Fahrzeuge) und zu eng gefasste Klassen heraus. Für `P2079`, das in Wikidata fast leer ist, liest sie die Herstellungsabschnitte der deutschen und englischen Wikipedia aus und schlägt die dort verlinkten Verfahren mit Beleg auf die Artikelversion vor. |

Details, Nutzung und Grenzen stehen jeweils im README der Anwendung:
[wikikg/README.md](wikikg/README.md) ·
[materialswiki/README.md](materialswiki/README.md) ·
[benchmark/README.md](benchmark/README.md) ·
[Material%20class%20structure/README.md](Material%20class%20structure/README.md) ·
[Anwendung/README.md](Anwendung/README.md) ·

## Repo-Aufbau

```
wikikg/        Wikipedia ↔ Wikidata Abgleich
  cli.py             Kommandozeile (python -m wikikg)
  compare.py         reine Vergleichslogik, netzwerkfrei und offline testbar
  wikipedia_client.py  MediaWiki-API: Titel → QID, ausgehende Links
  wikidata_client.py   Wikidata-API: ausgehende Item-Statements, Property-Labels
  web/               Wortfeld-Explorer (statisches HTML, D3 + SPARQL)
materialswiki/ Materials Project → Wikidata Vorschläge
  cli.py             Kommandozeile (python -m materialswiki) inkl. Abgleichlogik
  Werkstoff wikidata vorschläge.py
                     Multi-Source-Variante (Materials Project + PubChem)
benchmark/     Abdeckungsmessung der Werkstoff-Properties in Wikidata
  benchmark.py       Kommandozeile (python -m benchmark.benchmark)
  properties_snapshot.json  Momentaufnahme der Property-Liste (für --offline)
Material class structure/  Klassenhierarchie der Werkstoffe: prüfen und zeichnen
  ClassCheck.py             zwölf Strukturprüfungen -> gestaffelte Empfehlung
  visualisierung.py         Anbindung an die Wurzel als Graph (PNG)
  wikidata_graph.py         gemeinsame Wikidata-Zugriffsschicht beider Skripte
Anwendung/     Anwendungen der Werkstoffe (P366/P186/P2079) entwerfen
  Anwendung.py       Kommandozeile (python "Anwendung/Anwendung.py")
lauf.py        Sammelbefehl: Benchmark + materialswiki + ClassCheck je Gruppe
tests/         Offline-Tests (pytest)
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

[requirements.txt](requirements.txt) enthält alles: `requests` für alle
Anwendungen, `networkx` + `matplotlib` zusätzlich für die
Kategorie-Hierarchie-Graphen und `pytest` für die Tests.

Gestartet wird aus dem Repo-Wurzelverzeichnis heraus:

```bash
python -m wikikg --title Holz --lang de
python -m materialswiki --elements Ti O --max 50
python -m benchmark.benchmark --offline
python "Anwendung/Anwendung.py"
python "Material class structure/visualisierung.py"
```

`python -m lauf` bündelt Benchmark, `materialswiki` und die Strukturprüfung
(`ClassCheck.py`) zu **einem** kurzen Befehl je Werkstoffgruppe; alle
Ergebnisse tragen denselben Zeitstempel und landen zusammen in `--out-dir`
(Default `proposals/`):

```bash
python -m lauf legierungen                  # Benchmark + materialswiki
python -m lauf legierungen --struktur        # zusätzlich die Klassenstruktur
python -m lauf polymer --struktur            # Polymere/Kunststoffe (Q11474)
python -m lauf magnetwerkstoffe --struktur   # Magnetwerkstoffe (Q949573)

# nur die Strukturprüfung (ClassCheck.py), für JEDE Grundgesamtheit:
python -m lauf struktur benannte-legierungen
python -m lauf struktur oxide
python -m lauf struktur material --limit 500
python -m lauf struktur periodensystem -- --ohne-dichte
```

`python -m lauf struktur <population>` deckt auch `material` und
`metallischer-werkstoff` ab, die kein Benchmark-Gegenstück haben. ClassCheck
lässt sich weiterhin direkt aufrufen — mit `--out-dir` landet die Empfehlung
im selben `proposals/`-Ordner.

## Ausgabedateien

Vorschlagsdateien (CSV, QuickStatements, die gestaffelte Empfehlung) landen in
**`proposals/`** (CLAUDE.md, „Arbeitsweise" Punkt 2) — `--out` / `--qs-out` /
`--csv` / `--out-dir` verlegen sie. Graphen und `--output` bleiben im
aktuellen Arbeitsverzeichnis. Alle diese Dateien sind Momentaufnahmen eines
Laufs und stehen in [.gitignore](.gitignore) — sie gehören nicht ins Repo:

| Datei | Erzeugt von |
|---|---|
| `proposals/vorschlaege_<Zeitstempel>.csv`, `proposals/qs_<Zeitstempel>.txt` | [materialswiki/cli.py](materialswiki/cli.py) |
| `werkstoffe_vorschlaege.csv`, `werkstoffe_qs_entwurf.txt` | [materialswiki/Werkstoff wikidata vorschläge.py](materialswiki/Werkstoff%20wikidata%20vorschl%C3%A4ge.py) |
| `abdeckung.csv` (bzw. was `--csv` angibt) | [benchmark/benchmark.py](benchmark/benchmark.py) |
| `proposals/qs_class_<Population>_<Zeitstempel>.txt` (und `qs_class_befunde_*.csv` nur mit `--csv`) | [Material class structure/ClassCheck.py](Material%20class%20structure/ClassCheck.py) |
| alle drei Schritte (`abdeckung_*`, `qs_*`, `qs_class_*`) mit gemeinsamem Zeitstempel in `--out-dir` (Default `proposals/`) | [lauf.py](lauf.py) |
| `proposals/anwendungen_befunde_<Zeitstempel>.csv`, `proposals/qs_anwendungen_<Zeitstempel>.txt` | [Anwendung/Anwendung.py](Anwendung/Anwendung.py) |
| `werkstoff_check.csv`, `werkstoff_graph.png`, `trace_*.png`, `subclass_tree_material.png` (nur `--tree`) | [Material class structure/visualisierung.py](Material%20class%20structure/visualisierung.py) |
| `output/…` (`--output`) | [wikikg/cli.py](wikikg/cli.py) |

Einzige bewusst versionierte Ergebnisdatei ist
[benchmark/properties_snapshot.json](benchmark/properties_snapshot.json):
Sie hält die Property-Liste der Projektseite fest und macht `--offline`-Läufe
reproduzierbar.

## Rate Limits und User-Agent

Alle Skripte drosseln sich auf eine Anfrage pro Sekunde
(`REQUEST_DELAY_SEC = 1.0`). Vor produktiver Nutzung ist der `USER_AGENT` im
jeweiligen Skript mit echtem Namen und Kontaktadresse zu füllen — so verlangt
es die
[Wikimedia-User-Agent-Richtlinie](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy).

## Zugangsdaten (`.env`)

API-Schlüssel und Kontaktadresse stehen an **einer** Stelle: `.env` im
Repo-Wurzelverzeichnis. Die Datei ist in [.gitignore](.gitignore) eingetragen
und wird nie committet — im Quelltext steht kein Zugangsdatum mehr.

Einrichten:

```bash
cp .env.beispiel .env
chmod 600 .env
# dann .env ausfüllen
```

| Eintrag | Wofür |
|---|---|
| `MP_API_KEY` | Materials Project, Pflicht für `materialswiki` (kostenlos unter <https://next-gen.materialsproject.org/api>) |
| `CONTACT_EMAIL` | landet im User-Agent **aller** Anwendungen — so verlangt es die Wikimedia-Richtlinie |
| `CONTACT_NAME` | Klarname für den User-Agent (optional) |
| `MP_ACCOUNT_EMAIL`, `WIKIDATA_USERNAME` | nur zur Dokumentation, werden nicht abgefragt |

[.env.beispiel](.env.beispiel) ist die versionierte Vorlage und enthält nur
Platzhalter.

Gelesen wird in dieser Rangfolge: **echte Umgebungsvariable → `.env` →
Vorgabewert im Skript**. Die Umgebung gewinnt, damit sich ein einzelner Lauf
umstellen lässt, ohne die Datei zu ändern:

```bash
MP_API_KEY=zweitschluessel python -m materialswiki --periodic-table
```

Gelesen wird über [konfig.py](konfig.py) — 20 Zeilen ohne zusätzliche
Abhängigkeit; `python-dotenv` wäre dafür zu viel.

## Tests

```bash
pytest
```

Getestet wird die netzwerkfreie Logik:

| Datei | Deckt ab |
|---|---|
| [tests/test_compare.py](tests/test_compare.py) | Wikipedia-↔-Wikidata-Vergleich |
| [tests/test_formula.py](tests/test_formula.py) | Formel-Normalisierung und Infobox-Parser |
| [tests/test_mp.py](tests/test_mp.py) | Materials-Project-Feldabbildung und Einheitenumrechnung |
| [tests/test_quickstatements.py](tests/test_quickstatements.py) | Aufbau des QuickStatements-Entwurfs |

Alle Tests laufen offline und brauchen **keinen** API-Schlüssel.

## Datenquellen und deren Lizenzen

Die Vorschlagslisten (`vorschlaege*.csv`, `qs_*.txt`)
enthalten abgeleitete Daten aus fremden Datenbanken. Wer sie weitergibt, gibt
diese Daten mit weiter — deshalb hier die Herkunft und die jeweiligen
Bedingungen:

| Quelle | Lizenz | Was daraus stammt | Pflichten |
|---|---|---|---|
| Wikidata selbst (P274) | CC0 (Public Domain) | „besteht aus" (P527) und „enthält Elemente von" (P2670), aus der Summenformel abgeleitet — **Stufe abgeschaltet**, nur mit `--formel` | keine |
| [Materials Project](https://next-gen.materialsproject.org/) | CC BY 4.0 | Dichte, elastische Moduln, Poissonzahl; Kristallsystem nur als Rückfall | Namensnennung + Zitierung, siehe unten |
| [Crystallography Open Database](https://www.crystallography.net/cod/) | CC0 (Public Domain) | Raumgruppe, Kristallsystem, COD-ID | keine; Nennung der Originalautoren erbeten |
| Wikipedia (de/en) | CC BY-SA 4.0 | Infobox-Werte als Rückfall | Namensnennung, Weitergabe unter gleichen Bedingungen |

### Materials Project: Zitierpflicht

Die [Nutzungsbedingungen](https://next-gen.materialsproject.org/about/terms)
stellen die Daten unter **CC BY 4.0** und verlangen die Zitierung der
Hauptpublikation:

> A. Jain, S.P. Ong, G. Hautier, W. Chen, W.D. Richards, S. Dacek, S. Cholia,
> D. Gunter, D. Skinner, G. Ceder, K.A. Persson: *The Materials Project: A
> materials genome approach to accelerating materials innovation.*
> APL Materials 1(1), 011002 (2013). [doi:10.1063/1.4812323](https://doi.org/10.1063/1.4812323)

Für einzelne Datensätze kommt eine **eigene Zitierung hinzu**. Betroffen sind
hier Kompressionsmodul, Schubmodul und Poissonzahl:

> M. de Jong et al.: *Charting the complete elastic properties of inorganic
> crystalline compounds.* Scientific Data 2:150009 (2015).
> [doi:10.1038/sdata.2015.9](https://doi.org/10.1038/sdata.2015.9)

Beide DOIs schreibt `materialswiki` automatisch in den Referenzblock jeder
betroffenen Aussage (`MP_DATASET_DOI` in [materialswiki/cli.py](materialswiki/cli.py)).

Weiter gilt laut Nutzungsbedingungen: Die Website darf **nicht gescrapt**
werden — der Zugriff läuft ausschließlich über die offizielle API. Größere
Abrufe sollen vorab beim MP-Support angekündigt werden. Und: die Daten sind
**berechnet** (DFT bei 0 K), nicht gemessen; jede erzeugte Aussage trägt
deshalb den Qualifikator P459 „berechnet (Dichtefunktionaltheorie)".

### Hinweis zum Import nach Wikidata

Wikidata veröffentlicht alle Inhalte unter **CC0** — eine Lizenz, die eine
Attributionspflicht *nicht* weiterträgt. Der Import von CC-BY-Daten (Materials
Project) und CC-BY-SA-Daten (Wikipedia) stützt sich darauf, dass einzelne
Faktenaussagen nicht urheberrechtlich schutzfähig sind und die Attribution
über die mitgeschriebene Referenz faktisch geleistet wird. Bei einem
systematischen Massenimport kann zusätzlich das Datenbankherstellerrecht
berührt sein. Das ist der Grund, warum die Werkzeuge hier ausschließlich
Vorschlagslisten erzeugen und **nie automatisch nach Wikidata schreiben** —
und warum COD (CC0) für Struktur­angaben die bevorzugte Quelle ist, wo es
etwas liefert.

Die Stufe „Formel" war von alledem nicht betroffen: sie leitet P527 und P2670
aus der Summenformel ab, die am Wikidata-Item bereits steht. Es wird nichts von
außen geholt und nichts weitergegeben — deshalb tragen diese Aussagen auch
keinen Beleg, sondern nur die Herkunftsnotiz in der CSV-Spalte `ref_note`.

**Seit dem 27.08.2026 ist diese Stufe abgeschaltet**: P527 und P2670 sollen
nicht mehr vorgeschlagen werden, und sie ist die einzige Stufe, die beide
erzeugt — samt der Umstellung bestehender Aussagen „Stoff P527 Element" auf
P2670, der einzigen Stufe mit Löschzeilen. Der Code bleibt erhalten; `--formel`
schaltet ihn für einen einzelnen Lauf wieder ein.

## Lizenz

Der **Code** steht unter der Lizenz in [LICENSE](LICENSE). Für die **Daten**
in den erzeugten Ausgabedateien gelten die Lizenzen der jeweiligen Quelle
(siehe oben).
