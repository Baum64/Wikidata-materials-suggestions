# nomadwiki — NOMAD → Wikidata

Erzeugt aus der Materialdatenbank [NOMAD](https://nomad-lab.eu)
Vorschlagslisten für Wikidata-Statements. Das Skript **legt keine neuen
Wikidata-Items an und schreibt nichts automatisch nach Wikidata** — es liefert
CSV-Kandidaten zur manuellen Prüfung.

## Ablauf

1. NOMAD nach Einträgen durchsuchen, die zu einem Datensatz mit echter **DOI**
   gehören (nur DOI = zitierfähige, stabile Referenz).
2. Die Materialformel gegen **bestehende** Wikidata-Items abgleichen
   (Property `P274` "chemical formula"). Mehrdeutige Treffer (z.B. Polymorphe)
   werden als `MANUELLE_KLAERUNG_NOETIG` markiert.
3. Prüfen, ob das jeweilige Statement dort bereits existiert.
4. Alle offenen Kandidaten als CSV-Vorschlagsliste schreiben, plus einen
   QuickStatements-V1-**Entwurf**, der erst nach zeilenweiser manueller Prüfung
   eingespielt werden darf.

## Nutzung

Aus dem Repo-Wurzelverzeichnis (Installation siehe [../README.md](../README.md)):

```bash
python -m nomadwiki --elements Ti O --max 50
```

`python -m nomadwiki.cli ...` funktioniert gleichwertig.

| Option | Bedeutung |
|---|---|
| `--elements` | Elementfilter, z.B. `--elements Ti O` (alle genannten müssen enthalten sein) |
| `--max` | maximale Anzahl NOMAD-Einträge (Standard: 50) |
| `--out` | Ziel der CSV-Vorschlagsliste (Standard: `vorschlaege.csv`) |
| `--qs-out` | Ziel des QuickStatements-Entwurfs (Standard: `quickstatements_entwurf.txt`) |

Ergebnis: `vorschlaege.csv` mit den Status `VORSCHLAG`, `BEREITS_VORHANDEN`
oder `MANUELLE_KLAERUNG_NOETIG`.

## Vor dem Einsatz anpassen

Alle drei Stellen stehen im Konfigurationsblock oben in [cli.py](cli.py):

- **`USER_AGENT`** — gemäß
  [Wikimedia-User-Agent-Richtlinie](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
  mit echtem Namen/Kontakt füllen.
- **`NOMAD_FIELD_MAP`** — Feldpfade im NOMAD-Schema können sich ändern; vor
  Gebrauch im
  [NOMAD API-Dashboard](https://nomad-lab.eu/prod/v1/api/v1/extensions/docs)
  verifizieren.
- **`PROPERTY_MAP`** — nur Properties eintragen, die auf wikidata.org
  tatsächlich existieren und zum Datentyp passen. Aktuell nur verifizierte
  Properties (Dichte, Schmelzpunkt, Siedepunkt). Mechanische Kenngrößen wie
  E-Modul haben derzeit **keine** etablierte Property — nicht ergänzen, ohne
  das vorher auf wikidata.org zu prüfen.

Zwischen allen API-Aufrufen liegt eine Pause von `REQUEST_DELAY_SEC` (1 s), um
die Rate Limits von NOMAD und Wikidata zu respektieren.
