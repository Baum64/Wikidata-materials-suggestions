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
| Dichte | 10 … 30 000 kg/m³ | Lithium 534, Osmium 22 590 |

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
Titan    4500 kg/m³   P2076=25 °C   P515=Q11438 (fest)
Eisen    7874 kg/m³   P2076=20 °C   P515=Q11438 (fest)
Brom     3120 kg/m³   P2076=20 °C   P515=Q11435 (flüssig)
Quecks. 13546 kg/m³   P2076=20 °C   P515=Q11435 (flüssig)
```

#### MP-Dichten stehen bei 0 K, nicht bei 20 °C

Für Materials-Project-Werte greift die 20-°C-Vorgabe **nicht**: Eine
DFT-Rechnung liefert das Volumen des relaxierten Grundzustands, also 0 K. Das
ist „anders angegeben" im Wortsinn, und es ist zugleich die Erklärung für die
systematische Abweichung von den Handbuchwerten — bei Raumtemperatur ist die
Zelle thermisch geweitet.

```
Q716	P2054	4670.17U844211	P459	Q1048589	P2076	0U11579	P515	Q11438	S356	"10.1063/1.4812323"
```

Ein angenehmer Nebeneffekt: Kupfer bekommt aus MP 9219 kg/m³, die Literatur
nennt 8960. Mit den Qualifikatoren widersprechen sich beide Werte am Item
nicht mehr — der eine gilt bei 0 K, der andere bei 20 °C.

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

Die **Herkunft** bleibt in der CSV-Spalte `ref_note` und im Kommentar des
Entwurfs stehen (`ohne Beleg, Identifikator - Infobox-Feld 'CAS'`), damit die
Zeile beim Durchsehen prüfbar ist. Die Belegspalten der CSV bleiben leer — ein
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
| `--periodic-table` | Vorschläge für **alle** 118 Elemente; Abgleich über das Elementsymbol `P246` statt über die Summenformel |
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
| Dichte `P2054` | `density` | g/cm³ → kg/m³ (×1000); **mit Messbedingungen**, siehe unten |
| Kristallsystem `P556` | `symmetry.crystal_system` + `symmetry.symbol` | Groß-/Kleinschreibung, dann `value_map`; Zentrierung → fcc/bcc; **Beleg aus Literatur** |
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
