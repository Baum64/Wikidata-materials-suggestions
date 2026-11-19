# pmdmap – PMDco ↔ Wikidata abgleichen

Pilot zum Konzept [docs/konzept_bfo_wikidata_mapping.md](../docs/konzept_bfo_wikidata_mapping.md)
(Entscheidungen E1–E7). Das Werkzeug gleicht die PMD-Kernontologie (PMDco) mit
Wikidata ab und erzeugt ein **Prüf-Dokument**, das zugleich der
QuickStatements-Entwurf ist: Vorschläge stehen als fertige QS-Zeilen darin,
Unsicheres ist mit `#` auskommentiert. Entschieden wird durch Löschen oder
Setzen des `#`; danach wird die **ganze Datei** in QuickStatements
eingefügt – die `#`-Zeilen verwirft QuickStatements dabei.

**pmdmap schreibt nie in Wikidata.** Es liest Ontologie, Linksuche,
Query-Service und Action-API; alle Ergebnisse landen unter `proposals/pmdmap/`.

## Stand

| Paket | Inhalt | Stand |
|---|---|---|
| 0 | Bestand der vorhandenen PMD-Links prüfen | umgesetzt (`fetch`, `review --paket 0`) |
| 1 | Pilot-Werkstoffe: Kandidaten für fehlende Links | umgesetzt (`review --paket 1`) |
| 2 | Pilot-Eigenschaften inkl. P1628 | umgesetzt (`review --paket 2`) |
| 3 | Prüf-Dokument `quickstatements_<datum>.txt` (+ Beleg-Tabelle CSV) | umgesetzt für Pakete 0–2 |
| 4 | Prüfung vor dem Einfügen / Teil-Dateien (`export`) | umgesetzt |

## Aufruf

Aus dem Repo-Wurzelverzeichnis (dort liegt `config.yaml`):

```bash
pip install -r requirements.txt          # braucht rdflib, pyyaml, pandas, requests

python -m pmdmap fetch                   # Ontologie + Wikidata-Bestand -> cache/
python -m pmdmap review --paket 0        # Prüftabelle, Bericht, review-needed.md
python -m pmdmap review --paket 1 2      # Kandidaten für Pilot-Werkstoffe/-Eigenschaften
python -m pmdmap export --review proposals/pmdmap/quickstatements_<datum>.txt --nur-pruefen
python -m pmdmap fetch --refresh         # Cache ignorieren
```

Jedes `review` schreibt das Prüf-Dokument **über alle Pakete** neu und
**behält dabei, was im vorhandenen Dokument aktiviert oder auskommentiert
wurde** (erkannt an der QS-Zeile ohne Quellenteil). Aktive Zeilen, die nicht
mehr vorgeschlagen werden, landen in einem eigenen Abschnitt am Ende – es geht
nichts verloren. Die Beleg-Tabelle (CSV) wird ebenfalls zusammengeführt.

### Pakete 1 und 2 – Kandidaten

