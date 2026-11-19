"""IRI-Erkennung - netzfrei."""
from dataclasses import replace
from pathlib import Path

import pytest

from pmdmap.config import load_config
from pmdmap.iri import IriScheme

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


@pytest.fixture(scope="module")
def pmd():
    return IriScheme.from_profile(load_config(CONFIG).profile)


@pytest.mark.parametrize("iri", [
    "https://w3id.org/pmd/co/PMD_0020096",   # steel
    "https://w3id.org/pmd/co/PMD_0000000",
    "https://w3id.org/pmd/co/PMD_9999999",
])
def test_gueltige_klassen_iri(pmd, iri):
    assert pmd.is_class_iri(iri)
    assert pmd.local_id(iri) == iri.rsplit("/", 1)[-1]
    assert pmd.problem(iri) is None


@pytest.mark.parametrize("iri, grund", [
    ("http://w3id.org/pmd/co/PMD_0020096", "http statt https"),
    ("https://w3id.org/pmd/co/PMD_0020096 ", "Leerraum"),
    (" https://w3id.org/pmd/co/PMD_0020096", "Leerraum"),
    ("https://w3id.org/pmd/co/", "Basis-IRI"),
    ("https://w3id.org/pmd/co", "Basis-IRI"),
    ("https://w3id.org/pmd/co/PMD_002009", "Muster"),       # 6 Ziffern
    ("https://w3id.org/pmd/co/PMD_00200960", "Muster"),     # 8 Ziffern
    ("https://w3id.org/pmd/co/PMD_0020096/", "Muster"),
    ("https://w3id.org/pmd/co/pmd_0020096", "Muster"),
    ("https://w3id.org/pmd/co/Steel", "Muster"),             # PMDco 2.x-Stil
    ("https://w3id.org/pmd/ao/PMD_0020096", "Muster"),       # anderes Modul
])
def test_ungueltige_iri_mit_grund(pmd, iri, grund):
    assert not pmd.is_class_iri(iri)
    assert pmd.local_id(iri) is None
    assert grund in pmd.problem(iri)


def test_belongs_erkennt_auch_fehlerhafte_links(pmd):
    assert pmd.belongs("http://w3id.org/pmd/co/PMD_0020096")
    assert pmd.belongs("https://w3id.org/pmd/co/")
    assert not pmd.belongs("http://purl.obolibrary.org/obo/BFO_0000040")


def test_zweite_ontologie_nur_konfiguration():
    """MWO braucht keinen Code, nur ein Profil mit eigenem Muster."""
    prof = replace(
        load_config(CONFIG).profile,
        key="mwo",
        base_iri="https://purls.helmholtz-metadaten.de/mwo/",
        iri_pattern=r"^https://purls\.helmholtz-metadaten\.de/mwo/\d{7}$",
    )
    mwo = IriScheme.from_profile(prof)
    assert mwo.is_class_iri("https://purls.helmholtz-metadaten.de/mwo/0001109")
    assert not mwo.is_class_iri("https://w3id.org/pmd/co/PMD_0020096")
