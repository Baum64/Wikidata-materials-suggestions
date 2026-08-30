# materialswiki — Materials Project → Wikidata

Erzeugt aus dem [Materials Project](https://next-gen.materialsproject.org) —
und, für alles Fehlende, aus den Wikipedia-Infoboxen — Vorschlagslisten für
Wikidata-Statements. Das Skript **legt keine neuen Wikidata-Items an und
schreibt nichts automatisch nach Wikidata** — es liefert Kandidaten als
Markdown-Tabelle zur manuellen Prüfung.

## Aufbau: welche Datei was tut

Der Code liegt in Schichten, die einzeln ladbar sind — wer nur Formeln
zerlegen will, braucht weder Netz noch Wikidata:

| Datei | Inhalt | haengt ab von |
|---|---|---|
| [konfiguration.py](konfiguration.py) | Kennungen, Endpunkte, Schlüssel aus `.env` | — |
| [netz.py](netz.py) | HTTP: Drosselung je Gegenstelle, Retry, **einziger** Einstiegspunkt | konfiguration |
| [properties.py](properties.py) | Property-Tabellen, Einheiten, Plausibilitätsschranken, Feldkarten der Infoboxen | — |
| [formeln.py](formeln.py) | Summenformeln zerlegen und schreiben (beide Parser, funktionale Gruppen) | — |
| [ausgabe.py](ausgabe.py) | Referenzmodell, Vorschlagszeile, Markdown-Tabelle, QuickStatements-Entwurf | properties |
| [wikidata.py](wikidata.py) | Vokabular (Elemente, Raumgruppen) und Itemzustand (Aussagen, CAS, Siedepunkt) | netz, properties, formeln |
| [gruppen.py](gruppen.py) | Werkstoffgruppen, Prüfliste, Legierungsprüfung | netz, wikidata |
| [infobox.py](infobox.py) | die drei Wikipedia-Infoboxen samt Parsern | netz, wikidata, ausgabe |
| [quellen/mp.py](quellen/mp.py) | Materials Project | netz, wikidata, ausgabe |
| [quellen/cod.py](quellen/cod.py) | Crystallography Open Database | netz, wikidata, ausgabe |
| [quellen/nist.py](quellen/nist.py) | NIST Chemistry WebBook | netz, wikidata, ausgabe |
| [ableitungen.py](ableitungen.py) | was ohne externe Quelle aus dem Item folgt (P527, P2670, P589, Umstellung) | wikidata, ausgabe, gruppen |
| [cli.py](cli.py) | die Kaskade, der Chargenbetrieb, die Kommandozeile | alle |

**Eine Regel macht die Tests verlässlich:** Module rufen einander über das
*Modul* auf (`netz.get_with_retry`, `wikidata.item_has_statement`), nicht über
eine eigene Namensbindung. Dadurch greift ein einziger `monkeypatch` überall —
die Netzsperre in [../conftest.py](../conftest.py) ist deshalb eine Zeile und
lässt keinen Weg offen.

## Warum das Materials Project

Entscheidend ist nicht die Menge der Werte, sondern ob sich einer Zeile
ansehen lässt, wie belastbar sie ist. Eine reine Sammlung **einzelner
Rechnungen** kann das nicht: dort steht nirgends, ob das gerechnete Material
real existiert oder überhaupt stabil ist.

Das Materials Project pflegt dagegen kuratierte Materialdokumente und macht
genau diese Einordnung **als Query-Parameter** abfragbar:

| Filter | Bedeutung | Default |
|---|---|---|
| `theoretical=false` | experimentell nachgewiesen, in aller Regel ICSD-hinterlegt | an (`--no-experimentell` schaltet ab) |
| `is_stable=true` | auf der konvexen Hülle, thermodynamisch stabil | an (`--no-stabil` schaltet ab) |
| `deprecated=false` | keine zurückgezogenen Dokumente | immer an |

Damit fallen hypothetische Strukturen, instabile Phasen und Rechenartefakte
von vornherein weg. `--no-experimentell` lässt auch rein gerechnete
Strukturen zu — die Ausbeute steigt dann, die Verlässlichkeit sinkt.

Dazu kommt: Ein MP-Materialdokument enthält Formel, Symmetrie und alle
Kennwerte **auf einmal**, es genügt also eine Anfrage je Material statt einer
Trefferliste plus Einzelabrufen.

## API-Schlüssel (Pflicht)

Die Materials-Project-API verlangt einen Schlüssel; ohne ihn antwortet jeder
Endpunkt mit HTTP 401, mit einem falschen Schlüssel mit HTTP 403. Beides fängt
das Skript mit einer verständlichen Meldung ab (Exit-Code 2) statt mit einem
Traceback.

Kostenlos anlegen unter <https://next-gen.materialsproject.org/api>, dann in
die gitignorierte `.env` im Repo-Wurzelverzeichnis eintragen:

```bash
cp ../.env.beispiel ../.env && chmod 600 ../.env
# darin: MP_API_KEY=...
```

Details siehe [../README.md](../README.md#zugangsdaten-env). Für einen
einzelnen Lauf lässt sich der Schlüssel auch über die Umgebung setzen, sie hat
Vorrang vor der Datei:

```bash
MP_API_KEY=zweitschluessel python -m materialswiki --periodic-table
```

Bewusst **nicht** im Quelltext: ein Schlüssel im Repo wäre ein Leck, sobald
das Repo geteilt wird.

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

### Physikalisch Unmögliches wird abgefangen

Die API-Filter sagen etwas über das **Material** aus, nichts über die einzelne
Rechnung. Am Bestand gefunden (2026-08-15) — Zink, `mp-aaaaaadb`, laut MP
experimentell nachgewiesen **und** stabil:

```
shear_modulus: {voigt: 44.248, reuss: -5606.668, vrh: -2781.21}
homogeneous_poisson: -1.153
```

Die Reuss-Schranke ist havariert und reißt das VRH-Mittel mit. Ein negativer
Schubmodul bedeutet mechanische Instabilität — Zink ist aber schlicht stabil,
der Wert ist Rechenmüll. Ohne Prüfung stünde an Wikidatas Zink-Item ein
Schubmodul von **−2781 GPa** (Literaturwert: 43 GPa).

Geprüft wird deshalb gegen physikalische Schranken, in Wikidata-Einheiten:

| Größe | Schranke | Begründung |
|---|---|---|
| Kompressions-/Schubmodul | 0,001 … 1000 GPa | müssen positiv sein; Diamant liegt bei 443 bzw. 535 GPa |
| Poissonzahl | −1 … 0,5 | thermodynamische Grenze für isotrope lineare Elastizität |
| Dichte | 0,01 … 30 g/cm³ | Lithium 0,534, Osmium 22,59 |
| Mohshärte | 1 … 10 | die Skala selbst; `P1088` trägt genau diesen Bereichs-Constraint |

Unplausible Werte werden **nicht still verworfen**, sondern als
`MANUELLE_KLAERUNG_NOETIG` ausgewiesen — sonst fiele nie auf, dass die
Datenbank an dieser Stelle kaputt ist:

```
# Q758 Zink: unplausibler Wert -2.78121e+12, erwartet 1e+06..1e+12
#            - Rechnung in mp-aaaaaadb vermutlich fehlgeschlagen
```

Die gesunden Größen desselben Materials bleiben davon unberührt: Dichte,
Kristallsystem und Kompressionsmodul von Zink gehen normal durch.

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

In der Vorschlagstabelle steht dasselbe lesbar in der Spalte `bestimmungsmethode`.

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

### Kristallsystem: fcc und bcc statt bloß „kubisch"

Der `one-of`-Constraint von `P556` lässt inzwischen elf Werte zu — die sieben
Kristallsysteme plus:

| QID | Wert | genutzt |
|---|---|---|
| `Q3006714` | face-centered cubic (fcc) | ja |
| `Q851536` | body-centered cubic (bcc) | ja |
| `Q103382` | amorphes Material | nein — keine Quelle liefert es |
| `Q263214` | Quasikristall | nein — dito |

fcc und bcc sind streng genommen Bravais-Gitter und keine Kristallsysteme;
Wikidata lässt sie auf `P556` dennoch zu, und sie sind die aussagekräftigeren
Werte: „kubisch" allein unterschlägt den Unterschied zwischen Kupfer und
Wolfram. Wo die Quelle die Zentrierung hergibt, wird deshalb der spezifischere
Wert genommen.

**Woher die Zentrierung kommt:** MPs Feld `crystal_system` sagt nur `Cubic`.
Der **erste Buchstabe des Hermann-Mauguin-Symbols** (`symmetry.symbol`) nennt
sie aber genau:

```
P  primitiv          →  bleibt „kubisch"
F  flächenzentriert  →  fcc      Cu, Al  (Fm-3m)
I  raumzentriert     →  bcc      Fe, W   (Im-3m)
```

Angewandt nur auf kubische Systeme — ein `I4/mmm` ist tetragonal und bleibt
es. Fehlt das Symbol oder ist der Anfangsbuchstabe unbekannt, wird nichts
behauptet.

Die Wikipedia-Infoboxen schreiben es ohnehin aus (`kubisch flächenzentriert`,
`body-centered cubic`) — das wurde bisher zu bloßem „kubisch" eingedampft.
Aluminium schreibt es hinter einem Wikilink (`[[Kubisches
Kristallsystem|kubisch]] flächenzentriert`); die Verweise werden deshalb
aufgelöst, bevor nach Stichworten gesucht wird, sonst zerreißt die Klammer die
gesuchte Phrase.

Ergebnis eines Laufs:

```
Aluminium  Q3006714  kubisch flaechenzentriert
Kupfer     Q3006714  kubisch flaechenzentriert
Eisen      Q851536   kubisch raumzentriert
Wolfram    Q851536   kubisch raumzentriert
Titan      Q663314   hexagonales Kristallsystem
```

**Grenze:** Trägt ein Item bereits ein grobes `P556` = „kubisch", gilt die
Aussage als vorhanden (`BEREITS_VORHANDEN`) und die Verfeinerung auf fcc/bcc
wird nicht vorgeschlagen. Das Werkzeug ergänzt Fehlendes, es überschreibt
nichts.

### Das Kristallsystem wird mit Literatur belegt, nicht mit der Rechnung

Für eine Größe ist die DFT-Rechnung der **schlechtere** Beleg, obwohl der Wert
unstrittig ist: Dass Kupfer kubisch und Titan hexagonal kristallisiert, ist
seit Jahrzehnten etablierte Kristallographie. Eine Symmetrieanalyse einer
DFT-Zelle dafür zu zitieren, belegt die Rechnung — nicht den Stoff.

`P556` trägt deshalb einen Literaturbeleg:

```
Greenwood/Earnshaw, Chemistry of the Elements, 2. Aufl. 1997
ISBN 0-08-037941-9   → QuickStatements S957 (ISBN-10)
```

Prüfsumme validiert und über OpenLibrary als dieses Werk bestätigt
(2026-08-15). In der Zeile sieht das so aus — **ohne** `P459`, denn ein
Literaturwert mit dem Vermerk „berechnet" wäre schlicht falsch:

```
Q753	P556	Q473227	S957	"0-08-037941-9"
Q753	P5668	151394000000.0U44395	P459	Q1048589	S356	"10.1063/1.4812323"
```

**Der Wert stammt weiterhin aus der MP-Symmetrieanalyse** — das steht in der
Notiz, und genau deshalb ist die Zeile zu prüfen:

```
Greenwood/Earnshaw, Chemistry of the Elements, 2. Aufl. 1997;
Wert aus der Symmetrieanalyse von Materials Project mp-aaaaaabe -
Modifikation gegen das Werk pruefen
```

Das ist kein Formalismus: Elemente und Verbindungen haben je nach Modifikation
verschiedene Kristallsysteme (Graphit/Diamant, α-/β-Titan). Welche Modifikation
MP gerechnet hat, entscheidet die Zeile nicht — das Buch schon.

Weitere Größen lassen sich genauso umstellen; die Zuordnung steht in
`LITERATUR_BELEG` in [cli.py](cli.py).

**Wikipedia-Werte bekommen bewusst keinen Qualifikator.** Das sind
Literaturwerte, und mit welcher Methode sie bestimmt wurden, steht in der
Infobox nicht — eine Methode zu behaupten wäre geraten.

### Die Dichte steht in g/cm³

`P2054` lässt laut Constraint vier Einheiten zu (`Q844211` kg/m³,
`Q13147228` g/cm³, dazu g/l und g/m³). Genommen wird **g/cm³**, aus zwei
Gründen:

- **Der Bestand ist eindeutig.** Von 2476 Dichteangaben in Wikidata stehen
  2015 in g/cm³ und nur 461 in kg/m³ (gemessen 2026-08-19). Wer die Werte
  eines Items vergleicht, soll nicht zwischen zwei Einheiten umrechnen müssen.
- **Alle hiesigen Quellen liefern g/cm³** — das Materials Project ebenso wie
  beide Wikipedia-Infoboxen. Die Umrechnung entfällt damit ersatzlos, und mit
  ihr der Faktor 1000, der bisher an vier Stellen im Code stand und an jeder
  einzeln danebengehen konnte.

Die Plausibilitätsschranken laufen entsprechend in g/cm³ (0,01 … 30, siehe
oben).

### Die Dichte trägt ihre Messbedingungen

Die Nutzungsanweisung von `P2054` verlangt zwei Qualifikatoren, und beide sind
nötig: Stoffe dehnen sich aus, und 13,5 g/cm³ für Quecksilber meint die
*Flüssigkeit*.

| Qualifikator | Woher |
|---|---|
| `P2076` Temperatur | aus der Infobox, falls angegeben; sonst 20 °C |
| `P515` Aggregatzustand | aus Schmelz- und Siedepunkt desselben Artikels abgeleitet |

**20 °C blind anzunehmen wäre falsch gewesen.** Die Elementinfoboxen sind
uneinheitlich — am Bestand geprüft (2026-08-15):

```
Kupfer, Silber, Aluminium, Blei   (20 °C)
Titan, Zink                       (25 °C)
Eisen, Quecksilber                keine Angabe  → Vorgabe 20 °C
```

**„Fest" wäre ebenso falsch gewesen.** Der Zustand wird deshalb aus dem
Schmelzpunkt abgeleitet; fehlt er, wird gar nichts behauptet — lieber kein
Qualifikator als ein falscher:

```
Titan    4,50 g/cm³   P2076=25 °C   P515=Q11438 (fest)
Eisen    7,874 g/cm³  P2076=20 °C   P515=Q11438 (fest)
Brom     3,12 g/cm³   P2076=20 °C   P515=Q11435 (flüssig)
Quecks. 13,546 g/cm³  P2076=20 °C   P515=Q11435 (flüssig)
```

#### MP-Dichten stehen bei 0 K, nicht bei 20 °C

Für Materials-Project-Werte greift die 20-°C-Vorgabe **nicht**: Eine
DFT-Rechnung liefert das Volumen des relaxierten Grundzustands, also 0 K. Das
ist „anders angegeben" im Wortsinn, und es ist zugleich die Erklärung für die
systematische Abweichung von den Handbuchwerten — bei Raumtemperatur ist die
Zelle thermisch geweitet.

```
Q716	P2054	4.67017U13147228	P459	Q1048589	P2076	0U11579	P515	Q11438	S356	"10.1063/1.4812323"
```

Ein angenehmer Nebeneffekt: Kupfer bekommt aus MP 9,219 g/cm³, die Literatur
nennt 8,96. Mit den Qualifikatoren widersprechen sich beide Werte am Item
nicht mehr — der eine gilt bei 0 K, der andere bei 20 °C.

#### Auch die Poissonzahl steht bei 0 K

Dieselbe Überlegung greift bei `P5593`. Die Poissonzahl ist
temperaturabhängig, und der Elastizitätsdatensatz (de Jong et al. 2015) ist
wie alles bei MP bei 0 K gerechnet. Ohne Qualifikator stünde in Wikidata eine
temperaturlose Zahl, die stillschweigend als Raumtemperaturwert gelesen würde
— und gerade hier weicht die Rechnung am stärksten ab (−16,6 % bis +21,7 %,
siehe oben). Sie bekommt deshalb `P2076 = 0 K`, aber **keinen**
Aggregatzustand: den verlangt nur `P2054`, an einer Materialkonstante wäre er
bloßes Beiwerk.

```
Q320603	P5593	0.28	P459	Q1048589	P2076	0U11579	S356	"10.1063/1.4812323"	S356	"10.1038/sdata.2015.9"
```

Geprüft am 2026-08-19: `P5593` trägt **keinen** Qualifikator-Constraint,
`P2076` ist dort also zulässig; 4 der 226 bestehenden Aussagen führen ihn
bereits (3 weitere den Druck `P2077`).

**Aus den Infoboxen kommt keine Temperatur.** Weder die deutsche
Elementinfobox (`| Poissonzahl = 0,34<ref …>`) noch die englische Vorlage
(`| Poisson ratio = 0.34`) nennt eine — geprüft an Titan, Kupfer, Eisen,
Aluminium und Wolfram (2026-08-19). Dort wird deshalb nichts behauptet;
20 °C zu unterstellen wäre geraten. Kompressionsmodul und Schubmodul bleiben
vorerst ebenfalls ohne Temperatur — sie stammen aus demselben 0-K-Datensatz,
die Erweiterung wäre einzeilig.

Verifiziert am 2026-08-15: `P2076` ist mengenwertig, `P515` itemwertig, beide
laut Property-Scope-Constraint als Qualifikator zugelassen (`P515` sogar
ausschließlich). Die drei Zustands-QIDs (`Q11438` fest, `Q11435` flüssig,
`Q11432` Gas) sind die tatsächlich als `P515`-Qualifikator verwendeten, per
SPARQL nach Häufigkeit ermittelt.

### Identifikatoren bekommen gar keinen Beleg

Die CAS-Nummer belegt sich selbst: `7440-50-8` **ist** der Verweis auf den
Eintrag im CAS-Register — man schlägt sie dort nach und hat damit die Prüfung.
Ein zusätzliches „importiert aus Wikipedia" sagt darüber nichts aus; es belegt
nur, wo die Zeichenkette abgeschrieben wurde, nicht dass sie stimmt.

`P231` geht deshalb **ohne** `S`-Angabe in den Entwurf:

```
Q753	P231	"7440-50-8"
```

Entschieden über den Datentyp statt über einzelne P-Nummern: was Wikidata als
`external-id` führt, ist per Definition ein Identifikator. Zurzeit betrifft
das nur die CAS-Nummer.

Die **Herkunft** bleibt in der Tabellenspalte `ref_note` und im Kommentar des
Entwurfs stehen (`ohne Beleg, Identifikator - Infobox-Feld 'CAS'`), damit die
Zeile beim Durchsehen prüfbar ist. Die Belegspalten der Tabelle bleiben leer — ein
gefülltes `ref_url` würde suggerieren, dass ein Beleg mitgeschrieben wird.

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
5. Alle offenen Kandidaten als Vorschlagsliste (Markdown-Tabelle) schreiben, plus einen
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

## Periodensystem-Modus: 118, nicht 174

Die Abfrage nach `P31=Q11344` („chemisches Element") mit Symbol `P246` liefert
**174** Wikidata-Items. Davon sind 56 gar keine Elemente, sondern
systematische IUPAC-Platzhalter für **unentdeckte** Elemente — `Ubb`
(Unbibium, Z=122), `Uue` (Ununennium, Z=119) und so fort. Wikidata führt sie
völlig korrekt so; es gibt sie nur nicht.

Das Materials Project beantwortet eine Abfrage danach mit HTTP 400
(`Please provide a comma-seperated list of elements`). Aussortiert werden sie
an der Symbollänge: echte Elementsymbole haben ein oder zwei Zeichen, die
Platzhalter immer drei. Am Bestand geprüft trennt das exakt — 118 echte
Elemente, genau die Zahl der bekannten.

**Ein einzelnes Element reißt den Lauf nicht mehr ab.** Über 118 Elemente mal
drei Quellen dauert ein Durchlauf Stunden; fällt eines aus (API-Fehler,
Netzaussetzer), wird es gemeldet, übersprungen und am Ende gesammelt
ausgewiesen — mit dem fertigen Befehl zum Nachholen:

```
3 Element(e) uebersprungen: Am, Cm, Np
Gezielt nachholen mit: --periodic-table --elements Am Cm Np
```

Ein fehlender API-Schlüssel bricht dagegen weiterhin sofort ab — der träfe
jedes Element, da wäre Weitermachen sinnlos.

## Quellenkaskade

In **beiden Modi dieselbe**; jede Stufe liefert nur, was die vorherige nicht
schon belegt hat:

```
Formel (ohne Netzzugriff)     →  COD (DOI der Originalarbeit)
                              →  Materials Project (DOI)
                              →  NIST WebBook (ISBN der Originalarbeit)
                              →  de.wikipedia (Import)  →  en.wikipedia (Import)
```

Die Stufe **Formel** steht vorn, weil sie ohne eine einzige Netzanfrage
auskommt und eine Property liefert, die keine der externen Quellen führt —
siehe [„enthält Elemente von" (P2670)](#enthält-elemente-von-p2670-aus-der-summenformel). Wo gar
eine weitere Aussage entsteht ebenso aus dem Item selbst: die
**Punktgruppe** (`P589`) aus der Raumgruppe, die am Item schon steht, siehe
[Punktgruppe (P589) aus der Raumgruppe](#punktgruppe-p589-aus-der-raumgruppe).

Die **[Crystallography Open Database](https://www.crystallography.net/cod/)**
steht vorn und ist die primäre Quelle für Raumgruppe (P690), Kristallsystem
(P556) und COD-ID (P9824). Drei Gründe:

| | COD | Materials Project |
|---|---|---|
| Lizenz | **CC0** — kein Konflikt mit Wikidatas CC0 | CC BY 4.0 |
| Beleg | DOI der **Originalarbeit** je Struktur | Sammel-DOI der Datenbank |
| Herkunft des Werts | **gemessen** (`method`, `celltemp`) | DFT-Rechnung bei 0 K |

Das Materials Project liefert diese drei Größen nur noch, wo COD nichts hat.
Abschaltbar mit `--no-cod`.

**Was COD *nicht* beisteuert:** Die Gitterparameter (a, b, c und die Winkel)
kommen zwar mit, aber Wikidata hat dafür keine Property — am 2026-08-16
gesucht, es gibt weder „lattice constant" noch „unit cell". Der eigentliche
Strukturinhalt lässt sich also nicht eintragen.

**Welche Modifikation?** Ein Stoff hat mehrere Kristallstrukturen, COD führt
sie alle. Entschieden wird nach **Häufigkeit über alle Treffer**, nicht nach
Jahrgang — der jüngste Eintrag ist oft eine Hochdruck- oder Dünnschichtphase.
Real gemessen (2026-08-16):

| Stoff | Treffer | Ergebnis |
|---|---|---|
| Fe₂O₃ | 13× Rg. 167, 2× Rg. 15 | Hämatit, trigonal ✔ (nach Jahrgang wäre es monoklin geworden) |
| Cu | 22× Rg. 225 | kubisch flächenzentriert ✔ |
| Ti | 5× Rg. 194, 2× Rg. 229 | α-Titan, hexagonal ✔ |
| TiO₂ | 12× Rg. 136, 11× Rg. 141 | **zur Klärung markiert** — Rutil und Anatas sind beide gängig |

Ist die häufigste Raumgruppe nicht mindestens doppelt so häufig wie die
zweithäufigste, wird nichts vorgeschlagen, sondern
`MANUELLE_KLAERUNG_NOETIG` gesetzt. Die COD-ID stammt immer aus der
gewählten Modifikation, zeigt also nicht auf eine andere Struktur als die
vorgeschlagene Raumgruppe.

Zwei weitere Eigenheiten der COD-Abfrage, beide im Code behandelt:

- Die Formelsuche verlangt **strikte Hill-Notation** (alphabetisch sortiert,
  Elemente durch Leerzeichen getrennt). `Ti O2` liefert null Treffer, `O2 Ti`
  deren 39.
- Ein COD-Eintrag beschreibt eine Struktur *innerhalb* einer Publikation. Der
  Publikationstitel sagt daher nichts über den Stoff — der beste Kupfertreffer
  steht in einer Arbeit über Ammoniak-Monohydrat.

### „enthält Elemente von" (P2670) aus der Summenformel

Woraus ein Stoff besteht, steht bereits in seiner Summenformel — es braucht
dafür keine externe Quelle. Deshalb lohnt die Stufe: die Angabe ist bei
Mineralarten nahezu leer (249 von 6301, gemessen 2026-08-17), während 5694
eine Formel tragen.

Die Stufe liefert **zwei** Arten von Aussagen: `P527` je funktionaler Gruppe
(Sulfat, Kristallwasser, Hydroxid …) und `P2670` je Element, das danach noch
übrig ist. Zuerst die Gruppen, siehe gleich unten; die Elemente rechnen dann
nur noch mit dem Rest der Formel.

#### Zuerst die größtmögliche funktionale Gruppe (P527)

Ein Mineral ist kein Haufen Atome. In Gips (`CaSO₄·2H₂O`) sitzt kein loser
Schwefel und kein loser Sauerstoff, sondern **ein Sulfation und zwei Moleküle
Kristallwasser**. Deshalb läuft vor der Elementzerlegung eine Stufe, die die
Formel in die größtmöglichen Baugruppen zerlegt:

| Formel | Aussagen |
|---|---|
| `CaSO₄·2H₂O` | `P527 → Sulfation` (×1), `P527 → Wasser` (×2), `P2670 → Calcium` (×1) |
| `Mg(OH)₂` | `P527 → Hydroxidion` (×2), `P2670 → Magnesium` (×1) |
| `Ca₅(PO₄)₃(OH)` | `P527 → Phosphation` (×3), `P527 → Hydroxidion` (×1), `P2670 → Calcium` (×5) |

Die Elementstufe rechnet nur noch mit dem **Rest**: was in einer Gruppe
gebunden ist, wird nicht noch einmal einzeln behauptet. Anzahl jeweils als
`P1114`, wie bei den Elementen.

**Warum hier P527 richtig ist.** Das Argument gegen `P527` (unten) trifft die
*Elemente*: ein Elementitem ist eine Klasse. Ein Sulfation ist keine Klasse,
sondern ein Stück Materie im Kristall — „Gips besteht aus einem Sulfation"
ist genau die Aussage, die `P527` meint. Deshalb erzeugt diese Stufe `P527`
und die Elementstufe `P2670`.

**Warum das Ion und nicht die Verbindungsklasse.** Für Brucit wird
`Hydroxidion` (`Q199877`) vorgeschlagen, nicht `hydroxy compound`
(`Q71421787`). Letzteres ist die Klasse der Verbindungen, die eine
Hydroxygruppe *enthalten* — also das Mineral selbst und nicht sein
Bestandteil. Alle 23 Gruppen-QIDs sind gegen die Formel am Item (`P274`)
geprüft; genau daran ist `silicate(2−)` (`Q32854872`) aufgefallen und
draußen geblieben — es trägt `SO₃²⁻` statt `SiO₃²⁻`. Ohne verlässliches Item
keine Aussage, `SiO₃` wird deshalb nicht erkannt.

**Bewusst konservativ.** Erkannt wird nur, was die Formel als Einheit
*hergibt*: eine geklammerte Gruppe oder eine zusammenhängende Tokenfolge,
deren Symbole und Anzahlen **exakt** auf eine bekannte Gruppe passen.
`Al₂SiO₅` (Kyanit) liefert daher nichts — `SiO₅` ist keine Gruppe, und `SiO₄`
herauszulesen hieße raten. Ebenso bleibt eine Kommagruppe eine Mischreihe und
keine Baugruppe: aus `(OH,F)₁₈` wird nichts. Und wo die Formel *nur* aus einer
Gruppe besteht, entsteht keine Zeile — „Wasser besteht aus einem Wasser" sagt
nichts.

Uranyl zählt **nur geklammert**: `(UO₂)` in Carnotit ist eine Ansage, das
nackte `UO₂` von Uraninit dagegen ein Oxid des vierwertigen Urans und gerade
kein Uranylion.

Abdeckung an den 5705 Mineralformeln im Bestand (gemessen 2026-08-24):

| | Anteil |
|---|---|
| Formeln mit mindestens einer Gruppe | 3502 = **61,4 %** |

Macht rund **6170 P527-Aussagen, davon 6091 mit Anzahl** (ohne Anzahl bleibt,
was hinter einem `·nH₂O` steht). Häufigste Gruppen: `H₂O` 1835, `OH` 1614,
`PO₄` 583, `SO₄` 517, `AsO₄` 351, `CO₃` 326, `SiO₄` 246, `UO₂` 210,
`Si₂O₇` 196.

**Bekannte Grenze: Silicate.** Das Formelbild trennt Neso- von
Gerüstsilicaten nicht. `Mg₂SiO₄` (Forsterit) enthält tatsächlich isolierte
Orthosilicat-Tetraeder, `KAlSiO₄` (Kalsilit) dagegen ein Gerüst
eckenverknüpfter Tetraeder — beide sehen in der Summenformel gleich aus.
Betroffen sind die 35 Fälle, in denen `SiO₄` **ungeklammert** steht; die
geklammerten schreibt die Quelle selbst als Baugruppe. Beim Durchsehen der
Vorschläge darauf achten.

**Warum P2670 und nicht P527.** Das Item eines chemischen Elements ist die
**Klasse seiner Atome**, kein einzelnes Stück Materie. „Wasser *besteht aus*
Wasserstoff" (`P527`) ist deshalb mereologisch falsch — ein Teil-Ganzes-Bezug
zwischen einem Stoff und einer Klasse. `P2670` „hat Teil(e) der Klasse" sagt
genau das Gemeinte: *„the subject has one or more parts of the object class"*.

Erzeugt wird **Element plus stöchiometrischer Anzahl** (`P1114`) als
Qualifikator. Vorbild im Bestand sind Kohlenstoffdioxid (`Q1997`) und
Kohlenstoffmonoxid (`Q2025`), die genau diese Form tragen.

**Der Bestand ist mehrheitlich anders modelliert** — das sollte man wissen,
bevor man einspielt (gemessen 2026-08-21):

| | Aussagen | Items |
|---|---|---|
| `P527 → chemisches Element` | 24 538 | 10 095 |
| `P2670 → chemisches Element` | 28 | 14 |

Wasser (`Q283`) selbst steht bis heute auf `P527`. Die Mehrheit ist also
nicht auf unserer Seite, die Definition der beiden Properties schon — und
`P2670` mit `P1114` ist mit 36 201 Aussagen insgesamt gut eingeführt, nur
eben meist mit anderen Wertklassen. Wer das anders sieht, ändert eine Zeile
in `PROPERTY_MAP`.

**Ein Constraint bleibt offen:** `P2670` verlangt am *Wert* eine
`P279`-Aussage. 77 der 118 Elemente haben eine, 41 nicht (Rhenium, Uran,
Barium …). Das ist eine weiche Beanstandung am Elementitem, nicht an unserer
Aussage — behoben wird sie dort, nicht hier.

**Warum ein zweiter Parser neben `parse_formula`.** `parse_formula` ist für
den Item-*Abgleich* gebaut und deshalb bewusst streng: es braucht die exakte
Stöchiometrie, um `TiO₂` gegen Wikidata zu suchen, und lehnt alles ab, was
daran zweifeln lässt. An echten Mineralformeln scheitert es dadurch in
**61,8 %** der Fälle (3524 von 5700, gemessen 2026-08-17) — an Hydratpunkten,
Ladungen, eckigen Klammern, Leerstellen. Für P2670 ist die Anforderung aber
schwächer: gebraucht wird, *welche* Elemente vorkommen, nicht in welchem
Verhältnis. `Co₃(AsO₄)₂·8H₂O` ist stöchiometrisch unbequem, aber dass Cobalt,
Arsen, Sauerstoff und Wasserstoff darin stecken, ist eindeutig. Der Abgleich
darf seine Strenge nicht verlieren, also steht daneben ein toleranterer
Parser.

**Die eigentliche Falle sind Mischreihen.** Mineralformeln schreiben
Mischkristallreihen als Klammer mit Komma: `(Fe,Mg)₂SiO₄` heißt Fe *oder* Mg
auf derselben Gitterposition, je nach Glied der Reihe. Wer daraus „besteht
aus Eisen" **und** „besteht aus Magnesium" macht, behauptet für jedes
Endglied etwas Falsches. 850 der 5700 Formeln enthalten ein solches Komma —
ein Fehler wäre also nicht die Ausnahme. Unterschieden wird dreifach:

| Fall | Ergebnis |
|---|---|
| Element sicher, Menge sicher | `P2670` **mit** `P1114` |
| Element sicher, Menge offen | `P2670` **ohne** `P1114` |
| Element nur eine Möglichkeit | nichts, nur `MANUELLE_KLAERUNG_NOETIG` |

Ein Element gilt als sicher, wenn es mindestens einmal **außerhalb** jeder
Kommagruppe steht — oder wenn es in **jedem** Zweig einer Kommagruppe
vorkommt. Der zweite Fall ist nicht theoretisch: `(V⁵⁺,V⁴⁺)₄` nennt zweimal
Vanadium in verschiedenen Oxidationsstufen, Vanadium steht also fest.
Umgekehrt ist in `Al₁₃Si₅O₂₀(OH,F)₁₈Cl` der Sauerstoff durch `O₂₀` gesichert,
nur seine Gesamtmenge nicht.

Abdeckung an 5705 echten Formeln, gemessen **am Rest nach Abzug der
Gruppen** (2026-08-24; in Klammern derselbe Lauf ohne die Gruppenstufe,
2026-08-17):

| | Anteil |
|---|---|
| voll bestimmt | 76,8 % (76,7 %) |
| voll bestimmt neben einer Mischreihe | 10,1 % (9,3 %) |
| Element sicher, Menge teils offen | 6,4 % (8,5 %) |
| nicht deutbar | 5,2 % (5,2 %) |
| kein sicheres Element | 1,2 % (0,3 %) |
| ganz in Gruppen aufgegangen | 0,3 % (—) |

Macht rund **16 470 P2670-Aussagen, davon 15 910 mit Anzahl** — vor der
Gruppenstufe waren es 22 990. Die Differenz ist nicht verloren, sie steckt in
den 6170 `P527`-Aussagen und ist dort besser aufgehoben. Dass „Menge teils
offen" zurückgeht, hat denselben Grund: das offene `n` hängt fast immer am
Kristallwasser, und das ist jetzt eine Gruppe. Nicht deutbar bleiben
Variablen im Index (`Cu₂₋ₓAlₓ…`) und Bereichsangaben (`·(10-12)H₂O`) — dort
wird bewusst nichts behauptet.

**Beleg.** Die Stufe holt nichts von außen, sie leitet aus P274 am Item selbst
ab. Ein „importiert aus Wikidata" wäre zirkulär, und ein passendes
Heuristik-Item für P887 existiert nicht. Die Aussagen gehen deshalb **ohne
S-Beleg** raus — dieselbe Überlegung wie bei den Identifikatoren (siehe
[Identifikatoren bekommen gar keinen Beleg](#identifikatoren-bekommen-gar-keinen-beleg)).
Die Herkunft samt Formel bleibt in der Tabellenspalte `ref_note` nachprüfbar.
Trägt ein Item bereits `P2670`, wird **nichts ergänzt** — wer die
Zusammensetzung von Hand gepflegt hat, weiß mehr als diese Ableitung. Ein
bestehendes `P527` blockiert dagegen nicht mehr: zeigt es auf Elemente,
stellt die Umstellung es um (siehe unten); zeigt es auf *Verbindungen*
(Quarz → Siliciumdioxid), ist es eine andere Aussage und bleibt unberührt.

#### Umstellung bestehender P527-Aussagen

Was schon als `P527 → Element` am Item steht, wird nicht daneben noch einmal
behauptet, sondern **umgehängt**. Je Aussage entstehen zwei Zeilen, die
zusammengehören:

```
Q283	P2670	Q556	P1114	2
-Q283	P527	Q556
```

Das führende `-` ist QuickStatements-Syntax für *entfernen*. Es ist die
**einzige Stelle im ganzen Werkzeug, die etwas wegnimmt** — der Kopf von
Abschnitt 1 im Entwurf weist eigens darauf hin und zählt diese Zeilen. Wer
nur eine der beiden einspielt, hinterlässt eine Dublette oder eine Lücke.

**Was nicht umgestellt wird.** QuickStatements kann Belege und Qualifikatoren
einer bestehenden Aussage nicht mitnehmen; eine Umstellung würde sie
verlieren. Solche Aussagen gehen deshalb zur Klärung statt zur Umstellung
(gemessen 2026-08-21, über alle 24 538 Elementaussagen):

| | Aussagen |
|---|---|
| mit Beleg | 318 |
| mit `P1114` (wird mit umgehängt) | 515 |
| mit anderen Qualifikatoren (`P1107` Anteil, `P1121` Oxidationszahl …) | 302 |

Die Zahl 302 stand zwischenzeitlich bei 1101 — der Wertknoten jeder
Mengenangabe hängt zusätzlich unter `.../qualifier/value/P1114` und zählte
als fremder Qualifikator. An genau dieser Stelle scheiterte zuerst die
Umstellung von Wasser, dessen einziger Qualifikator `P1114` ist.

**Umgestellt wird nur an Stoffen** — erkennbar an einer Summenformel oder an
der Einordnung als Legierung. Der Grund steht im Bestand: `Q19557`
„Alkalimetalle" führt mit `P527` seine **Mitglieder** auf (Caesium, Lithium
…). Dort ist `P527` die richtige Aussage, „Alkalimetalle enthält Teile der
Klasse Caesium" wäre es nicht. Solche Sammelbegriffe hängen wegen des
bekannten Modellierungsfehlers mitten in der Legierungsgruppe und wären sonst
mit umgestellt worden.

Trägt ein Item beide Aussagen bereits (ein Fall im Bestand), bleibt nur die
Löschzeile übrig.

Abschaltbar mit `--no-formel` — die Umstellung hängt an derselben Stufe.

### Verschoben: chemische Metaklasse (P31) für Legierungen

Diese Stufe gibt es hier nicht mehr (seit 2026-08-23). Sie schlug Legierungen
die Metaklasse `Q119892838` („definiertes Gemisch chemischer Substanzen") vor,
und sie folgte nicht aus einer Quelle, sondern aus der
**Klassenzugehörigkeit** des Items — dafür ist dieses Werkzeug der falsche
Ort: es musste den Klassengraphen eigens abfragen, während das
Struktur-Werkzeug ihn ohnehin im Speicher hält.

Sie steht jetzt als Prüfung `metaklasse` in
[Material class structure](../Material%20class%20structure/README.md#chemische-metaklasse-p31-für-legierungen),
mit denselben Regeln (Mineralarten außen vor, die schiefe Kante
Metall → Legierung ausgespart, eine vorhandene *andere* Chemie-Metaklasse
wird gemeldet statt ersetzt) und demselben Schalter
`--metaklasse-auch-mit-p31`.

Was hier bleibt: die **Klassenlage** (`metaklassen()` in `ableitungen.py`).
Die Umstellung `P527 → P2670` braucht sie, weil ein Item ohne Summenformel
nur dann als Stoff gilt, wenn es eine Legierung ist.

### Punktgruppe (P589) aus der Raumgruppe

Dieselbe Bauart, dritter Fall: der Wert steht schon am Item, nur in einer
anderen Property. Jede der 230 Raumgruppen gehört zu genau **einer** der 32
kristallographischen Punktgruppen, und Wikidata führt diese Zuordnung bereits
an den Raumgruppen-Items selbst — **230 der 236** tragen `P589` (gemessen
2026-08-19). Es ist also nichts abzuleiten, nur nachzuschlagen.

Warum es lohnt (gemessen 2026-08-19):

| | Items |
|---|---|
| tragen eine Raumgruppe (`P690`) | 2876 |
| davon **ohne** Punktgruppe | 2858 |
| davon über das Raumgruppen-Item auflösbar | **2851** |
| darunter Mineralarten | 2602 |

Zum Vergleich: von 6301 Mineralarten führen bisher **19** eine Punktgruppe.

**Mehrere Raumgruppen am Item → nichts.** 56 Items tragen mehr als eine
`P690`, meist weil mehrere Modifikationen an einem Item hängen. Welche gemeint
ist, entscheidet die Fachfrage; die Zeile geht als
`MANUELLE_KLAERUNG_NOETIG` heraus, mit beiden Raumgruppen im Status. Sechs
Raumgruppen-Items führen selbst keine Punktgruppe — dort entsteht gar keine
Zeile.

**Zweiter Weg: frisch aus der COD.** Schlägt die COD-Stufe eine Raumgruppe
vor, kommt die Punktgruppe in derselben Zeilengruppe mit — belegt mit
*derselben* Originalarbeit und mit demselben Klärungsvermerk: ist die
Modifikation offen, ist es die Punktgruppe auch.

**Was am Item steht, gewinnt.** Beide Wege können sich widersprechen: Graphit
trägt Raumgruppe 194, die COD-Suche nach `C` findet aber überwiegend Diamant
(225). Dann gilt der Befund am Item; die abweichende COD-Raumgruppe bleibt als
eigene Zeile sichtbar und damit prüfbar.

**Beleg.** Der Weg über `P690` am Item geht **ohne S-Beleg** raus (wie die
beiden anderen Ableitungen), der Weg über die COD mit dem DOI der
Originalarbeit.

Abschaltbar mit `--no-punktgruppe`.

### Längenausdehnungskoeffizient (P5672)

Die einzige Größe, die **nur** aus der englischen Elementinfobox kommt: die
deutsche Infobox hat kein solches Feld (an Kupfer, Titan und Eisen geprüft),
die Chembox auch nicht, und das Materials Project rechnet keine thermische
Ausdehnung. Sie fällt damit ausschließlich im Periodensystem-Modus an.

Das Feld heißt `thermal expansion comment` und steht in der Form

```
{{val|16.64|e=−6}}/K (at&nbsp;20&nbsp;°C)<ref name="Arblaster 2018" />
```

also 16,64 µm/(m·K) — genau die einzige laut Constraint erlaubte Einheit
(`Q56025776`) — **mit ausdrücklicher Temperatur**, die als `P2076` mitgeht.
Ältere Vorlagen führen stattdessen `thermal expansion at 25` als bloße Zahl,
die dort bereits in µm/(m·K) steht.

An allen 118 Elementvorlagen gemessen (2026-08-19):

| Fall | Zahl | Ergebnis |
|---|---|---|
| isotroper Wert mit Temperatur | 38 | `VORSCHLAG` (33 davon mit eigenem `<ref>`, meist Arblaster 2018 → ISBN-Beleg statt Import) |
| anisotrop | 24 | `MANUELLE_KLAERUNG_NOETIG` |
| unbrauchbar | 11 | nichts |
| ohne Angabe | 45 | nichts |

**Anisotrope Elemente werden nicht vorgeschlagen.** Bei Titan, Zink oder
Beryllium hängt der Koeffizient von der Kristallachse ab; die Infobox nennt
als Hauptwert das Mittel α_V/3 und die Achsenwerte in einer Fußnote. Ein
einzelner Wert ohne Achsenangabe wäre in Wikidata eine Halbwahrheit — das
entscheidet niemand nebenbei, also geht die Zeile zur Klärung.

**Unbrauchbar** heißt hier: „at r.t." statt einer Zahl (Holmium, Erbium,
Thulium …) und Werte, die sich auf eine Modifikation beziehen
(`diamond: 0.8`, `β form: 5–7`, `amorphous: 37`). Beides wäre geraten.

**Die Property ist noch leer.** Am 2026-08-19 trägt in ganz Wikidata **keine
einzige** Aussage `P5672`. Die 38 Vorschläge wären die ersten — ein Grund
mehr, sie einzeln durchzusehen.

### NIST Chemistry WebBook: ΔfH° und S°

Zwei Größen, die keine andere Quelle hier liefert — **Standardbildungsenthalpie**
(`P3078`) und **molare Standardentropie** (`P3071`), je Aggregatzustand.
Gesucht wird über die **CAS-Nummer** am Item (`7440-50-8` → `C7440508`).

**Der Beleg ist nie das WebBook.** NIST-Standardreferenzdaten sind nach dem
Standard Reference Data Act (15 U.S.C. § 290e) urheberrechtlich geschützt —
anders als sonstige Werke US-amerikanischer Bundesbehörden, die die
Lizenzseite von NIST ausdrücklich davon abgrenzt. Auf jeder Seite steht *„Data
compilation copyright by the U.S. Secretary of Commerce … All rights
reserved."* Wikidata ist CC0. Übernommen wird deshalb nur, was das WebBook
einer **zitierbaren Originalarbeit** zuschreibt, und belegt wird mit dieser
Arbeit — dieselbe Linie wie bei COD (DOI der Originalarbeit statt der
Datenbank). Das WebBook bleibt Fundstelle in `ref_note`.

Zwei Werke decken den Bestand ab; beide ISBNs am 2026-08-23 über OpenLibrary
geprüft:

| Kürzel im WebBook | Werk | Beleg |
|---|---|---|
| `Cox, Wagman, et al., 1984` | CODATA Key Values for Thermodynamics, Hemisphere | ISBN 0-89116-758-7 |
| `Chase, 1998` | NIST-JANAF Thermochemical Tables, 4. Aufl., J. Phys. Chem. Ref. Data Monograph 9 | ISBN 978-1-56396-820-4 |

Zur ersten Zeile: das WebBook datiert auf 1984 (CODATA-Bericht), das gedruckte
Werk erschien 1989 — die ISBN gehört zum Buch. Zur zweiten: OpenLibrary löst
die ISBN auf ebendiese 1951 Seiten der Reihe „J. Phys. Chem. Ref. Data, no. 9"
auf, genau wie das WebBook zitiert; es gibt drei ISBNs (Gesamtwerk und beide
Teile) mit identischem Titel.

**Was keiner dieser beiden Quellen zugeschrieben ist, wird nicht
übernommen** — ohne Originalarbeit gäbe es keinen Beleg. Solche Werte
verschwinden aber nicht still: am Ende des Laufs meldet das Skript, wie viele
es waren und aus welchen Quellen, damit `NIST_QUELLEN` ergänzt werden kann.

**Der Aggregatzustand ist Pflicht.** Beide Properties verlangen ihn laut
Constraint als Qualifikator (`P515`) — ohne ihn ist die Zahl bedeutungslos,
weil ΔfH° von Feststoff, Flüssigkeit und Gas verschieden ist. Genau in dieser
Aufteilung liefert das WebBook sie auch (`ΔfH°solid`, `ΔfH°gas`):

```
Q753	P3078	337.4U752197	P515	Q11432	S957	"0-89116-758-7"
```

**Zwei Quellen zur selben Größe** sind der Regelfall (CODATA *und* JANAF).
Stimmen sie auf 1 % überein, gilt CODATA — das sind die international
abgestimmten Schlüsselwerte. Weichen sie ab, wird nichts vorgeschlagen,
sondern `MANUELLE_KLAERUNG_NOETIG` gesetzt, mit beiden Zahlen im Status.

**Gegenprobe über die Summenformel.** Das WebBook liefert auf jeder Seite
`molecularFormula` als JSON-LD mit. Steht am Item eine Formel und lassen sich
beide deuten, müssen sie übereinstimmen — eine CAS-Nummer kann am falschen
Item stehen, die Zusammensetzung lügt nicht.

**Tempo.** `robots.txt` des WebBook verlangt `Crawl-delay: 5`; die Stufe hält
ihn ein. Je Item mit CAS-Nummer fallen zwei Abrufe an, also rund zehn
Sekunden. Deshalb greift sie nur, wo eine CAS-Nummer dasteht — und die ist in
den Gruppen sehr ungleich verteilt:

| Gruppe | Items | mit CAS |
|---|---|---|
| chemische Elemente | 118 | 116 |
| Oxide mit Formel | 155 | 141 |
| Mineralarten | 6304 | 60 |
| Legierungen | 1122 | 30 |

Legierungen führt das WebBook ohnehin nicht — es ist eine Verbindungsdatenbank.

**Wie viel davon wirklich ankommt**, an allen 258 Items mit CAS-Nummer
gemessen (2026-08-23, ein Abruf je Item):

| | Items |
|---|---|
| mit Thermochemie im WebBook | **120** (69 Oxide, 51 Elemente) |
| davon kondensierte Phase / Gasphase | 86 / 97 |
| Seite vorhanden, aber ohne Thermodaten | 89 |
| CAS-Nummer dem WebBook unbekannt | 49 |

Die Ausbeute ist bei den Lanthanoiden und Actinoiden am dünnsten — für
Lanthan etwa liefert das WebBook eine Seite, aber keine einzige
thermochemische Tabelle. Ein Lauf über beide Gruppen dauert wegen des
Crawl-delay rund 40 Minuten.

Abschaltbar mit `--no-nist`.

### Die drei Wikipedia-Stufen und ihre Fallstricke

Welche Infobox gelesen wird, entscheidet sich am Artikel. Alle drei Stufen
belegen als Wikimedia-Import (`P143` + `P4656` mit Permalink auf die
konkrete Version), sofern der Wert nicht selbst einen Einzelnachweis trägt.

**1. `{{Infobox Chemisches Element}}` (de).** Die ergiebigste Quelle
überhaupt — sie führt als einzige spezifische Wärmekapazität (`P2056`),
elektrische Leitfähigkeit (`P2055`), Schallgeschwindigkeit (`P2075`),
Poissonzahl (`P5593`) und CAS-Nummer (`P231`). Sie steht im **Artikel**, nicht
in einer eigenen Vorlagenseite. Der Artikeltitel wird über den
Wikidata-Sitelink aufgelöst und **nicht** aus dem Elementnamen geraten: Titan
liegt unter „Titan (Element)", weil „Titan" der Mond bzw. die Mythologie ist.

Deutsche Zahl- und Markup-Eigenheiten, alle real im Bestand:

| Beispiel | Eigenheit |
|---|---|
| `8,96&nbsp;g/cm³ (20 [[Grad Celsius\|°C]])` | Dezimalkomma, Messtemperatur im Text |
| `58,1 · 10<sup>6</sup>` | Zehnerpotenz als Markup |
| `1812 ± 1 [[Kelvin\|K]]` | Toleranzangabe |
| `etwa 7,14 · 10<sup>6</sup>` | Unschärfewort |
| `α-Eisen: kubisch raumzentriert<br />γ-…` | **mehrdeutig** |
| `Graphit: 2,26 g/cm<sup>3</sup><br />Diamant: 3,51` | **mehrdeutig** |
| `<!--G: 119–165 W/(m·K)-->` | auskommentiert |

Werte mit `<br` oder `:` bezeichnen mehrere Modifikationen und werden
**verworfen** — sonst landete willkürlich Graphit oder Diamant als „der" Wert
des Elements in Wikidata.

**Dasselbe Feld trägt `{{Infobox Mineral}}`.** „Mohshärte" heißt in der
Mineralvorlage genau wie in der Elementinfobox, und ein Artikel trägt immer
nur eine der beiden — ein Eintrag in der Feldkarte bedient deshalb beide.
Für die Mineralgruppe ist das die erste Größe überhaupt, die aus dem Artikel
selbst kommt: Wikidata hat sie an 285 der Mineralarten (2026-08-23), die
deutsche Wikipedia an praktisch allen.

Der Haken ist die Härteangabe selbst. In einer Stichprobe von 60 Mineral-
artikeln (2026-08-23) führen **alle 60** das Feld, aber nur **20** mit einem
einzelnen Wert:

| Beispiel | Was daraus wird |
|---|---|
| `7<ref name="Bačík et al. 2013" />` | 7 — Beleg aus dem `<ref>` |
| `4,5` | 4,5 |
| `≈&nbsp;5<ref …/>` | 5 — Unschärfewort fällt weg |
| `2 bis 3` | **verworfen** — Bereich |
| `6 bis 6,5 (2 wenn massiv)` | **verworfen** — Bereich |
| `''nicht definiert''` | **verworfen** — keine Zahl |
| `geschätzt: 5` | **verworfen** — beschrifteter Wert |

Die Ritzhärte ist von Natur aus ein Intervall, deshalb ist der Bereich hier
der Normalfall und nicht die Ausnahme. Ein Mittelwert daraus wäre erfunden;
Wikidatas Mengentyp könnte das Intervall zwar als Ober- und Untergrenze
tragen, dafür müsste aber die ganze Zeilenerzeugung Schranken kennen. Bis
dahin gilt die Hausregel: lieber nichts vorschlagen als raten. Gemessen am
Lauf über 25 Mineralarten (2026-08-23) bleiben so 9 Werte, 7 davon als
`VORSCHLAG`.

Werte **unterhalb** der Skala werden nicht verworfen, sondern als
`MANUELLE_KLAERUNG_NOETIG` ausgewiesen: Caesium steht mit 0,2 in der
Elementinfobox — ein richtiger Wert, den `P1088` wegen seines
Bereichs-Constraints trotzdem nicht annimmt. Das ist eine Entscheidung für
den Menschen, kein Fall für den Papierkorb.

**2. `Template:Infobox <element>` (en).** Je Element eine eigene Vorlagenseite.
Angenehm: `melting point K` / `boiling point K` stehen bereits in Kelvin, also
in der Wikidata-Einheit; `Mohs hardness` steht dort ebenfalls (`|Mohs
hardness=3.0` bei Kupfer). Trotzdem nötig ist Vorsicht — reale Fälle:
`density=8.935&nbsp;g/cm<sup>3</sup>&thinsp;<ref …/>`,
`thermal conductivity=graphite: 119-165` (Prosa plus Bereich),
`electrical resistivity at 20=2.3{{e|3}}` (Vorlage im Wert). Deshalb wird
Markup entfernt und anschließend nur ein **sauberer** Zahlwert akzeptiert;
alles mit Buchstaben, Bereich oder Restvorlage wird verworfen.

**3. `{{Chembox}}` (en, Verbindungen).** Steht wieder im Artikel selbst. Die
Einheit steckt hier im **Feldnamen** (`MeltingPtC` vs. `MeltingPtK`), es muss
also nichts geraten werden. Im Mapping stehen die Kelvin-Felder vor den
Celsius-Feldern, damit der Wert ohne Umrechnung gewinnt, wenn die Box beide
führt.

**Einzelnachweise schlagen den Import.** Trägt ein Infobox-Wert einen eigenen
`<ref>` mit DOI oder ISBN, ist das ein echter Literaturbeleg und wird statt
des Wikimedia-Imports gesetzt. Zu behandeln sind dabei `[[doi:…]]`,
`{{DOI|…}}`, `|DOI=…`, `|ISBN=…` — und vor allem die reine **Wiederverwendung**
`<ref name="Binder" />`, deren Inhalt an anderer Stelle im Artikel steht und
über den Namen aufgelöst werden muss. Ohne das ginge bei der spezifischen
Wärmekapazität der Beleg verloren.

## Werkstoffgruppen (`--group`)

Statt über Elemente oder Formeln lässt sich eine ganze Gruppe bestehender
Wikidata-Items durchgehen. Wie ergiebig das ist, hängt stark an der Gruppe
(gemessen 2026-08-16):

| Gruppe | Items | mit Formel | mit de-Artikel |
|---|---|---|---|
| `minerale` | 6301 | 5694 | 1806 |
| `legierungen` | 568 | 10 | 178 |
| `oxide` | 154 | 154 | 108 |
| `polymer` | ~795 | 8 | 113 |
| `magnetwerkstoffe` | ~17 | 0 | wenige |
| `keramik` | ~1021 | 0 | ~210 |
| `glas` | ~1160 | wenige | ~73 |

**`polymer`** ist der Subtree unter `Q11474` „Kunststoff" (nicht `Q81163`
„polymer", das auch Biopolymere umfasst). Wie bei den Legierungen ist die
Summenformel die Ausnahme — der Ertrag liegt in Struktur und
Infobox-Kennzahlen. **`magnetwerkstoffe`** (`Q949573`) ist winzig und trägt
den Isotopenfilter `FILTER NOT EXISTS { ?i wdt:P1086 ?z }`: ohne ihn zieht ein
schiefer Instanzpfad über Nickel ~40 Nickel-Isotope herein (dieselbe Fehlkante
wie „Metalle unter Legierung", siehe unten). `MAGNET_PATTERN` verankert neben
`Q949573` auch `Q2554911` (weichmagnetische Werkstoffe) und `Q9259184`
(ferromagnetic material) als eigene Wurzeln — so bleibt der ferromagnetische
Zweig auch dann in der Grundgesamtheit, wenn die eine P279-Kante unter
`Q949573` (die die `verkehrt`-Prüfung fälschlich zur Löschung meldet) fällt.
Der Lauf lohnt vor allem für die Strukturprüfung.

**`keramik`** (`Q45621`) nimmt **nur die Klassen** (`P279*`, ~1021), nicht die
Instanzen: allein unter „fine ceramic" (`Q13464614`) hängen ~49.000 Museums-
und Fundstücke — konkrete Objekte *aus* Keramik, keine Werkstoffsorten. Keine
Summenformel, aber ~210 mit de-Artikel; der Ertrag liegt in Struktur und
Infobox-Kennzahlen. **`glas`** (`Q11469`) ist mit ~1160 Items (davon ~165
Klassen) handhabbar und läuft wie `polymer` mitsamt Instanzen; kein Element
hängt unter `Q11469`, ein Isotopenfilter ist nicht nötig. Ausgeschlossen wird
`Q1207302` „jar" (de-Label ebenfalls „Glas") **mitsamt seinem Ast** (Tonkrug,
decorative jar, Glas-Gefäße …) — Behälter, keine Werkstoffe. Sie hingen nur
über die schiefe Kette `Q1207302 → Q5164895` „Hohlglas" im Glas-Baum; diese
Kette ist auf Wikidata inzwischen gekappt, `GLAS_AUSSCHLUSS_FILTER`
(`FILTER NOT EXISTS { ?i wdt:P279*/… wd:Q1207302 }`, gilt für Benchmark,
materialswiki und ClassCheck) hält den Ast auch dann draußen, wenn die Kante
zurückkehrt.

**`minerale`** ist mit Abstand die ergiebigste Gruppe: Instanzen von
`Q12089225`, also die von der IMA geführten Arten — bewusst **nicht** der
Subtree unter `Q7946` „Mineral", der auch Gruppen und Sammelbegriffe enthält.
Bei den Legierungen ist die Summenformel dagegen die Ausnahme (Stahl hat
keine), weshalb COD und Materials Project dort kaum etwas beitragen können.
Dafür fehlt dort massenhaft die chemische Metaklasse: 313 Legierungen tragen
gar kein `P31`. Die entwirft aber nicht mehr dieses Werkzeug, sondern die
Prüfung `metaklasse` in
[Material class structure](../Material%20class%20structure/README.md#chemische-metaklasse-p31-für-legierungen).

**`legierungen` braucht einen Filter, sonst ist die Grundgesamtheit Müll.**
Die naheliegende Abfrage — alles unter Legierung (`Q37756`) — liefert 3718
Items. Grund ist ein Modellierungsfehler in Wikidata:

```
Q11426 "Metalle"  wdt:P279  Q37756 "Legierung"
```

Metalle sind dort eine *Unterklasse* von Legierung, fachlich genau verkehrt
herum. Dadurch hängt jedes Metall und jedes Metallisotop unter „Legierung";
die Trefferliste füllt sich mit Selen-78, Rubidium-87 und gediegenem Kupfer
(geprüft 2026-08-16, Pfad: Selen-78 → Selen → Halbmetalle → Metalle →
Legierung). Ausgeschlossen wird deshalb, was eine **Ordnungszahl** trägt:
Elemente und ihre Isotope. Das ist der präzise Schnitt — aus 3718 Items
werden 1081.

Ein früherer Versuch schnitt stattdessen den ganzen Metalle-Zweig weg. Das
war zu grob und riss 17 echte Legierungen mit, darunter **Stahl**, Gusseisen
und Ti-6Al-4V — die hängen völlig zu Recht auch unter „Metalle". Gemessen an
den 94 klassifizierten Legierungen aus [[en:List of named alloys]]: der alte
Filter ließ 77 durch, der neue alle 94.

### Überschneidende Gruppen laufen nur einmal

`minerale` lässt aus, was auch in `oxide` steht — für die Oxide gibt es einen
eigenen Aufruf, und dieselben Vorschläge in zwei Dateien helfen niemandem. Der
Ausschluss steht als `"ausschluss": ("oxide",)` in der Gruppendefinition und
greift **vor** `--limit`, damit die Zahl dort die tatsächlich bearbeiteten
Items meint. Wie viele wegfallen, meldet der Lauf auf stderr;
`--mit-ueberschneidungen` nimmt sie wieder dazu.

Die Überschneidung ist klein — es geht um Sauberkeit, nicht um Tempo
(gemessen 2026-08-23):

| Paar | gemeinsame Items |
|---|---|
| `minerale` ∩ `oxide` | 7 (Eis, Stishovit, Coesit, Minium …) |
| `minerale` ∩ `legierungen` | 26 |

Die 26 Minerale in der Legierungsgruppe sind **nicht** ausgeschlossen: für
die Stufen dieses Werkzeugs ist die Legierungsgruppe kein Duplikat, sondern der
einzige Ort, an dem diese Items überhaupt vorkommen. Wer es anders will,
ergänzt eine Zeile in `WERKSTOFFGRUPPEN`.

Fällt die Abfrage der anderen Gruppe aus, wird **nichts** ausgeschlossen —
lieber doppelt bearbeitet als still um Items gebracht.

**`oxide`** verlangt die Summenformel als Teil der *Definition*, nicht bloß
als Filter: der Subtree unter `Q50690` umfasst 27670 Items, die allermeisten
labellose Massenimporte ohne jede Angabe. Ohne Formel ist ein Item für diesen
Zweck wertlos.

### Prüfliste statt Datenquelle

Für die Gruppe aus [[en:List of named alloys]] wird zusätzlich **gemeldet**,
welche Items nicht als Legierung klassifiziert sind — vorgeschlagen wird dazu
nichts. Die Einordnung eines Werkstoffs in die Klassenhierarchie ist eine
fachliche Entscheidung, und [[Wikidata:WikiProject Materials/Materials]]
verlangt dafür eine differenzierte Einhängung (Ferrous alloy, Alloy steel …),
die sich aus dem Basismetall allein nicht ableiten lässt.

Die Liste ist als Prüfliste ohnehin wertvoller denn als Datenquelle. Gemessen
2026-08-16: 140 benannte Legierungen, davon 104 mit Wikidata-Item, davon 94
als Legierung klassifiziert. Die Kennwerte sind praktisch leer —
Zugfestigkeit 0 von 104, Elastizitätsmodul 2, Dichte 6.

### Laufzeit

Gemessen an fünf Oxiden mit allen Stufen (2026-08-23, je ein frischer Prozess):

| | vorher | nachher |
|---|---|---|
| Gesamt | 68,9 s | **17,7 s** |
| je Item | 13,8 s | **3,5 s** |
| Anfragen je Item | 8,8 | 6,0 |

Im Periodensystem-Modus (fünf Elemente): 11,0 s → **4,7 s** je Element. Vier
Maßnahmen, keine davon ändert ein Ergebnis:

**1. Gedrosselt wird je Gegenstelle, nicht global.** Ein Lauf spricht sieben
Server an (Wikidata-Query, Wikidata-API, COD, Materials Project, zwei
Wikipedias, WebBook). Eine gemeinsame Uhr summierte deren Wartezeiten: 44
Anfragen waren 44 Wartesekunden. Jetzt hat jeder Server seine eigene Uhr — die
Rücksicht bleibt dieselbe (≤ 1 Anfrage/s je Server), die Wartezeiten laufen
aber nebeneinander statt hintereinander. Das war der größte Einzelposten.

**2. Der Aussagenbestand kommt in Chargen.** Statt `wbgetclaims` je Item holt
`wbgetentities` 50 Items auf einmal — bei 6301 Mineralen 127 Anfragen statt
6301. **Der Siedepunkt fällt dabei mit ab:** die Rohaussagen tragen Wert und
Einheit längst, wofür vorher eine eigene SPARQL-Abfrage *je Item* nötig war.

**3. Quellen, die nichts mehr beitragen können, werden nicht befragt.** Trägt
das Item alle Properties einer Stufe schon, entfällt der Abruf — nicht bloß
die Zeile. Das ist billig zu prüfen, seit (2) den Bestand ohnehin vorlädt.

Wie viel das bringt, hängt stark an der Gruppe (gemessen 2026-08-23):

| | Mineralarten (6304) | Oxide (155) |
|---|---|---|
| alle COD-Properties vorhanden | 8 | 0 |
| alle MP-Properties vorhanden | 131 | 28 |
| alle NIST-Properties vorhanden | 0 | 4 |

In den großen Gruppen greift es also **selten** — Items tragen fast nie den
*vollständigen* Satz einer Quelle. Im Periodensystem-Modus dagegen oft: dort
wurde die MP-Stufe bei drei von fünf Elementen übersprungen. Was der Lauf sich
gespart hat, meldet er am Ende auf stderr.

**Der Preis:** Abschnitt 2 des Entwurfs (`BEREITS_VORHANDEN`) enthält dann nur
noch, was beim Suchen nebenbei anfiel — nicht mehr jede geprüfte und verworfene
Möglichkeit. Wer den vollständigen Prüfbericht braucht, nimmt
`--auch-vorhandene`. Die Gegenprobe an fünf Oxiden: **dieselben 23 Vorschläge**
in beiden Läufen, nur acht `BEREITS_VORHANDEN`-Zeilen fehlen.

**4. Das WebBook liefert beide Phasen in einem Abruf.** `Mask` ist eine
Bitmaske; `Mask=3` (Gasphase | kondensierte Phase) enthält alle Zeilen der
beiden Einzelseiten — an Kupfer geprüft. Bei `Crawl-delay: 5` sind das
5 statt 10 Sekunden je Item mit CAS-Nummer.

**Was nicht umgesetzt ist:** echte Parallelität. Während der Lauf fünf
Sekunden auf das WebBook wartet, liegen die sechs anderen Gegenstellen
brach — ein kleiner Thread-Pool über die Items wäre der nächste große Hebel,
verträgt sich aber nicht ohne Weiteres mit der zeilenweise geschriebenen
Vorschlagstabelle und der stabilen Reihenfolge der Chargen. Ebenso fehlt ein Antwort-Cache auf
der Platte: ein abgebrochener Lauf holt beim Wiederholen alles neu.

### Chargenbetrieb (`--batch-size`)

Bei 6301 Mineralen läuft ein Durchgang stundenlang, und ohne Zwischenstände
gäbe es bis zum Schluss keine einspielbaren QuickStatements. Mit
`--batch-size N` werden Vorschlagstabelle und Entwurf nach **jeder** Charge geschrieben —
man kann also einspielen, während der Rest noch läuft, und ein Abbruch kostet
höchstens die angefangene Charge.

Der Stand landet in einer Fortschrittsdatei; `--weiter` setzt dort auf. Nach
einem Abbruch steht der Fortschritt auf der letzten **vollständigen** Charge,
die angefangene wird wiederholt — lieber doppelt geprüfte Items als
übersprungene.

### Auswahl im Periodensystem-Modus: Metalle und Halbmetalle

Standardmäßig werden nur **Metalle und Halbmetalle** durchgegangen — 98 der
118 Elemente. Nichtmetalle tragen zu einem Werkstoffprojekt nichts bei, und
ihre Festkörper-Kennwerte wären ohnehin größtenteils gesperrt (siehe unten:
die Hälfte von ihnen ist bei 20 °C ein Gas). `--no-nur-metalle` nimmt sie
wieder dazu.

Die Einteilung steht als **feste Liste** im Code, nicht als Wikidata-Abfrage.
Gemessen (2026-08-16):

| Abfrage | gefundene Metalle | fehlt |
|---|---|---|
| `P31/P279*` → Metalle (Q11426) | 55 von ~90 | Cr, Mn, Co, Ni, Re, Sr, Ba, alle Lanthanoide und Actinoide |
| `Q19588` Übergangsmetalle | 17 statt ~38 | |
| `Q11426` direkt | 7 | |

Chrom, Mangan, Cobalt und Nickel sind zentrale technische Werkstoffe — eine
Auswahl, die sie verliert, ist unbrauchbar. Die Lehrbuch-Einteilung des
Periodensystems ist dagegen vollständig und unstrittig; definiert wird über
die **Nichtmetalle** (die kürzere, stabilere Liste), alles andere ist Metall
oder Halbmetall. Grenzfälle bewusst gesetzt: Po als Halbmetall, At als
Nichtmetall, Ts und Og als Nichtmetalle (rein theoretische Zuordnung).

### Keine Festkörper-Kennwerte an Gasen

Das Materials Project rechnet ausschließlich kristalline Festkörper — für
Stickstoff oder Neon also die Tieftemperaturphase. Ohne Filter landen deren
Werte an einem Item, das den Stoff bei Normalbedingungen beschreibt. Das ist
real passiert: **Neon trägt in Wikidata bereits Kompressionsmodul, Schubmodul
und Poissonzahl.**

Ist der Siedepunkt ≤ 293,15 K, werden deshalb **weder aus MP noch aus COD noch
aus den Infoboxen** vorgeschlagen:

| Größe | Warum nicht |
|---|---|
| Kompressionsmodul, Schubmodul, Poissonzahl | am Gas nicht definiert |
| Dichte (P2054) | die des Festkörpers — für Neon 1,815 g/cm³ statt 0,0009 g/cm³ |
| Kristallsystem (P556), Raumgruppe (P690) | ein Gas hat bei Raumtemperatur keine Kristallstruktur |

Nicht gesperrt sind die **Schallgeschwindigkeit** (in Gasen sauber definiert und
gemessen, Luft rund 343 m/s) und die **COD-ID** — sie ist ein Verweis auf einen
Datenbankeintrag, keine Aussage über den Stoff bei Raumtemperatur.

Zwei Fallstricke, beide im Code behandelt:

- **P2102 steht in gemischten Einheiten** — am Bestand 32× Grad Celsius, 27×
  Grad Fahrenheit, 11× Kelvin. Wikidatas normalisierte Werte (`psn:`) helfen
  nicht, weil Celsius→Kelvin eine Verschiebung ist und nur multiplikativ
  normalisiert wird. Ohne eigene Umrechnung gilt Fluor mit „−307" (Fahrenheit)
  als absurd kalt und Iod mit „184,4" (Celsius) als Gas.
- **Nur 70 der 118 Elemente führen überhaupt einen Siedepunkt.** Erkannt werden
  damit H, He, Ne, Ar, N und F; für O, Cl, Kr, Xe und Rn fehlt die Angabe. Dort
  wird nichts unterdrückt — lieber ein Vorschlag zu viel, der beim Durchsehen
  auffällt, als eine still verschluckte Zeile. P515 (Aggregatzustand) taugt als
  Ersatzsignal nicht: es ist bei **keinem** Element gesetzt.

### Bewusst offen: die Metaklasse der reinen Stoffe

Für **Gemische** ist die Metaklasse umgesetzt — nicht mehr hier, sondern in
[Material class structure](../Material%20class%20structure/README.md#chemische-metaklasse-p31-für-legierungen);
dort ist sie eindeutig bestimmt. Für **reine Stoffe** bleibt sie liegen, und
zwar aus demselben Grund wie beim ersten Anlauf.

Der Widerspruch, an dem es hängt (gemessen 2026-08-16): Die Projektseite
[[Wikidata:WikiProject Chemistry]] bittet um
`P31 = Q113145171` für „each pure chemical substance", die verbindliche
Guideline dagegen nur für „stereochemically or isotopically defined chemical
entities". In der Praxis tragen 1.280.233 Items die Metaklasse — aber
**keines der 118 Elemente**.

Genau in diese Lücke fällt auch die Gegenprobe zur Gemisch-Prüfung: 10
Legierungen tragen `Q113145171` regelwidrig, darunter Messing. Sie werden dort
gemeldet, nicht korrigiert.

Wer die reinen Stoffe aufgreift, fängt bei jener Klärung an, nicht beim Code.

### Ausgabedateien

Beide landen im aktuellen Arbeitsverzeichnis und sind gitignoriert (siehe
[../README.md](../README.md#ausgabedateien)). Der Dateiname trägt
standardmäßig einen Zeitstempel (`vorschlaege_2026-08-15_1102.md`), für
Tabelle und Entwurf denselben — so überschreibt kein Lauf den vorherigen, und
die beiden Dateien sind als Paar erkennbar.

Wer feste Namen braucht, setzt `--out`/`--qs-out`. Dann wird der
QuickStatements-Entwurf **vor** dem Lauf geleert: Er entsteht erst am Ende,
und ohne das Leeren stünde nach einem Abbruch der vollständige Entwurf des
letzten Laufs neben der frisch und nur teilweise geschriebenen
Vorschlagstabelle — zwei Dateien, die nicht zusammengehören. Nach einem Abbruch trägt der Entwurf
deshalb nur die Zeile `# Lauf noch nicht abgeschlossen …`.

### Status in der Vorschlagstabelle

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

`PROPERTY_MAP` in [properties.py](properties.py) enthält nur auf wikidata.org
verifizierte Properties. **Bedient** werden davon die 22 unten — sie haben
einen MP-Feldpfad, eine Infobox-Feldkarte oder eine Ableitung hinter sich:

| Größe | Property | Einheit / Typ |
|---|---|---|
| Dichte | `P2054` | g/cm³ |
| Schmelzpunkt | `P2101` | Kelvin |
| Siedepunkt | `P2102` | Kelvin |
| Kristallsystem | `P556` | Item (7 Werte, 1:1 zum MP-Vokabular) |
| Kompressionsmodul | `P5668` | Gigapascal |
| Schubmodul | `P5673` | Gigapascal |
| Wärmeleitfähigkeit | `P2068` | W/(m·K) |
| Elektrische Leitfähigkeit | `P2055` | S/m |
| Spezifischer Widerstand | `P5679` | Ω·m |
| Spezifische Wärmekapazität | `P2056` | J/(kg·K) |
| Schallgeschwindigkeit | `P2075` | m/s |
| Poissonzahl | `P5593` | dimensionslos |
| Mohshärte | `P1088` | dimensionslos (Skala 1 … 10) |
| CAS-Nummer | `P231` | external-id |
| besteht aus | `P527` | Item (funktionale Gruppe, Anzahl als `P1114`) |
| enthält Elemente von | `P2670` | Item (Element, Anzahl als `P1114`) |
| Raumgruppe | `P690` | Item (230 Raumgruppen über `P9733`) |
| Punktgruppe | `P589` | Item (32 Punktgruppen, am Raumgruppen-Item abgelesen) |
| Standardbildungsenthalpie | `P3078` | kJ/mol, **mit Aggregatzustand** |
| molare Standardentropie | `P3071` | J/(mol·K), **mit Aggregatzustand** |
| COD-ID | `P9824` | external-id |
| Längenausdehnungskoeffizient | `P5672` | µm/(m·K), **mit Temperatur** |

Seit dem 28.08.2026 stehen zusätzlich die **44 übrigen Properties des
WikiProject Materials** in der Tabelle (aus
[../benchmark/properties_snapshot.json](../benchmark/properties_snapshot.json),
Datentyp und Einheiten-Constraint an dem Tag von wikidata.org geholt). Sie
sind dort nur *bekannt*, nicht *bedient*: keine Quelle liefert sie, und wo
die Property gar keinen Einheiten-Constraint trägt, bleibt `unit_qid` bewusst
leer, bis eine Quelle den Wert wirklich liefert. Welche Properties ein Lauf
abfragt, steht in der Spalte `quellen` des
[Benchmarks](../benchmark/README.md), nicht in dieser Tabelle.

Wichtig: **Ein Eintrag in `PROPERTY_MAP` allein erzeugt noch keine
Vorschläge.** Aus dem Materials Project kommen nur Größen, die auch in
`MP_FIELD_MAP` einen Pfad haben — das sind fünf:

| Wikidata | MP-Feld | Umrechnung |
|---|---|---|
| Dichte `P2054` | `density` | keine — g/cm³ ist schon die Zieleinheit; **mit Messbedingungen**, siehe unten |
| Kristallsystem `P556` | `symmetry.crystal_system` + `symmetry.symbol` | Groß-/Kleinschreibung, dann `value_map`; Zentrierung → fcc/bcc; **Beleg aus Literatur** |
| Kompressionsmodul `P5668` | `bulk_modulus.vrh` | keine — GPa ist die Zieleinheit |
| Schubmodul `P5673` | `shear_modulus.vrh` | keine — GPa ist die Zieleinheit |
| Poissonzahl `P5593` | `homogeneous_poisson` | keine; **mit Temperatur** (0 K), siehe unten |

Die **Einheiten sind der Fallstrick** — seit dem 28.08.2026 aber keiner
mehr: kein einziges MP-Feld wird noch umgerechnet. Die Moduln gehen in
Gigapascal nach Wikidata, weil der Einheiten-Constraint von `P5668` und
`P5673` ausschließlich `Q53448922` (Gigapascal) zulässt — genau die Einheit,
in der MP rechnet. Vorher schrieb das Werkzeug Pascal (×10⁹) und verletzte
damit bei jeder Modul-Aussage den Constraint. Die Dichte kommt ohnehin schon
in g/cm³. Die Faktoren stehen in `MP_FIELD_MAP` und sind einzeln getestet
([../tests/test_mp.py](../tests/test_mp.py)). Die Moduln
kommen als Voigt-Reuss-Hill-Mittel (`vrh`), das übliche Mittel für
polykristalline Werkstoffe — nicht als `voigt` oder `reuss`.

`P527` und `P2670` entstehen ohne externe Quelle aus dem Item selbst, `P690`
und `P9824` liefert die COD, `P589` beide Wege. Alles Übrige stammt aus den
Wikipedia-Infoboxen:
bei Elementen alle 14 Kennwerte der Tabelle oben, bei Verbindungen Dichte,
Schmelz- und Siedepunkt sowie die CAS-Nummer.

Feldnamen und Einheiten stammen aus dem öffentlichen OpenAPI-Schema
(<https://api.materialsproject.org/openapi.json>, `SummaryDoc`, 69 Felder,
ausgewertet am 2026-08-15).

Bewusst **nicht** übernommen, obwohl MP es führt:

- **Bandlücke** (`band_gap`, eV) — Wikidata hat dafür **keine** Property. Es
  gibt zwei thematisch passende Items, beide als Prädikat unbrauchbar, denn
  an der mittleren Stelle einer Aussage steht zwingend eine P-Nummer:
  `Q806352` „Bandlücke" (Konzept, Energiebereich) und `Q103982939`
  „Bandlückenenergie" (physikalische Größe). Geprüft am 2026-08-13: keines
  der beiden trägt `P1687`, keine Property trägt `P1629` darauf, ein Sweep
  über alle `quantity`-Properties auf band/gap/semiconduct liefert nur
  `P2911` „time gap" und `P9279` „Egapro", und auch Silizium (Q670) und
  Galliumarsenid (Q147395) führen keine solche Aussage. Der saubere Weg wäre
  ein Property-Proposal mit `P1629` → `Q103982939`.
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

Ausgabe: `werkstoffe_vorschlaege.md` und
`werkstoffe_qs_entwurf.txt` (`--out` / `--qs-out`). Für die
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
