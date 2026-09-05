"""konfig.wert() liest Zugangsdaten NUR aus der Umgebung; die Datei
.env.api-keys wird beim Import einmalig hineingespiegelt (echte
Umgebungsvariablen gewinnen). Alles offline.
"""
import os

import konfig


def test_wert_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("MP_API_KEY", "aus-der-umgebung")
    assert konfig.wert("MP_API_KEY") == "aus-der-umgebung"


def test_wert_ohne_eintrag_gibt_die_vorgabe(monkeypatch):
    monkeypatch.delenv("VOELLIG_UNBEKANNT_XYZ", raising=False)
    assert konfig.wert("VOELLIG_UNBEKANNT_XYZ", "vorgabe") == "vorgabe"
    assert konfig.wert("VOELLIG_UNBEKANNT_XYZ") == ""


def test_leere_umgebungsvariable_faellt_auf_die_vorgabe(monkeypatch):
    monkeypatch.setenv("MP_API_KEY", "")
    assert konfig.wert("MP_API_KEY", "vorgabe") == "vorgabe"


def test_datei_wird_in_die_umgebung_gespiegelt(tmp_path, monkeypatch):
    datei = tmp_path / ".env.api-keys"
    datei.write_text(
        '# Kommentar\nCONTACT_EMAIL = "a@b.example"\nLEER=\nMP_API_KEY=k123\n',
        encoding="utf-8")
    monkeypatch.setattr(konfig, "API_KEYS_DATEI", str(datei))
    monkeypatch.setattr(konfig, "_GESPIEGELT", False)
    for name in ("CONTACT_EMAIL", "LEER", "MP_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    konfig._in_umgebung_spiegeln()

    assert konfig.wert("CONTACT_EMAIL") == "a@b.example"   # Quotes abgestreift
    assert konfig.wert("MP_API_KEY") == "k123"
    assert konfig.wert("LEER", "x") == "x"                 # leere Zeile: nicht gesetzt


def test_echte_umgebungsvariable_gewinnt_gegen_die_datei(tmp_path, monkeypatch):
    datei = tmp_path / ".env.api-keys"
    datei.write_text("MP_API_KEY=aus-der-datei\n", encoding="utf-8")
    monkeypatch.setattr(konfig, "API_KEYS_DATEI", str(datei))
    monkeypatch.setattr(konfig, "_GESPIEGELT", False)
    monkeypatch.setenv("MP_API_KEY", "aus-der-umgebung")

    konfig._in_umgebung_spiegeln()

    assert konfig.wert("MP_API_KEY") == "aus-der-umgebung"


def test_fehlende_datei_ist_kein_fehler(tmp_path, monkeypatch):
    monkeypatch.setattr(konfig, "API_KEYS_DATEI", str(tmp_path / "gibtsnicht"))
    monkeypatch.setattr(konfig, "_GESPIEGELT", False)
    konfig._in_umgebung_spiegeln()  # darf nicht werfen


def test_nirgends_anders_als_umgebung(tmp_path, monkeypatch):
    """'nur in der Umgebung und nirgends anders': die einzige Datei ist
    .env.api-keys neben konfig.py (Repo-Wurzel), NICHT im Arbeitsverzeichnis,
    und wert() greift ausserdem auf nichts ausser os.environ zu."""
    (tmp_path / ".env").write_text("HEIMLICH=ja\n", encoding="utf-8")
    (tmp_path / ".env.api-keys").write_text("HEIMLICH=ja\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HEIMLICH", raising=False)
    monkeypatch.setattr(konfig, "_GESPIEGELT", False)

    konfig._in_umgebung_spiegeln()  # liest weiter die Repo-Datei, nicht cwd

    assert konfig.wert("HEIMLICH") == ""
    assert konfig.API_KEYS_DATEI == os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env.api-keys")
