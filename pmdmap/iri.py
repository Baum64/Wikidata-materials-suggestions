"""Erkennung der Klassen-IRIs einer Ontologie.

Fuer PMDco: https://w3id.org/pmd/co/PMD_ + 7 Ziffern (Konzept, Ausgangslage).
Das Muster kommt aus dem Profil, damit MWO nur eine neue Konfiguration ist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import OntologyProfile


@dataclass(frozen=True)
class IriScheme:
    base_iri: str
    pattern: re.Pattern

    @classmethod
    def from_profile(cls, profile: OntologyProfile) -> "IriScheme":
        return cls(profile.base_iri, re.compile(profile.iri_pattern))

    def is_class_iri(self, value: str) -> bool:
        """Genau eine Klassen-IRI - ohne Leerraum, ohne Schraegstrich am Ende,
        nur https. Alles andere ist ein Befund, keine stille Korrektur."""
        return bool(self.pattern.fullmatch(value))

    def belongs(self, value: str) -> bool:
        """Zeigt der Wert ueberhaupt in diese Ontologie (auch fehlerhaft)?"""
        v = value.strip()
        base = self.base_iri.split("://", 1)[-1]
        return v.split("://", 1)[-1].startswith(base)

    def local_id(self, value: str) -> str | None:
        """'https://w3id.org/pmd/co/PMD_0020096' -> 'PMD_0020096'."""
        if not self.is_class_iri(value):
            return None
        return value[len(self.base_iri):]

    def problem(self, value: str) -> str | None:
        """Kurzbeschreibung, warum ein Wert keine gueltige Klassen-IRI ist."""
        if self.is_class_iri(value):
            return None
        if value != value.strip():
            return "Leerraum am Anfang/Ende"
        if value.startswith("http://"):
            return "http statt https"
        if value.rstrip("/") + "/" == self.base_iri:
            return "nur Basis-IRI der Ontologie, keine Klasse"
        return "passt nicht zum Klassen-IRI-Muster"
