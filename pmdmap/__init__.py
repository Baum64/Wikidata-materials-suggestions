"""pmdmap - Abgleich einer BFO-basierten Werkstoffontologie (zuerst PMDco) mit Wikidata.

Das Paket schreibt NIE in Wikidata. Es liest Ontologie und Wikidata, erzeugt
eine Pruef-Tabelle fuer Menschen und (spaeter) aus deren Entscheidungen
QuickStatements-Dateien unter proposals/pmdmap/.

Module:
    config      config.yaml lesen, Ontologie-Profile
    http        einziger Netzzugang: User-Agent, Drosselung, Retry bei 429/5xx
    cache       Datei-Cache fuer Ontologie und API-Antworten
    iri         Erkennung der Klassen-IRIs je Profil
    ontology    Ontologie laden (rdflib) und indizieren
    wikidata    SPARQL- und Action-API-Abfragen
    inventory   Paket 0: Bestand der vorhandenen Links erheben
    assessment  Paket 0: Regeln fuer den Vorschlag je Link
    review      Pruef-Tabelle schreiben/lesen
    report      Bestandsbericht und Eintraege fuer review-needed.md
    cli         Unterbefehle fetch | review | export
"""

__version__ = "0.1.0"
