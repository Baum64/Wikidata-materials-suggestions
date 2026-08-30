"""lauf.py bindet drei Werkzeuge zusammen (Benchmark, materialswiki,
ClassCheck). Diese Tests halten die drei Namenslisten konsistent - sonst
verspricht 'python -m lauf <gruppe>' einen Schritt, den das dahinterliegende
Werkzeug gar nicht kennt. Alles netzwerkfrei: nur Modul-Konstanten.
"""
import importlib.util
import os

import lauf
from benchmark.benchmark import WERKSTOFFGRUPPEN as BENCH_GRUPPEN
from materialswiki.gruppen import WERKSTOFFGRUPPEN

_PFAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "Material class structure", "ClassCheck.py")
_spec = importlib.util.spec_from_file_location("classcheck_lauf", _PFAD)
classcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(classcheck)


def test_jede_gruppe_mit_group_cli_kennt_materialswiki():
    for name, info in lauf.GRUPPEN.items():
        if info["cli"][0] == "--group":
            assert info["cli"][1] in WERKSTOFFGRUPPEN, name


def test_jede_struktur_grundgesamtheit_kennt_classcheck():
    for name, info in lauf.GRUPPEN.items():
        if info.get("struktur"):
            assert info["struktur"] in classcheck.POPULATIONEN, name


def test_classcheck_populationen_liste_stimmt_mit_dem_skript():
    for name in lauf.CLASSCHECK_POPULATIONEN:
        assert name in classcheck.POPULATIONEN, name


def test_benchmark_kennt_jede_gruppen_grundgesamtheit():
    for name, info in lauf.GRUPPEN.items():
        pop = info["population"]
        if pop in ("metalle", "periodensystem"):
            continue  # --periodic-table, keine WERKSTOFFGRUPPE
        assert pop in BENCH_GRUPPEN, name


def test_neue_populationen_laufen_die_volle_kette():
    for name in ("polymer", "magnetwerkstoffe"):
        assert name in WERKSTOFFGRUPPEN
        assert name in classcheck.POPULATIONEN
        assert name in lauf.GRUPPEN
        assert lauf.GRUPPEN[name]["struktur"] == name


def test_magnetwerkstoffe_filtern_die_isotope_aus():
    """Ohne den Ordnungszahl-Filter zieht Q949573 ueber einen schiefen
    Instanzpfad (Nickel) rund 40 Nickel-Isotope herein."""
    assert "P1086" in WERKSTOFFGRUPPEN["magnetwerkstoffe"]["pattern"]
