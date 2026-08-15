# materialswiki — Materials Project → Wikidata

Erzeugt aus dem [Materials Project](https://next-gen.materialsproject.org) —
und, für alles Fehlende, aus den Wikipedia-Infoboxen — Vorschlagslisten für
Wikidata-Statements. Das Skript **legt keine neuen Wikidata-Items an und
schreibt nichts automatisch nach Wikidata** — es liefert CSV-Kandidaten zur
manuellen Prüfung.

## Warum Materials Project und nicht mehr NOMAD

NOMAD lieferte wenige und in der Einzelprüfung nicht belastbare Werte. Der
Grund ist strukturell: NOMAD sammelt **einzelne Rechnungen**, ohne Aussage
darüber, ob das gerechnete Material real existiert oder überhaupt stabil ist.
Ein Wert konnte aus einer hypothetischen Struktur stammen, und man sah es der
Zeile nicht an.

Das Materials Project pflegt dagegen kuratierte Materialdokumente und macht
genau diese Einordnung **als Query-Parameter** abfragbar:

| Filter | Bedeutung | Default |
|---|---|---|
| `theoretical=false` | experimentell nachgewiesen, in aller Regel ICSD-hinterlegt | an (`--no-experimentell` schaltet ab) |
| `is_stable=true` | auf der konvexen Hülle, thermodynamisch stabil | an (`--no-stabil` schaltet ab) |
| `deprecated=false` | keine zurückgezogenen Dokumente | immer an |

Damit fällt genau das weg, was die NOMAD-Ausbeute unbrauchbar machte.
`--no-experimentell` lässt auch rein gerechnete Strukturen zu — die Ausbeute
steigt dann, die Verlässlichkeit sinkt aber genau so, wie sie es bei NOMAD tat.

Zwei weitere Verbesserungen fallen nebenbei ab:

- **Eine Anfrage statt 1+N.** Ein MP-Materialdokument enthält Formel,
  Symmetrie und alle Kennwerte auf einmal; NOMAD brauchte je Eintrag einen
  zweiten Archiv-Abruf.
- **Eine Größe mehr.** MP führt die Poissonzahl (`P5593`) als Skalar, NOMAD
  nicht. Abgedeckt sind damit fünf statt vier Properties.

## API-Schlüssel (Pflicht)

Die Materials-Project-API verlangt einen Schlüssel; ohne ihn antwortet jeder
Endpunkt mit HTTP 401, mit einem falschen Schlüssel mit HTTP 403. Beides fängt
das Skript mit einer verständlichen Meldung ab (Exit-Code 2) statt mit einem
Traceback.

Kostenlos anlegen unter <https://next-gen.materialsproject.org/api>, dann:

```bash
export MP_API_KEY="..."
```

Bewusst als Umgebungsvariable und **nicht** im Quelltext: ein Schlüssel im
Repo wäre ein Leck, sobald das Repo geteilt wird.

## Die Werte sind gerechnet, nicht gemessen

Das ist die wichtigste Einschränkung, und sie bleibt auch mit den
Qualitätsfiltern bestehen: MP-Werte sind **DFT-Rechnungen bei 0 K am idealen
Einkristall**. Handbuchwerte stammen dagegen aus Messungen bei
Raumtemperatur an realem, polykristallinem Material mit Defekten und Textur.

Am Bestand geprüft (2026-08-15, Läufe über Cu, Fe, Ti):

| Größe | Abweichung vom Handbuchwert |
|---|---|
| Kristallsystem | exakt richtig |
| Dichte | +0,4 % bis +3,6 % |
| Kompressionsmodul | +2,6 % bis +21,8 % |
| Schubmodul | −17,6 % bis **+41,4 %** |
| Poissonzahl | −16,6 % bis +21,7 % |

Konkret: MP gibt für Titan einen Schubmodul von 62 GPa an, der Handbuchwert
liegt bei 44 GPa. Für Eisen kommt die Poissonzahl mit 0,353 statt 0,29 —
Eisen ist magnetisch, und das ist für DFT ein bekannt schwieriger Fall.

**Folge für die Durchsicht:** Dichte und Kristallsystem lassen sich weitgehend
bedenkenlos übernehmen. Bei den elastischen Moduln und der Poissonzahl ist
jede Zeile gegen Literatur zu prüfen — sonst steht am Wikidata-Item eines
Werkstoffs ein Wert, der 40 % neben dem liegt, was ein Ingenieur erwartet.

### Die Kennzeichnung steht im Statement selbst

Der Beleg sagt, **woher** ein Wert kommt; die Bestimmungsmethode sagt, **wie**
er zustande kam. Beides wird gebraucht. Jede MP-Aussage trägt deshalb den
Qualifikator

```
P459  „Bestimmungsmethode oder -standard"  →  Q1048589  Dichtefunktionaltheorie
```

In QuickStatements V1 steht er in derselben Zeile, **zwischen Wert und Beleg**
— Qualifikatoren tragen das `P`-Präfix, Belege das `S`-Präfix:

```
Q753	P5673	49843000000.0U44395	P459	Q1048589	S356	"10.1063/1.4812323"
        └ Schubmodul ┘ └ Wert + Einheit ┘  └ gerechnet ┘  └ Beleg ┘
```

Die Reihenfolge ist nicht beliebig: stünde der Beleg vor dem Qualifikator,
hängte QuickStatements den Qualifikator an die Referenz statt an die Aussage.
Ein Test hält das fest.

In der CSV steht dasselbe lesbar in der Spalte `bestimmungsmethode`.

Verifiziert am 2026-08-15:

- `P459` ist itemwertig, und sein Property-Scope-Constraint nennt ausdrücklich
  **„als Qualifikator"** — die Verwendung ist also vorgesehen, nicht bloß
  geduldet.
- `Q1048589` ist „density functional theory", beschrieben als *computational
  quantum mechanical modelling method to investigate the electronic
  structure* (P31/P279: algorithm, computational chemistry, computational
  physics). Das ist die Elektronenstruktur-DFT, die MP rechnet — **nicht**
  `Q1209474`, ein labelloser Stub gleichen Namens (die klassische DFT der
  statistischen Mechanik).

**Wikipedia-Werte bekommen bewusst keinen Qualifikator.** Das sind
Literaturwerte, und mit welcher Methode sie bestimmt wurden, steht in der
Infobox nicht — eine Methode zu behaupten wäre geraten.

Zusätzlich trägt jede MP-Zeile den Vermerk `berechnet (DFT)` an erster Stelle
der Belegnotiz, damit es auch beim Überfliegen des Entwurfs auffällt.

## Warum nicht `mp-api`?

Das Materials Project empfiehlt seinen eigenen Python-Client `mp-api` und
merkt an, außerhalb davon keinen Support zu leisten. Hier wird trotzdem direkt
per `requests` gegen die REST-API gegangen — aus zwei Gründen:

**Abhängigkeitsgewicht.** `mp-api` zieht (Stand 0.46.4) **46 Pakete** nach
sich, darunter pymatgen, emmet-core, scipy, pandas, sympy, plotly, boto3,
pyarrow und deltalake. Dieses Repo kommt sonst mit `requests` aus. Für einen
API-Aufruf, der als Rohdaten-Abruf ~60 Zeilen braucht, ist das kein guter
Tausch — zumal `mp-api` mindestens Python 3.11 verlangt.

**Es hilft nur der kleineren Hälfte.** Der Aufwand dieses Projekts steckt
nicht im Datenabruf, sondern im Abgleich mit Wikidata: Formel-Normalisierung,
Mehrdeutigkeitsauflösung, Statement-Prüfung, Beleg- und Qualifikatorenmodell,
QuickStatements-Erzeugung. Dazu trägt `mp-api` nichts bei — es kennt Wikidata
nicht. Ein „Mergen" mit Wikidata gibt es dort nicht als Funktion.

Was `mp-api` allerdings *richtig* macht und hier nachgebaut werden musste:

- **Paginierung.** Die API deckelt eine Seite bei 1000 Dokumenten
  (`meta.max_limit`) und liefert klaglos weniger, wenn man mehr anfordert.
  Größere Mengen holt das Skript deshalb seitenweise über `_skip`.
- **Einen akzeptierten User-Agent** (siehe unten).

Sollte sich das Verhältnis umkehren — etwa weil Strukturdaten, Phasendiagramme
oder Elektronenstrukturen gebraucht werden, für die pymatgen ohnehin nötig
wäre — ist der Wechsel klein: der Datenabruf steckt vollständig in
`fetch_mp_materials`, alles danach arbeitet auf schlichten dicts.

## Zwei User-Agents

Die beiden Gegenstellen verlangen Gegensätzliches:

- **Wikimedia** verlangt laut User-Agent-Richtlinie eine sprechende Kennung
  mit Kontakt; „Bot" im Namen ist dort üblich und erwünscht.
- **Materials Project** blockt genau das. Am Bestand geprüft (2026-08-15):
  mit `MaterialsWikidataSuggestBot/0.1` antwortet die API **HTTP 403
  „Forbidden", obwohl der Schlüssel gültig ist** — und zwar bevor sie den
  Schlüssel überhaupt prüft. Ausschlaggebend ist allein das Wort „Bot":
  `SomethingBot/1.0` → 403, dieselbe Kennung ohne „Bot" → 200.
  Kontaktangaben stören nicht.

Ein gemeinsamer User-Agent kann beides nicht erfüllen, deshalb gibt es zwei.
Die Kontaktadresse steht nur an **einer** Stelle (`CONTACT` in
[cli.py](cli.py)), beide Kennungen bauen darauf auf.

Wer hier etwas ändert: Ein „Bot" in `MP_USER_AGENT` führt zu einem 403, das
wie ein Schlüsselproblem aussieht und keines ist. Ein Test hält das fest.

## Ablauf

1. Materialien aus dem Materials Project holen, gefiltert wie oben.
2. Das Material gegen **bestehende** Wikidata-Items abgleichen — über die
   Summenformel (`P274`, siehe Formel-Normalisierung) bzw. im
   Periodensystem-Modus über das Elementsymbol (`P246`). Mehrdeutige Treffer
   (z.B. Polymorphe) werden als `MANUELLE_KLAERUNG_NOETIG` markiert.
3. Prüfen, ob das jeweilige Statement dort bereits existiert.
4. Für alles, was MP nicht liefert, die Wikipedia-Infoboxen heranziehen
   (siehe Quellenkaskade).
5. Alle offenen Kandidaten als CSV-Vorschlagsliste schreiben, plus einen
   QuickStatements-V1-**Entwurf**, der erst nach zeilenweiser manueller Prüfung
   eingespielt werden darf.

## Formel-Normalisierung

Datenbanken und Wikidata schreiben dieselbe Verbindung unterschiedlich auf:

| | Datenquelle | Wikidata |
|---|---|---|
| **Zeichensatz** | ASCII-Ziffern (`TiO2`) | tiefgestellt (`TiO₂`, U+2082) |
| **Reihenfolge** | wechselnd, oft alphabetisch (`O2Ti`) | konventionell, elektropositiv zuerst (`TiO₂`) |

Am Bestand geprüft (2026-08-15): eine Abfrage auf `TiO2`/`Al2O3`/`Fe2O3`
liefert **null** Treffer, auf `TiO₂`/`Al₂O₃`/`Fe₂O₃` dagegen 13. Ein direkter
Stringvergleich muss daran scheitern.

MP liefert mit `formula_pretty` zwar bereits eine aufgeräumte Form (`TiO2`),
aber eben mit ASCII-Ziffern — die Normalisierung bleibt also nötig und deckt
zugleich jede andere Quelle mit ab.

Deshalb wird die Formel jetzt erst in ihre Zusammensetzung `{Element: Anzahl}`
zerlegt, und daraus werden die plausiblen Schreibweisen **erzeugt**:

| Fall | Reihenfolge | Beispiel |
|---|---|---|
| Kohlenstoff **und** Wasserstoff → organisch | Hill (C, H, dann alphabetisch) | `C₁₅H₂₂O₃` |
| sonst → anorganisch | konventionell, nach Pauling-Elektronegativität | `TiO₂`, `Al₂O₃`, `SiC`, `CO₂` |
| immer zusätzlich | alphabetisch | `O₂Ti` |

Jede Variante wird tief- und normalgestellt erzeugt und in **einer** SPARQL-
Abfrage per `VALUES` geprüft. Die Einschränkung auf „C **und** H" ist wichtig:
Ein Carbid wie SiC ist anorganisch, und als Hill-Formel `CSi` geschrieben in
Wikidata nicht auffindbar, obwohl das Item existiert.

Die gefundene Formel wird anschließend **zurückgeparst** und ihre
Zusammensetzung gegengeprüft — eine Nachlässigkeit auf einer der beiden
Seiten fällt so auf.

Nicht deutbare Formeln (Hydratpunkte wie `CuSO4·5H2O`, Ladungen, Freitext)
werden verworfen statt geraten; dann bleibt der ursprüngliche Wortlaut der
einzige Kandidat.

### Mehrdeutigkeit

Weil Wikidata Minerale und Polymorphe als eigene Items führt, ist ein Treffer
oft nicht eindeutig: `O2Ti` findet Titan(IV)-oxid **und** Rutil, Brookit,
Anatas, Akaogiit. Solche Zeilen bleiben `MANUELLE_KLAERUNG_NOETIG` — welches
Polymorph MP beschreibt, ist eine fachliche Entscheidung, keine
Datenfrage. Die in Frage kommenden Items stehen jetzt in der Spalte
`kandidaten`, die Zeile ist also ohne eigene Recherche abarbeitbar.

Ein Sonderfall wird automatisch aufgelöst: **Isotopologe** („Carbon-13C
dioxide", „sodium chloride na-24") tragen dieselbe Formel *und* dieselbe
`P31` wie der echte Stoff, haben aber keinen Enzyklopädie-Artikel. Bei
Mehrdeutigkeit werden deshalb Items ohne de-/en-Sitelink aussortiert; bleibt
genau eines übrig, gilt der Treffer als eindeutig. Ein einzelner artikelloser
Treffer bleibt unangetastet — gefiltert wird nur, wo ohnehin ausgewählt
werden müsste.

## Quellenkaskade

In **beiden Modi dieselbe**; jede Stufe liefert nur, was die vorherige nicht
schon belegt hat:

```
Materials Project (DOI)  →  de.wikipedia (Import)  →  en.wikipedia (Import)
```

Deutsch steht vor Englisch, weil die deutsche Infobox mehr Größen führt (u.a.
spezifische Wärmekapazität, elektrische Leitfähigkeit, Schallgeschwindigkeit,
CAS-Nummer). Welche Infobox gelesen wird, hängt am Artikel:

| | Elemente | Verbindungen |
|---|---|---|
| **de** | `{{Infobox Chemisches Element}}` im Artikel | `{{Infobox Chemikalie}}` im Artikel |
| **en** | `Template:Infobox <element>` | `{{Chembox}}` im Artikel |

Die Artikeltitel kommen aus den Wikidata-Sitelinks, werden also nicht geraten
(Titan liegt unter „Titan (Element)").

Die Wikipedia-Stufen sind **standardmäßig an** und lassen sich mit
`--no-wikipedia` abschalten.

**Temperaturen:** Die deutsche Verbindungsinfobox führt Schmelz- und
Siedepunkt in Grad Celsius, Wikidata erwartet Kelvin. Umgerechnet wird nur,
wenn die Einheit im Feld tatsächlich dasteht — „1843" allein ließe offen, ob
°C oder K gemeint ist, und der Unterschied wäre ein um 273,15 danebenliegender
Wert. Stehen beide da („1855 °C (2128 K)"), gewinnt der Kelvin-Wert. In der
englischen Chembox steckt die Einheit ohnehin im Feldnamen (`MeltingPtC` vs.
`MeltingPtK`).

Die CSV wird **zeilenweise mit `flush()`** geschrieben. Ein
Periodensystem-Lauf dauert wegen der Drosselung viele Minuten; bei Abbruch
(Strg-C) bleibt alles bis zur letzten verarbeiteten Zeile erhalten.

## Nutzung

Aus dem Repo-Wurzelverzeichnis (Installation siehe [../README.md](../README.md)):

```bash
export MP_API_KEY="..."                          # einmal pro Sitzung

python -m materialswiki --elements Ti O --max 50   # Verbindungen, über die Formel
python -m materialswiki --periodic-table           # alle Elemente
python -m materialswiki --elements Ti O --no-wikipedia   # nur MP-Werte
python -m materialswiki --elements Ti O --no-experimentell  # auch Gerechnetes
```

`python -m materialswiki.cli ...` funktioniert gleichwertig.

| Option | Bedeutung |
|---|---|
| `--elements` | Elementfilter, z.B. `--elements Ti O` (alle genannten müssen enthalten sein). Im Periodensystem-Modus beschränkt es den Lauf auf diese Elemente. |
| `--max` | maximale Anzahl MP-Materialien (Standard: 50) |
| `--periodic-table` | Vorschläge für **alle** Elemente des Periodensystems; Abgleich über das Elementsymbol `P246` statt über die Summenformel |
| `--per-element` | MP-Materialien je Element im Periodensystem-Modus (Standard: 1) |
| `--no-experimentell` | auch rein gerechnete Materialien zulassen (`theoretical=true`); mehr Ausbeute, weniger Verlässlichkeit |
| `--no-stabil` | auch thermodynamisch instabile Phasen zulassen (`is_stable=false`) |
| `--no-wikipedia` | die Wikipedia-Stufen abschalten, nur MP-Werte vorschlagen (Standard: Wikipedia an) |
| `--out` | Ziel der CSV-Vorschlagsliste (Standard: `vorschlaege_<Zeitstempel>.csv`) |
| `--qs-out` | Ziel des QuickStatements-Entwurfs (Standard: `quickstatements_entwurf_<Zeitstempel>.txt`) |

### Ausgabedateien

Beide landen im aktuellen Arbeitsverzeichnis und sind gitignoriert (siehe
[../README.md](../README.md#ausgabedateien)). Der Dateiname trägt
standardmäßig einen Zeitstempel (`vorschlaege_2026-08-15_1102.csv`), für CSV
und Entwurf denselben — so überschreibt kein Lauf den vorherigen, und die
beiden Dateien sind als Paar erkennbar.

Wer feste Namen braucht, setzt `--out`/`--qs-out`. Dann wird der
QuickStatements-Entwurf **vor** dem Lauf geleert: Er entsteht erst am Ende,
und ohne das Leeren stünde nach einem Abbruch der vollständige Entwurf des
letzten Laufs neben der frisch und nur teilweise geschriebenen CSV — zwei
Dateien, die nicht zusammengehören. Nach einem Abbruch trägt der Entwurf
deshalb nur die Zeile `# Lauf noch nicht abgeschlossen …`.

### Status in der CSV

| Status | Bedeutung |
|---|---|
| `VORSCHLAG` | Item existiert, Property dort noch nicht gesetzt, Beleg vorhanden → Kandidat |
| `BEREITS_VORHANDEN` | Aussage steht schon in Wikidata |
| `MANUELLE_KLAERUNG_NOETIG` | mehrdeutige Formel (Kandidaten stehen in der Spalte `kandidaten`) oder ein Wert, der sich nicht eindeutig abbilden lässt |

### Aufbau des QuickStatements-Entwurfs

Der Entwurf enthält **alle drei Status**, aber in getrennten Abschnitten:

| Abschnitt | Inhalt | Form |
|---|---|---|
| 1 — Einspielbar | die `VORSCHLAG`-Zeilen | echte QuickStatements-Syntax |
| 2 — Bereits vorhanden | die `BEREITS_VORHANDEN`-Zeilen | auskommentiert |
| 3 — Manuelle Klärung | die offenen Fälle samt Kandidaten | auskommentiert |

**Außerhalb von Abschnitt 1 beginnt jede Zeile mit `#`.** Die Datei lässt
sich dadurch vollständig nach QuickStatements kopieren, ohne dass aus einer
geprüften oder offenen Zeile versehentlich eine Aussage wird — das ist
getestet ([tests/test_quickstatements.py](../tests/test_quickstatements.py)).

Abschnitt 2 und 3 sind bewusst nicht weggelassen: So ist nachvollziehbar, was
das Skript geprüft und *bewusst nicht* vorgeschlagen hat, statt dass es
kommentarlos verschwindet. Der Kopf der Datei zählt alle drei Abschnitte,
leere werden mit `# (keine)` ausgewiesen — ein fehlender Abschnitt soll nicht
wie ein vergessener aussehen.

### Belege

Jeder Wert trägt eine Referenz, in absteigender Belastbarkeit
(Spalte `ref_mode`):

| Modus | QuickStatements | Herkunft |
|---|---|---|
| `DOI` | `S356` | Referenzpublikation des Materials Project (die mp-ID steht in der Notiz) |
| `ISBN-13` / `ISBN-10` | `S212` / `S957` | Einzelnachweis aus der Wikipedia-Infobox |
| `Wikimedia-Import` | `S143` + `S4656` | Wikipedia-Wert ohne eigenen Nachweis; die Import-URL ist ein **Permalink auf die konkrete Artikelversion** (`oldid`) |
| `URL+Datum` | `S854` + `S813` | Notnagel |

Mengenwerte tragen im Entwurf zwingend ihre Einheit als `<zahl>U<QID-Nummer>`
(z.B. `1357.77U11579` für Kelvin). Fehlt bei einer Mengenaussage die Einheit,
warnt das Skript auf stderr — ohne Einheit stünde in Wikidata eine nackte Zahl.

## Abgedeckte Properties

`PROPERTY_MAP` in [cli.py](cli.py) enthält nur auf wikidata.org verifizierte
Properties:

| Größe | Property | Einheit / Typ |
|---|---|---|
| Dichte | `P2054` | kg/m³ |
| Schmelzpunkt | `P2101` | Kelvin |
| Siedepunkt | `P2102` | Kelvin |
| Kristallsystem | `P556` | Item (7 Werte, 1:1 zum MP-Vokabular) |
| Kompressionsmodul | `P5668` | Pascal |
| Schubmodul | `P5673` | Pascal |
| Wärmeleitfähigkeit | `P2068` | W/(m·K) |
| Elektrische Leitfähigkeit | `P2055` | S/m |
| Spezifischer Widerstand | `P5679` | Ω·m |
| Spezifische Wärmekapazität | `P2056` | J/(kg·K) |
| Schallgeschwindigkeit | `P2075` | m/s |
| Poissonzahl | `P5593` | dimensionslos |
| CAS-Nummer | `P231` | external-id |

Wichtig: **Ein Eintrag in `PROPERTY_MAP` allein erzeugt noch keine
Vorschläge.** Aus dem Materials Project kommen nur Größen, die auch in
`MP_FIELD_MAP` einen Pfad haben — das sind fünf:

| Wikidata | MP-Feld | Umrechnung |
|---|---|---|
| Dichte `P2054` | `density` | g/cm³ → kg/m³ (×1000) |
| Kristallsystem `P556` | `symmetry.crystal_system` | Groß-/Kleinschreibung, dann `value_map` |
| Kompressionsmodul `P5668` | `bulk_modulus.vrh` | GPa → Pa (×10⁹) |
| Schubmodul `P5673` | `shear_modulus.vrh` | GPa → Pa (×10⁹) |
| Poissonzahl `P5593` | `homogeneous_poisson` | keine |

Die **Einheiten sind der Fallstrick**: MP rechnet in g/cm³ und GPa, Wikidata
erwartet kg/m³ und Pascal. Die Faktoren stehen in `MP_FIELD_MAP` und sind
einzeln getestet ([../tests/test_mp.py](../tests/test_mp.py)). Die Moduln
kommen als Voigt-Reuss-Hill-Mittel (`vrh`), das übliche Mittel für
polykristalline Werkstoffe — nicht als `voigt` oder `reuss`.

Alles Übrige stammt aus den Wikipedia-Infoboxen: bei Elementen alle 13
Properties, bei Verbindungen Dichte, Schmelz- und Siedepunkt sowie die
CAS-Nummer.

Feldnamen und Einheiten stammen aus dem öffentlichen OpenAPI-Schema
(<https://api.materialsproject.org/openapi.json>, `SummaryDoc`, 69 Felder,
ausgewertet am 2026-08-15).

Bewusst **nicht** übernommen, obwohl MP es führt:

- **Bandlücke** (`band_gap`, eV) — Wikidata hat dafür keine Property. Die
  beiden passenden Items (Q806352, Q103982939) sind als Prädikat unbrauchbar;
  der saubere Weg wäre ein Property-Proposal. Details im Kommentar zu
  `MP_FIELD_MAP` in [cli.py](cli.py).
- **Dielektrizitätskonstante, Brechungsindex, piezoelektrischer Modul,
  Austrittsarbeit, Magnetisierung** — rechnerische Größen ohne etablierte
  Wikidata-Property bzw. ohne eindeutigen Bezug zum Stoff statt zur
  gerechneten Zelle.
- **Wärme- und elektrische Leitfähigkeit** (`P2068`/`P2055`) stehen in
  `PROPERTY_MAP`, MP führt sie aber nicht — sie können nur aus der
  Wikipedia-Infobox kommen.

Wie klein die Schnittmenge zwischen MP und der Property-Liste des
WikiProject Materials ist, misst [../benchmark/](../benchmark/).

## Multi-Source-Variante

[Werkstoff wikidata vorschläge.py](Werkstoff%20wikidata%20vorschl%C3%A4ge.py)
ist eine eigenständige Erweiterung desselben Prinzips auf weitere freie
Quellen — formelbasiert statt elementbasiert:

```bash
python "materialswiki/Werkstoff wikidata vorschläge.py" \
    --formulas TiO2 Fe2O3 NaCl --sources materials_project pubchem
```

| Quelle | Beleg |
|---|---|
| Materials Project | DOI der Referenzpublikation der Datenbank (Einträge haben keine eigene DOI) |
| PubChem | `P854` + `P813`, da PubChem keine Eintrags-DOIs vergibt |

Ausgabe: `werkstoffe_vorschlaege.csv` und
`werkstoffe_quickstatements_entwurf.txt` (`--out` / `--qs-out`). Für die
Materials-Project-Quelle ist ein eigener `MP_API_KEY` im Skript einzutragen
(kostenloser Account auf
<https://next-gen.materialsproject.org/api>). Die `PROPERTY_MAP` dieses
Skripts ist bewusst auf Dichte, Schmelz- und Siedepunkt beschränkt.

## Vor dem Einsatz anpassen

Alle drei Stellen stehen im Konfigurationsblock oben in [cli.py](cli.py)
(bzw. im Multi-Source-Skript):

- **`USER_AGENT`** — gemäß
  [Wikimedia-User-Agent-Richtlinie](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
  mit echtem Namen/Kontakt füllen.
- **`MP_FIELD_MAP`** — Feldnamen und Einheiten können sich ändern; vor
  Gebrauch gegen das
  [OpenAPI-Schema](https://api.materialsproject.org/openapi.json)
  verifizieren.
- **`PROPERTY_MAP`** — nur Properties eintragen, die auf wikidata.org
  tatsächlich existieren und zum Datentyp passen. Nichts ergänzen, ohne das
  vorher auf wikidata.org geprüft zu haben.

Zwischen allen API-Aufrufen liegt eine Pause von `REQUEST_DELAY_SEC` (1 s), um
die Rate Limits von Materials Project und Wikidata zu respektieren.

Das formelbasierte Matching ist eine Heuristik, kein Identitätsbeweis — jede
Zeile vor dem Übertragen gegenprüfen, besonders bei Polymorphen und Isomeren.
