# Unterthema: Magnetische Werkstoffe — Klassenkette vs. Merkmal

Manuell geprüft 2026-08-30. Ausgangsliste: 12 Werkstofffamilien der klassischen
weich-/hartmagnetischen Einteilung.

**Überarbeitet 2026-08-30** nach neuer Regel
`.claude/rules/ontology-magnetismus-p1552.md`:

- **Fall A — echte Magnetwerkstoff-Klassen** (`magnetic material Q949573`,
  `ferromagnetic material Q9259184`, `Weichmagnetische Werkstoffe Q2554911`):
  Die P279-Kette untereinander ist reine Klassenhierarchie und bleibt.
- **Fall B — konkrete Werkstoffe / Elemente** (Eisen, Nickel, Kobalt, eine
  bestimmte Legierung, ein Ferrit): P279/P31 **nur** auf die tatsächliche
  stoffliche Elternklasse (Element, Allotrop, Legierungstyp, Verbindung,
  Keramik). Das magnetische Verhalten separat über
  **has quality (P1552) → ferromagnetism (Q184207)** — nie
  `P279`/`P1552 → Q9259184` (das ist eine Klasse, kein Merkmal).
- Begründung: P279 = zeitlose, essentielle Klassenzugehörigkeit;
  P1552 = Zustands-/Verhaltensmerkmal, das quer zu mehreren Taxonomie-Ästen
  auftritt (Metalle, Ferrite, Ferrofluide) — P1552 vermeidet erzwungene
  Mehrfachvererbung über P279.

Ursprüngliche Frage war: Sind die Einträge als Unterklasse (P279) von
**Magnetwerkstoff (Q949573)** referenziert? — Für Fall B ist P279 dorthin nun
gar nicht mehr das Ziel.

## Zielklassen in Wikidata

| QID | Label | Einordnung |
|---|---|---|
| Q214609 | material | Wurzel |
| Q949573 | Magnetwerkstoff / magnetic material | P279 → Q214609 |
| Q9259184 | ferromagnetic material | P279 → Q949573 |
| Q2554911 | Weichmagnetische Werkstoffe / soft-magnetic material | P279 → Q949573 |
| Q114047906 | ferrite (magnetische Keramik) | P279 → Q9259184 |
| — | **hartmagnetischer Werkstoff** | **existiert nicht** (nur das weiche Gegenstück Q2554911) |

Paralleler Objekt-Ast (nicht Werkstoff, sondern Bauteil):
`Q11421 magnet → Q353743 permanent magnet → Q428788 rare-earth magnet`.

## Befund je Listeneintrag

Spalte „Vorschlag" überarbeitet: konkrete Werkstoffe bekommen **P1552 → Q184207**
statt P279 auf eine Magnetwerkstoff-Klasse; die stoffliche P279/P31-Kante bleibt
unverändert.

