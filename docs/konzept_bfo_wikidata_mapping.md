# Konzept: BFO-basierte Werkstoffontologien (MWO/PMDco) mit Wikidata verbinden

Stand: 19.11.2026 · Entwurf zur Diskussion im WikiProject Materials

## Ausgangslage

- Die NFDI-MatWerk-Ontologie (MWO) und die PMD-Kernontologie (PMDco) folgen der Basic Formal Ontology (BFO): strenge Trennung von Material (Ding), Qualität (Eigenschaft), Prozess und Rolle.
- Wikidata folgt keiner externen Oberontologie. Grundlage sind die Community-Konventionen (Help:Basic membership properties, WikiProject Materials).
- Korrektur 19.11.2026: Die erste Prüfabfrage suchte nach falschen Textmustern. Laut Special:LinkSearch gibt es **117 Links auf `w3id.org/pmd/`**, z. B. Riss (Q3073047), Pore (Q29702744), Zwischengitterplatz (Q3485440), Avogadro-Zahl (Q69189081), Rezept (Q219239). Bisher vor allem Defekte, Größen und Prozessbegriffe, kaum Werkstoffklassen.
- Bestand laut Variante A (19.11.2026): 105 Einträge mit PMD-Link, davon rund 24 Werkstoffe/Stoffklassen (u. a. Material, Metalle, Legierung, legierter Stahl, Kohlenstoffstahl, Aluminiumlegierung, Keramik, Borosilikatglas, Biopolymer, Mineral, Silicium). Der Rest: Eigenschaften, Gefügedefekte, Prozesse, Größen, Geräte, Rollen/Fähigkeiten.
- Lücken bei zentralen Werkstoffen: Stahl, Gusseisen, Kupferlegierung, Polymer/Kunststoff, Glas (allgemein), Verbundwerkstoff, Holz, Beton.
- Bestand laut Variante A2: 102 Abbildungen, **101 über P1709**, 1 über P2888 (Avogadro-Zahl), **keine einzige mit P4390**. Alle bestehenden Links behaupten damit volle Bedeutungsgleichheit – das muss pro Eintrag geprüft werden.
- Prüfbedarf: Rezept (Q219239, dt. Label „Kochrezept“) gegen PMD „recipe“ prüfen: Die PMD-Definition umfasst Kochen, Fertigung und Chemie. Ist der Wikidata-Eintrag ebenso allgemein → P1709 bleibt; ist er auf Küche beschränkt → P2888 mit P4390 = broad match. Außerdem wurden 2025 neue Einträge für BFO/PMD-Klassen angelegt (z. B. „sample role“, „capability to heat“, „quality of substance or disposition“) – prüfen, ob sie in P279-Ketten von Werkstoff-Einträgen hängen (Konflikt mit E1).
- Die PMD-Kernontologie hat einen eigenen Wikidata-Eintrag: **Q141572184** – als Quellenangabe (P248) für Abbildungen verwenden.
- PMDco-Klassen-IRIs haben das Muster `https://w3id.org/pmd/co/PMD_` + 7 Ziffern → Grundlage für eine eigene Kennungs-Eigenschaft (`^PMD_\d{7}$`).

## Grundsatzentscheidungen (E1–E4 bestätigt am 19.11.2026)

**E1 – Abbilden statt nachbauen.** Die BFO-Hierarchie wird nicht in Wikidata übernommen. Keine BFO-Klassen (z. B. „material entity“, „quality“) als Oberklassen in P279-Ketten. Die Verbindung entsteht ausschließlich über Abbildungs-Aussagen.

**E2 – Nur Werkstoffe und Stoffklassen werden abgebildet.** Abgebildet werden Einträge, die eine Art von Material oder eine Stoffklasse bezeichnen (Stahl, Aluminiumlegierung, Polyethylen, Keramik). Einzelne Proben oder Chargen werden nicht in Wikidata angelegt und bleiben im Fach-Wissensgraphen.

**E3 – Abbildungsart immer angeben.** Jede Verknüpfung bekommt den Qualifier „mapping relation type“ (P4390) mit einem SKOS-Wert (exakt, eng, weiter, enger, verwandt). Ohne Angabe gilt eine Verknüpfung als unvollständig.

Warum: Wikidata und die Ontologie schneiden Begriffe oft unterschiedlich. Der Qualifier sagt, *wie gut* zwei Begriffe zusammenpassen:

