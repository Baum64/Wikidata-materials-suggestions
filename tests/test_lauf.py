"""lauf.py fuehrt einen Dialog und ruft dahinter vier Werkzeuge auf
(Benchmark, materialswiki, ClassCheck, Anwendung). Diese Tests halten die
POPULATIONEN-Tabelle mit den Grundgesamtheiten dieser vier Werkzeuge
konsistent - sonst bietet der Dialog einen Schritt an, den das Werkzeug
dahinter gar nicht kennt. Alles netzwerkfrei: nur Modul-Konstanten und die
reine Dialoglogik.
"""
import importlib.util
import os

import pytest

import lauf
from benchmark.benchmark import WERKSTOFFGRUPPEN as BENCH_GRUPPEN
from materialswiki.gruppen import WERKSTOFFGRUPPEN as MW_GRUPPEN


def _lade(pfad_teile):
    pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        *pfad_teile)
    spec = importlib.util.spec_from_file_location("_geladen_" + pfad_teile[-1], pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


classcheck = _lade(["Material class structure", "ClassCheck.py"])
anwendung = _lade(["Anwendung", "Anwendung.py"])

BENCH_CHOICES = set(BENCH_GRUPPEN) | {"subtree", "metalle", "periodensystem"}


# ---------------------------------------------------------------------------
# Jede angebotene Grundgesamtheit kennt das Werkzeug dahinter
# ---------------------------------------------------------------------------

def _mit_schritt(stufe):
    return [(name, info) for name, info in lauf.POPULATIONEN.items()
            if stufe in info["schritte"]]


def test_benchmark_populationen_sind_gueltig():
    for name, info in _mit_schritt("benchmark"):
        assert info["schritte"]["benchmark"]["population"] in BENCH_CHOICES, name


def test_vorschlags_gruppen_kennt_materialswiki():
    for name, info in _mit_schritt("vorschlaege"):
        cli = info["schritte"]["vorschlaege"]["cli"]
        if cli[0] == "--group":
            assert cli[1] in MW_GRUPPEN, name
        else:
            assert cli[0] == "--periodic-table", name
            assert cli[1] in ("--nur-metalle", "--no-nur-metalle"), name


def test_struktur_populationen_kennt_classcheck():
    for name, info in _mit_schritt("struktur"):
        assert info["schritte"]["struktur"]["population"] in classcheck.POPULATIONEN, name


def test_anwendungs_populationen_kennt_anwendung():
    for name, info in _mit_schritt("anwendungen"):
        assert info["schritte"]["anwendungen"]["population"] in anwendung.POPULATIONEN, name


def test_jede_population_hat_mindestens_einen_schritt():
    for name, info in lauf.POPULATIONEN.items():
        assert info["schritte"], name


def test_zaehl_schluessel_ist_aufloesbar():
    """'gruppe' geht ueber gruppen_qids, alles andere braucht ein SPARQL-Muster."""
    erlaubt = {"gruppe"} | set(lauf._zaehl_sparql_muster())
    for name, info in lauf.POPULATIONEN.items():
        assert info["zaehl"] in erlaubt, name


# ---------------------------------------------------------------------------
# Die vollstaendige Kette und die grossen Wurzeln
# ---------------------------------------------------------------------------

def test_populationen_mit_voller_kette():
    for name in ("minerale", "carbide", "oxide", "polymer", "magnetwerkstoffe",
                 "keramik", "glas"):
        schritte = lauf.POPULATIONEN[name]["schritte"]
        assert set(schritte) == {"benchmark", "vorschlaege", "struktur"}
        assert schritte["struktur"]["population"] == name


def test_minerale_und_carbide_haben_die_struktur_option():
    for name in ("minerale", "carbide"):
        assert "struktur" in lauf.POPULATIONEN[name]["schritte"]


def test_entfernte_populationen_sind_weg():
    for name in ("benannte-legierungen", "material", "metallischer-werkstoff",
                 "metalle"):
        assert name not in lauf.POPULATIONEN


def test_jede_population_kennt_benchmark_vorschlaege_struktur():
    """Nach dem Wegfall von 'metalle' hat jede Population die volle Kette;
    'anwendungen' ist der einzige optionale Schritt."""
    for name, info in lauf.POPULATIONEN.items():
        assert {"benchmark", "vorschlaege", "struktur"} <= set(info["schritte"]), name


def test_anwendungen_nur_fuer_legierungen():
    for name, info in lauf.POPULATIONEN.items():
        if "anwendungen" in info["schritte"]:
            assert name == "legierungen"


def test_struktur_laeuft_ungebremst():
    """Die Batchgroesse betrifft nur den Vorschlagslauf - ClassCheck sieht
    immer die volle Grundgesamtheit."""
    for name in ("keramik", "minerale"):
        befehl, _ = lauf.schritt_befehl("struktur", name, "2026-01-01_0000", 500)
        assert "--limit" not in befehl


def test_periodensystem_vorschlaege_ohne_batch():
    """Der Periodensystem-Modus kennt kein --batch-size."""
    befehl, _ = lauf.schritt_befehl("vorschlaege", "periodensystem",
                                    "2026-01-01_0000", 500)
    assert "--batch-size" not in befehl
    assert "--periodic-table" in befehl


def test_gruppen_vorschlaege_mit_batch():
    befehl, _ = lauf.schritt_befehl("vorschlaege", "minerale",
                                    "2026-01-01_0000", 300)
    assert befehl[befehl.index("--batch-size") + 1] == "300"


# ---------------------------------------------------------------------------
# Ausgabedateien
# ---------------------------------------------------------------------------

def test_ausgabenamen_tragen_das_qs_schema():
    befehl, log = lauf.struktur_befehl("legierungen", "/tmp/x", "2026-01-01_0000")
    out = befehl[befehl.index("--out") + 1]
    befund_md = befehl[befehl.index("--md") + 1]
    assert os.path.basename(out) == "qs_class_legierungen_2026-01-01_0000.txt"
    assert os.path.basename(befund_md) == "qs_class_befunde_legierungen_2026-01-01_0000.md"
    assert os.path.basename(log) == "qs_class_legierungen_2026-01-01_0000.log"


def test_benchmark_und_vorschlaege_teilen_den_zeitstempel():
    b, _ = lauf.schritt_befehl("benchmark", "oxide", "2026-02-02_1200", None)
    v, _ = lauf.schritt_befehl("vorschlaege", "oxide", "2026-02-02_1200", None)
    assert b[b.index("--md") + 1].endswith("abdeckung_oxide_2026-02-02_1200.md")
    assert v[v.index("--out") + 1].endswith("vorschlaege_oxide_2026-02-02_1200.md")


# ---------------------------------------------------------------------------
# Die reine Dialoglogik
# ---------------------------------------------------------------------------

def test_frage_groesse_erzwingt_mindestens_100(monkeypatch):
    eingaben = iter(["50", "abc", "150"])
    monkeypatch.setattr("builtins.input", lambda _: next(eingaben))
    assert lauf.frage_groesse(5000) == 150


def test_frage_groesse_enter_nimmt_die_vorgabe(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert lauf.frage_groesse(5000, vorgabe=500) == 500


def test_frage_umfang_nur_verfuegbare_schritte(monkeypatch):
    # minerale kennt nur benchmark + vorschlaege -> keine 3
    monkeypatch.setattr("builtins.input", lambda _: "1 2")
    assert lauf.frage_umfang("minerale") == ["benchmark", "vorschlaege"]


def test_frage_umfang_mehrfachauswahl_haelt_die_reihenfolge(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "3,1")
    assert lauf.frage_umfang("legierungen") == ["benchmark", "struktur"]


def test_frage_umfang_alle(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "a")
    assert lauf.frage_umfang("legierungen") == [
        "benchmark", "vorschlaege", "struktur", "anwendungen"]


def test_frage_population_nimmt_nummer_und_name(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "minerale")
    assert lauf.frage_population() == "minerale"
    namen = list(lauf.POPULATIONEN)
    monkeypatch.setattr("builtins.input", lambda _: "1")
    assert lauf.frage_population() == namen[0]


def test_main_lehnt_argumente_ab(capsys):
    assert lauf.main(["legierungen"]) == 2


def test_unterbrochene_laeufe_liest_die_fortschrittsdatei(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(lauf, "PROPOSALS_DIR", str(tmp_path))
    (tmp_path / "qs_minerale_2026-03-03_0900.fortschritt.json").write_text(
        json.dumps({"gruppe": "minerale", "erledigt": 500, "gesamt": 6301,
                    "batch_size": 500, "letzte_charge": 1,
                    "zeitpunkt": "2026-03-03T09:00:00"}), encoding="utf-8")
    (tmp_path / "qs_oxide_2026-03-03_1000.fortschritt.json").write_text(
        json.dumps({"gruppe": "oxide", "erledigt": 154, "gesamt": 154}),
        encoding="utf-8")

    offen = lauf.unterbrochene_laeufe()
    assert len(offen) == 1
    assert offen[0]["gruppe"] == "minerale"
    assert offen[0]["stempel"] == "2026-03-03_0900"