| # | Listeneintrag | Wikidata-Item | aktueller stofflicher Pfad | Vorschlag (neu) |
|---|---|---|---|---|
| 1 | FeNiCo-Legierungen, kristallin | Permalloy **Q1061375**, Mu-Metall **Q307036**, Sendust **Q898730** | Q1061375 → Legierung m. besond. phys. Eig.; Q307036 P31; Q898730 P31 → Legierung | QS: **P1552 → Q184207** je Item (Stufe 2); Legierungs-Einordnung bleibt |
| 2 | FeNiCo-Legierungen, amorph + nanokristallin | amorphes Metall **Q527601**, nanokristallines Material **Q6964018** (generisch) | → Legierung / → material | **review-needed** – generische Struktur-/Zustandsklassen, kein magnetspezifisches Ziel; kein pauschales P1552 |
| 3 | Weichferrite (NiZn, MnZn) | Oberbegriff „ferrite" **Q114047906**; kein Item „Weichferrit" | Q114047906 → Q9259184 → Q949573 | **review-needed** – Ferrit = Keramik-Klasse, nicht alle magnetisch, Ferri- statt Ferromagnetismus; bestehende P279 → Q9259184 nicht automatisch ändern |
| 4 | Kobalt-Samarium (SmCo5, Sm2Co17 …) | Samarium-Cobalt-Magnet **Q905246** (de-Label: „Legierung") | → Q428788 → Q353743 → Q11421 (Objekt-Ast) | **review-needed** – Objekt- vs. Werkstoff-Ast, nicht selbst entscheiden |
| 5 | Neodym-Eisen-Bor (NdFeB) | Neodym-Magnet **Q908880** | → Q428788 → Q353743 → Q11421 | **review-needed** – wie #4 |
| 6 | AlNiCo-Legierungen | Alnico **Q658684** | → Q1985623 (Nickelbasislegierung) → Legierung | QS: **P1552 → Q184207** (Stufe 2); Legierungs-Einordnung bleibt |
| 7 | Hartferrite (Barium, Strontium) | Keramikmagnet **Q135855031**; Bariumhexaferrit **Q27259606** (Verbindung) | Q135855031 **P31** → Q11421; Q27259606 → chem. Verbindung | **review-needed** – Ferrimagnetismus-QID nicht sicher; früherer P31→P279+Q9259184-Entwurf entfällt |
| 8 | PtCo-Legierungen | **kein Item** | — | Anhang – Lücke |
| 9 | CuNiFe / CuNiCo | Cunife **Q384195**, Cunico **Q5794802** | Q384195 P31 → Kupferbasislegierung; Q5794802 P31 → Kupfer-/Nickelbasislegierung | QS: **P1552 → Q184207** je Item (Stufe 2); Legierungs-Einordnung bleibt |
| 10 | FeCoCr-Legierungen | „鉄-クロム-コバルト磁石" **Q11649507** (nur ja-Label) | → Q11421 (Objekt-Ast) | **review-needed** – wie #4; Label/Beschreibung de/en fehlen |
| 11 | martensitische Stähle | martensitischer nichtrostender Stahl **Q4704771** | → nichtrostender Stahl → Stahl → Legierung | **review-needed** – Q4704771 ist eine Gefügeklasse; nicht alle martensitischen Stähle sind Magnetwerkstoffe, pauschales P1552 wäre falsch |
| 12 | MnAlC-Legierungen | **kein Item** (nur Artikel Q66623241) | — | Anhang – Lücke |

Zusätzlich, bestehende Fehlkante: **Nickel Q744** hängt `P279 → Q9259184`
(ferromagnetic material). Ein Element ist keine Werkstoffklasse → Kante entfernen,
`P1552 → Q184207` setzen. Eisen (Q677), Kobalt (Q740) analog ergänzen, falls die
Merkmalsaussage fehlt (im Entwurf auskommentiert).

## Wichtig: Fehlbefund im vorherigen ClassCheck-Lauf

`proposals/p279_empfehlung_magnetwerkstoffe_2026-08-30_1140.txt`, Stufe 2 [0002]
schlägt vor, `Q9259184 P279 Q949573` als „verkehrte Kante" zu **entfernen**
(Kennzahl 48:3). Diese Kante ist **korrekt** – ferromagnetic material *ist* eine
Unterklasse von Magnetwerkstoff. Die 48:3-Heuristik kippt nur, weil der
Magnetwerkstoff-Baum unterbevölkert ist – genau das, was diese Prüfung bestätigt.
**Nicht einspielen.** [0001] (`Q744 Nickel P279 Q9259184`) dagegen **ist** ein
echter Fehler: Nickel als Element gehört nicht unter eine Werkstoffklasse. Neuer
Umgang: Kante entfernen und `Q744 P1552 → Q184207` (ferromagnetism) setzen
(Stufe 2 im Entwurf).

## Ergebnisdateien dieses Unterthemas

- `proposals/qs_class_ferromagnetika_2026-08-30.txt` – QuickStatements-Entwürfe (Stufe 2)
- `proposals/review-needed.md` – Abschnitt „Lauf 2026-08-30 … Ferromagnetische Werkstoffe"