- **Auswahl** (`config.yaml`): `pilot_werkstoffe.pflicht` nach Label;
  fehlt eine Klasse in der Ontologie (PMDco 3.1.2: *wood*, *concrete*),
  wird das als Lücke gemeldet. Aufgefüllt wird bis `max_klassen` mit
  unverlinkten Klassen unter *material*/*metal* – zuerst Minimalprofil,
  dann nach Zahl der Unterklassen. `pilot_eigenschaften` nach Label,
  optional mit `hinweis` (z. B. E7 bei Härte).
- **Suche** je Klasse mit Label (en/de) und Synonymen: Labelsuche
  (`wbsearchentities`) und Volltext mit `haswbstatement:P279`.
  Top-3 Einträge je Klasse; in Paket 2 zusätzlich Top-2
  Wikidata-Eigenschaften für P1628 (über P1687 des Begriffs-Eintrags,
  P1629 der Eigenschaft und Labelsuche).
- **Vorschläge**: `neu: P1709` (Regel: Rang 1, gleiches Label, Klasse,
  in Paket 1 unter *material*), `neu: P2888+P4390` (nur per Einschätzung),
  `neu: P1628`, `verwerfen`, `offen`. Einschätzungen in
  `pmdmap/einschaetzungen/pmdco_kandidaten.yaml`.
- `P1628` nur an Eigenschaften (P…), `P1709` nur an Einträgen (Q…) –
  der Export prüft das.

Ergebnisse:

| Datei | Inhalt |
|---|---|
| `proposals/pmdmap/quickstatements_<datum>.txt` | **Prüf-Dokument = Batch**: Erläuterungen (`##`) + Vorschläge als QuickStatements-Zeilen, aktiv oder `#`-auskommentiert; als Ganzes einfügbar |
| `proposals/pmdmap/review_<datum>.csv` | Beleg-Tabelle (UTF-8, Semikolon) – alle Spalten zum Nachschlagen; die Spalten `entscheidung*` werden nicht mehr gebraucht |
| `proposals/pmdmap/qs_{neu,umstellen,entfernen,eigenschaften}_partNN.txt` | nur mit `export` ohne `--nur-pruefen`: reine QuickStatements, je Datei höchstens 50 Zeilen |
| `proposals/pmdmap/manuell_eigenschaften.md` | Export: Aussagen an Wikidata-Eigenschaften (P1628/P2888) als Liste |
| `proposals/pmdmap/export_<datum>.md` | Export: Dateien und Hinweise (z. B. Löschungen mit Quellen) |
| `proposals/pmdmap/bestand_<datum>.md` | Bericht Paket 0: Ontologie-Version, Zählungen, Abgleich A2 ↔ Claims, E1 |
| `proposals/pmdmap/kandidaten_<datum>.md` | Bericht Pakete 1–2: Top-Kandidaten je Klasse, P1628-Kandidaten |
| `proposals/review-needed.md` | je Paket ein Abschnitt mit allen Grenzfällen (wird bei jedem Lauf ersetzt) |
| `cache/pmdco/bestand_<datum>.json` | Schnappschuss, aus dem `review` offline arbeitet |

## Prüf-Dokument bearbeiten

| Zeile beginnt mit | Bedeutung |
|---|---|
| `##` | Erläuterung (Labels, Definition, Vorschlag, Begründung) – wird nie exportiert |
| `#Q…` / `#-Q…` / `#P…` | auskommentierter Vorschlag – `#` löschen aktiviert ihn |
| `Q…` / `-Q…` / `P…` | aktiv – geht in den Export |

- **Aktiv vorbelegt** ist nur Sicheres: neue P1709/P1628, bei der Regel und
  Einschätzung übereinstimmen, ohne Grenzfall. Alles andere – und jede
  Löschung bestehender Aussagen – ist auskommentiert.
- **Umstellen** (P1709 → P2888) besteht aus Löschzeile `-Q…|P1709|"…"` und
  neuer Zeile `Q…|P2888|"…"|P4390|…`: beide aktivieren. P4390 lässt sich in der
  Zeile ändern (QID nach `P4390|`); im Kopf des Dokuments stehen die Werte.
- **Danach die ganze Datei in QuickStatements (V1) einfügen.** Die
  `#`-Zeilen werden dabei verworfen (Erfahrung im Projekt; die Hilfeseite
  dokumentiert Kommentarzeilen nicht – im Zweifel die Vorschau ansehen).
  Deshalb enthält das Dokument nichts Aktives, was nicht ausgeführt werden
  soll: auch Zeilen aus einer früheren Fassung, die nicht mehr vorgeschlagen
  werden, stehen auskommentiert am Ende.

`export --nur-pruefen` ist die empfohlene Prüfung vor dem Einfügen; ohne
`--nur-pruefen` schreibt `export` zusätzlich Teil-Dateien à 50 Zeilen.
Bei Fehlern wird **nichts** geschrieben. Geprüft werden:
Zeilenformat, Klassen-IRI (Muster, in der Ontologie, nicht veraltet),
P2888 nur mit erlaubtem P4390, P1709/P1628 ohne P4390, P1709 nur an Q…,
P1628 nur an P…, Quelle S248/S813 vorhanden, keine doppelten aktiven
Zeilen. Hinweise (kein Abbruch): Löschung einer Aussage mit Quellen,
halbe Umstellung (Löschen ohne neue Zeile), zweite P1709 an einem Eintrag
oder an einer Klasse, Aussage existiert schon. Eine Umstellung wird nie
auf zwei Blöcke verteilt; alte `qs_*_partNN.txt` werden vorher entfernt.

### Wie der Vorschlag entsteht

`begruendung` trennt zwei Quellen:

- **Regel:** mechanische Prüfungen in `pmdmap/assessment.py` – gültige und
  nicht veraltete IRI, Property (P1709/P2888/P3950), P4390 vorhanden und
  zulässig, Labels (inkl. Synonyme) stimmen in en oder de überein, Eintrag ist
  ein chemisches Element, dieselbe PMD-Klasse an mehreren Einträgen,
  Begriffsart, E7-Hinweis auf die zugehörige Wikidata-Eigenschaft.
- **Einschätzung:** fachliche Einschätzung nach Vergleich der Definitionen,
  gepflegt in `pmdmap/einschaetzungen/pmdco.yaml`. Sie ersetzt den Vorschlag,
  nie die Befunde der Regeln.

Vorschläge Paket 0: `behalten`, `P4390 ergänzen`, `umstellen auf
P2888+P4390`, `entfernen`, `offen`. „offen“ und als Grenzfall markierte
Zeilen stehen zusätzlich in `proposals/review-needed.md`.

## Datenquellen und Grenzen

- **PMDco** über `https://w3id.org/pmd/co/` (Content Negotiation → Turtle).
  Version aus `owl:versionIRI`, Abgleich mit der neuesten GitHub-Release.
- **Bestand**: MediaWiki-Linksuche (`exturlusage`) und Abfrage A2 aus dem
  Konzept, ergänzt um P3950. Danach werden alle Einträge per `wbgetentities`
  geholt und die Abbildungen direkt aus den Claims gelesen; der Bericht zeigt,
  was A2 übersieht. Kein Massen-Scan über alle P1709/P2888-Aussagen.
- **Erlaubte P4390-Werte** aus dem one-of-Constraint (P2302/P2305) von P4390.
- **E1-Prüfung**: Von den Werkstoff-Einträgen aus (auf PMD-Werkstoffklassen
  abgebildet, plus Unterklassen neuer Einträge mit PMD-/BFO-Link) wird die
  P279-Kette per `wbgetentities` nach oben verfolgt. Gemeldet wird jede Kante
  „Werkstoff → Konstrukt“; Konstrukt = neu angelegter Eintrag (QID ab
  `e1.neu_ab_qid`) mit eigener Abbildung auf eine Fremdontologie oder mit
  einer Beschreibung wie „DOLCE class“ (`e1.konstrukt_beschreibung`).
  SPARQL mit `wdt:P279*` lief dafür am 19.11.2026 durchweg in HTTP 504.

## Netz

- User-Agent aus `config.yaml`; ist `PMDMAP_KONTAKT` gesetzt, wird der Wert
  angehängt (Wikimedia-Richtlinie). Er steht absichtlich nicht im Repo.
- Drosselung je Gegenstelle (`netz.drosselung_s`), Retry bei 429/5xx mit
  `Retry-After`. Der Query-Service war am 19.11.2026 auf 1 Anfrage/Minute
  gedrosselt – daher 61 s; nach der Störung kann der Wert sinken.
- Cache unter `cache/` (7 Tage, `--refresh` erzwingt Neuladen).

## Zweite Ontologie (MWO)

Ein weiteres Profil unter `ontologien:` in `config.yaml` (Basis-IRI,
IRI-Muster, Linksuche, Download-URLs, Ankerklassen für die Begriffsart,
Quellen-QID) und `--ontologie mwo`. Der Code enthält keine PMD-spezifischen
Konstanten.

## Tests

```bash
python -m pytest tests/test_pmdmap_*.py
```

Netzfrei: `conftest.py` sperrt `pmdmap.http._send`.
