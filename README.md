# WikiKnowledgeGraph

Zwei eigenständige Anwendungen rund um die Frage: **Welches Wissen fehlt in
Wikidata noch als strukturierte Aussage?** Beide erzeugen ausschließlich
Vorschlagslisten zur manuellen Prüfung — es wird nie automatisch nach Wikidata
geschrieben.

| Anwendung | Verzeichnis | Was sie macht |
|---|---|---|
| **Wikidata Knowledge Graph** | [wikikg/](wikikg/) | Vergleicht die ausgehenden Links eines Wikipedia-Artikels mit den Statements des zugehörigen Wikidata-Items und zeigt fehlende Beziehungen. Enthält zusätzlich den browserbasierten *Wortfeld-Explorer*. |
| **NOMAD Wiki** | [nomadwiki/](nomadwiki/) | Holt DOI-belegte Materialdaten aus der NOMAD-Datenbank und schlägt daraus Wikidata-Statements für bereits existierende Items vor (CSV + QuickStatements-Entwurf). |

Details, Nutzung und Grenzen stehen jeweils im README der Anwendung:
[wikikg/README.md](wikikg/README.md) · [nomadwiki/README.md](nomadwiki/README.md)

## Repo-Aufbau

```
wikikg/        Anwendung 1 — Wikipedia ↔ Wikidata Abgleich
  cli.py             Kommandozeile (python -m wikikg)
  compare.py         reine Vergleichslogik, netzwerkfrei und offline testbar
  wikipedia_client.py  MediaWiki-API: Titel → QID, ausgehende Links
  wikidata_client.py   Wikidata-API: ausgehende Item-Statements, Property-Labels
  web/               Wortfeld-Explorer (statisches HTML, D3 + SPARQL)
nomadwiki/     Anwendung 2 — NOMAD → Wikidata Vorschläge
  cli.py             Kommandozeile (python -m nomadwiki) inkl. Abgleichlogik
tests/         Offline-Tests (pytest)
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

Beide Anwendungen teilen sich dieselbe Abhängigkeit (`requests`) und werden aus
dem Repo-Wurzelverzeichnis heraus als Module gestartet:

```bash
python -m wikikg --title Holz --lang de
python -m nomadwiki --elements Ti O --max 50
```

## Tests

```bash
pytest
```

Getestet wird die netzwerkfreie Vergleichslogik; alle Tests laufen offline.

## Lizenz

Siehe [LICENSE](LICENSE).
