# Unterthema: Ferromagnetische Werkstoffe als Unterklassen von „Magnetwerkstoff"

Manuell geprüft 2026-08-30. Ausgangsliste: 12 Werkstofffamilien der klassischen
weich-/hartmagnetischen Einteilung. Frage: Sind sie in Wikidata korrekt als
Unterklasse (P279) von **Magnetwerkstoff (Q949573)** referenziert?

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

| # | Listeneintrag | Wikidata-Item | aktueller P279-Pfad | Unterklasse von Q949573? | Vorschlag |
|---|---|---|---|---|---|
| 1 | FeNiCo-Legierungen, kristallin | kein Sammelitem; Permalloy **Q1061375**, Mu-Metall **Q307036**, Sendust **Q898730** | Q1061375 → Q31445259 (Legierung m. besond. phys. Eig.) → Legierung; Q307036 nur P31; Q898730 P31 → Legierung (Q37756) | **nein** | QS: P279 → Q2554911 (Stufe 2) |
| 2 | FeNiCo-Legierungen, amorph + nanokristallin | amorphes Metall **Q527601**, nanokristallines Material **Q6964018** (beide generisch, nicht magnetspezifisch) | → Legierung / → material | **nein** | **review-needed** – kein Item für „amorphe/nanokristalline weichmagnetische Legierung"; generische Items dürfen kein P279 → Magnetwerkstoff bekommen |
| 3 | Weichferrite (NiZn, MnZn) | Oberbegriff „ferrite" **Q114047906**; kein Item „Weichferrit" | Q114047906 → Q9259184 → Q949573 | **ja** (über Oberklasse) | ok; Lücke: Item „Weichferrit" fehlt (Anhang) |
| 4 | Kobalt-Samarium (SmCo5, Sm2Co17 …) | Samarium-Cobalt-Magnet **Q905246** (de-Label: „Legierung") | → Q428788 → Q353743 → Q11421 (Objekt-Ast) | **nein** | **review-needed** – Objekt- vs. Werkstoff-Ast, nicht selbst entscheiden |
| 5 | Neodym-Eisen-Bor (NdFeB) | Neodym-Magnet **Q908880** | → Q428788 → Q353743 → Q11421 | **nein** | **review-needed** – wie #4 |
| 6 | AlNiCo-Legierungen | Alnico **Q658684** | → Q1985623 (Nickelbasislegierung) → Legierung | **nein** | QS: P279 → Q9259184 (Stufe 2) |
| 7 | Hartferrite (Barium, Strontium) | Keramikmagnet **Q135855031**; Bariumhexaferrit **Q27259606** (Verbindung) | Q135855031 **P31** → Q11421 (kein P279); Q27259606 → chem. Verbindung | **nein** | QS: P31→P279-Tausch bei Q135855031; Item „Hartferrit" fehlt |
| 8 | PtCo-Legierungen | **kein Item** | — | — | Anhang – Lücke |
| 9 | CuNiFe / CuNiCo | Cunife **Q384195**, Cunico **Q5794802** | Q384195 P31 → Kupferbasislegierung; Q5794802 P31 → Kupfer-/Nickelbasislegierung | **nein** | QS: P279 → Q9259184 (Stufe 2) |
| 10 | FeCoCr-Legierungen | „鉄-クロム-コバルト磁石" **Q11649507** (nur ja-Label) | → Q11421 (Objekt-Ast) | **nein** | **review-needed** – wie #4; Label/Beschreibung de/en fehlen |
| 11 | martensitische Stähle | martensitischer nichtrostender Stahl **Q4704771**; generischer „martensitischer Stahl" ohne Item | → nichtrostender Stahl → Stahl → Legierung | **nein** | **review-needed** – Q4704771 ist eine Gefügeklasse, kein Magnetwerkstoff; P279 → Magnetwerkstoff wäre hier falsch |
| 12 | MnAlC-Legierungen | **kein Item** (nur Artikel Q66623241) | — | — | Anhang – Lücke |

## Wichtig: Fehlbefund im vorherigen ClassCheck-Lauf

`proposals/p279_empfehlung_magnetwerkstoffe_2026-08-30_1140.txt`, Stufe 2 [0002]
schlägt vor, `Q9259184 P279 Q949573` als „verkehrte Kante" zu **entfernen**
(Kennzahl 48:3). Diese Kante ist **korrekt** – ferromagnetic material *ist* eine
Unterklasse von Magnetwerkstoff. Die 48:3-Heuristik kippt nur, weil der
Magnetwerkstoff-Baum unterbevölkert ist – genau das, was diese Prüfung bestätigt.
**Nicht einspielen.** Ebenso [0001] (`Q744 Nickel P279 Q9259184`): Nickel als
Element gehört nicht unter eine Werkstoffklasse – aber das ist ein eigener Fall.

## Ergebnisdateien dieses Unterthemas

- `proposals/qs_class_ferromagnetika_2026-08-30.txt` – QuickStatements-Entwürfe (Stufe 2)
- `proposals/review-needed.md` – Abschnitt „Lauf 2026-08-30 … Ferromagnetische Werkstoffe"
