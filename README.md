# WikiKnowledgeGraph

Vergleicht die **ausgehenden Hyperlinks eines Wikipedia-Artikels** mit den
**ausgehenden Item-Beziehungen des entsprechenden Wikidata-Items** und zeigt
auf, welche in Wikipedia verlinkten Begriffe in Wikidata (noch) **nicht** als
strukturierte Beziehung (Statement) hinterlegt sind — also mögliche
Kandidaten für Ergänzungen im Wikidata-Datensatz.

## Idee

1. Artikel `X` in Wikipedia → Wikidata-Item `Q...` auflösen.
2. Alle ausgehenden Links von `X` im Artikelnamensraum sammeln, jeweils mit
   dem Wikidata-Item des verlinkten Artikels (falls vorhanden).
3. Alle ausgehenden "Item → Item"-Statements von `Q...` in Wikidata laden
   (z.B. `instance of`, `subclass of`, `made from material`, `part of`, ...).
4. Abgleichen: Für jeden Wikipedia-Link prüfen, ob das Ziel-Item auch als
   Wikidata-Statement-Ziel existiert.
   - **matched** — Beziehung existiert in beiden.
   - **missing** — Wikipedia verlinkt den Begriff, Wikidata kennt (noch)
     keine direkte Beziehung dorthin → Ergänzungskandidat.
   - **no_wikidata_item** — verlinkter Artikel hat kein Wikidata-Item, daher
     nicht vergleichbar.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Nutzung

```bash
python -m wikikg.cli --title Holz --lang de
python -m wikikg.cli --title Holz --lang de --format json --output output/holz.json
python -m wikikg.cli --title Holz --lang de --format csv --output output/holz.csv
```

`--lang` steuert sowohl die Wikipedia-Sprachversion als auch die
Wikidata-Label-Sprache (Fallback: Englisch).

## Tests

Die Vergleichslogik (`wikikg/compare.py`) ist bewusst frei von
Netzwerkaufrufen und wird vollständig offline getestet:

```bash
pytest
```

## Grenzen / nächste Schritte

- Es werden nur **direkte** Claims (`mainsnak`) verglichen, keine Qualifier
  oder Referenzen.
- Ein "missing" Ergebnis heißt nicht automatisch, dass die Beziehung *falsch*
  fehlt — manche Wikipedia-Links sind rein redaktionell/kontextuell und
  gehören nicht zwingend als Wikidata-Statement modelliert. Das Tool liefert
  Kandidaten, keine automatischen Edits.
- Denkbare Erweiterung: Property-Vorschlag für "missing"-Kandidaten (z.B. per
  Heuristik über die `instance of`/`subclass of`-Klasse des Zielitems, oder
  über ein Sprachmodell), sowie automatisches Anlegen von Statements über die
  Wikidata-`wbeditentity`-API (erfordert Login/OAuth und sollte nur mit
  Vorsicht bzw. manueller Prüfung erfolgen).