| Wert (SKOS) | Bedeutung | Beispiel |
|---|---|---|
| exact match | gleicher Begriff, austauschbar | Wikidata „Stahl“ ↔ Ontologie „Steel“ mit gleicher Definition |
| close match | fast gleich, kleine Abweichungen in der Definition | Wikidata „Gusseisen“ ↔ Ontologie „Cast iron“, die Gusseisen-Sorten anders einschließt |
| broad match | die Ontologieklasse ist **weiter** als der Wikidata-Eintrag | Wikidata „Edelstahl“ → Ontologie nur „Steel“ |
| narrow match | die Ontologieklasse ist **enger** als der Wikidata-Eintrag | Wikidata „Metall“ → Ontologie „Metallic material“ in einer engeren Fassung |
| related match | verwandt, aber keine Ober-/Unterbeziehung | Wikidata „Härten“ (Prozess) ↔ Ontologie „Hardness“ (Qualität) |

So bleibt sichtbar, wo Wikidata und Ontologie nicht deckungsgleich sind, ohne dass jemand die Wikidata-Struktur „passend machen“ muss.

**E4 – Bedeutungsgleichheit nur bei echter Deckung.** „Äquivalente Klasse“ (P1709) nur, wenn Definition und Umfang übereinstimmen. Sonst P2888 („exakte Übereinstimmung“ bzw. URL-Abbildung) mit passender P4390-Abstufung.

**Präzisierung von E3/E4 nach Bestandsaufnahme (19.11.2026):** P1709 bedeutet bereits „exakt gleich“ und braucht daher keinen P4390-Qualifier. P4390 ist Pflicht nur bei P2888, also bei allen nicht-exakten Abbildungen.

**E5 – Referenzontologie.** Zunächst wird gegen **PMDco** abgebildet. MWO bleibt als spätere Option offen; die Regeln gelten dann sinngemäß.

**E7 – Physikalische Eigenschaften.** Eine Eigenschaft existiert in Wikidata oft doppelt: als **Begriffs-Eintrag** (z. B. Dichte, Kompressionsmodul, Härte) und teils als **Wikidata-Eigenschaft**, mit der Werte an Werkstoffen angegeben werden (z. B. Dichte P2054). PMD-Qualitätsklassen werden immer am **Begriffs-Eintrag** abgebildet (P1709 bzw. P2888 + P4390). Gibt es zusätzlich eine passende Wikidata-Eigenschaft, bekommt diese „äquivalente Eigenschaft“ (P1628). Für Eigenschaften ohne einfachen Zahlenwert (z. B. Härte mit verschiedenen Skalen) reicht der Begriffs-Eintrag.

**E6 – Normbezeichnungen.** Werkstoffnormen (z. B. Werkstoffnummer 1.4301, EN-Kurznamen) werden zunächst nur auf Klassenebene abgebildet, keine eigenen Einträge je Sorte.

## Zuordnung der BFO-Kategorien zu Wikidata-Mustern

| BFO-Kategorie | Beispiel | Modellierung in Wikidata | Abbildung |
|---|---|---|---|
| Material (material entity, als Klasse) | Stahl | Eintrag mit P279 (Unterklasse von) zur Oberklasse | Eintrag ↔ Ontologieklasse über P1709/P2888 + P4390 |
| Qualität | Dichte, Härte, Schmelzpunkt | Aussage mit Wert und Einheit am Werkstoff-Eintrag (z. B. Dichte P2054) | Wikidata-Eigenschaft ↔ Ontologieklasse über „äquivalente Eigenschaft“ (P1628) |
| Prozess | Wärmebehandlung, Gießen | eigener Eintrag für den Prozesstyp | Eintrag ↔ Ontologieklasse; Verbindung zum Werkstoff, wo sinnvoll, über eine Herstellungs-Eigenschaft |
| Rolle/Funktion | Baustoff, Schmiermittel | **nicht** als Oberklasse (P279), sondern als Verwendung (P366) | Rollen-Klasse ↔ Eintrag für die Verwendung |

Die Regel in der letzten Zeile deckt sich mit Help:Basic membership properties: Rollen gehören nicht in die Klassenhierarchie. Das ist der wichtigste gemeinsame Nenner zwischen BFO und den Wikidata-Konventionen und sollte in der Guideline ausdrücklich stehen.

## Mittelfristig: eigene Kennungs-Eigenschaften

Statt allgemeiner URL-Abbildungen eigene External-ID-Eigenschaften vorschlagen:

- **MWO-ID** – lokales Format laut Bioregistry: 7 Ziffern (`^\d{7}$`), z. B. `0001109`
- **PMDco-ID** – Format `PMD_` + 7 Ziffern, z. B. `PMD_0020202` (Riss)

Vorteile: Formatprüfung über Constraints, Abgleich per Mix'n'match, einfache Abfragen.

## Vorgehen

0. **Bestand prüfen:** Die 101 P1709-Links einzeln durchgehen. Echte Deckung → bleibt P1709. Keine volle Deckung → umstellen auf P2888 mit P4390 (Verdachtsfälle: Metalle, Silicium, Größe; Rezept auf Umfang prüfen).

1. **Pilot:** 20 zentrale Werkstoffklassen (z. B. Stahl, Gusseisen, Aluminiumlegierung, Kupferlegierung, Polymer, Keramik, Glas, Holz, Beton, Verbundwerkstoff) manuell abbilden, jeweils mit P4390 und Quellenangabe auf den Wikidata-Eintrag der Ontologie.
2. **Prüfen:** Gibt es für jede Ontologieklasse genau einen passenden Wikidata-Eintrag? Wo nicht, festhalten, ob Wikidata feiner, gröber oder anders schneidet.
3. **Abstimmen:** Ergebnisse auf der Diskussionsseite von WikiProject Materials vorstellen, außerdem Kontakt mit dem MatWerk-Team (FIZ Karlsruhe).
4. **Eigenschaftsvorschläge** für MWO- und PMDco-ID einreichen.
5. **Skalieren** per Skript und QuickStatements, analog zum Identifier-Abgleich.

## Offene Fragen

- Wie stabil sind die IRIs beider Ontologien zwischen Versionen?

## Kontrollabfragen

Die erste Fassung durchsuchte alle P1709/P2888-Aussagen in Wikidata (mehrere Millionen) per Textfilter und lief in einen Timeout. Daher zwei schlanke Varianten.

**A – über die Link-Suche von MediaWiki (schnell, findet alle Einträge mit Links auf die Ontologie-Domains):**

```sparql
SELECT ?item ?itemLabel WHERE {
  VALUES ?domain { "w3id.org/pmd/" "purls.helmholtz-metadaten.de/mwo/" "materialdigital.github.io" }
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "Generator" ;
                    wikibase:endpoint "www.wikidata.org" ;
                    mwapi:generator "exturlusage" ;
                    mwapi:geuquery ?domain ;
                    mwapi:geunamespace "0" ;
                    mwapi:geulimit "max" .
    ?item wikibase:apiOutputItem mwapi:title .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
}
```

**A2 – Bestandsaufnahme der vorhandenen PMD-Links: welche Eigenschaft, welche Abbildungsart?**

```sparql
SELECT ?item ?itemLabel ?prop ?uri ?artLabel WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:api "Generator" ;
                    wikibase:endpoint "www.wikidata.org" ;
                    mwapi:generator "exturlusage" ;
                    mwapi:geuquery "w3id.org/pmd/" ;
                    mwapi:geuprotocol "https" ;
                    mwapi:geunamespace "0|120" ;
                    mwapi:geulimit "max" .
    ?item wikibase:apiOutputItem mwapi:title .
  }
  VALUES (?p ?ps ?prop) { (p:P1709 ps:P1709 "P1709") (p:P2888 ps:P2888 "P2888") (p:P1628 ps:P1628 "P1628") }
  ?item ?p ?st . ?st ?ps ?uri .
  FILTER(CONTAINS(STR(?uri), "w3id.org/pmd/"))
  OPTIONAL { ?st pq:P4390 ?art . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
}
ORDER BY ?prop ?itemLabel
```

**B – nur für die Pilot-Werkstoffe, mit Abbildungsart (QIDs der Pilotliste eintragen):**

```sparql
SELECT ?item ?itemLabel ?prop ?uri ?artLabel WHERE {
  VALUES ?item { wd:Q11427 wd:Q663 }   # Beispiele: Stahl, Aluminium – durch Pilotliste ersetzen
  VALUES (?p ?ps ?prop) { (p:P1709 ps:P1709 "P1709") (p:P2888 ps:P2888 "P2888") }
  ?item ?p ?st . ?st ?ps ?uri .
  OPTIONAL { ?st pq:P4390 ?art . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
}
```

Die IRI-Präfixe (`w3id.org/pmd/…` für PMDco, `purls.helmholtz-metadaten.de/mwo/…` für MWO) vor dem Einsatz an einer echten Klassen-IRI prüfen.
