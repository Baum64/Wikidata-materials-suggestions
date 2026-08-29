"""Die Quellenspalte des Benchmarks: was ein Lauf wirklich abfragt.

Der Benchmark markiert je Property, aus welcher Quelle materialswiki den
Wert holen koennte. Diese Markierung ist nur so viel wert, wie sie zum
tatsaechlichen Lauf passt - deshalb hier die drei Stellen, an denen sie
frueher zu grosszuegig war. Alles netzwerkfrei.
"""
import pytest

from benchmark.benchmark import (
    WP_SCHLUESSEL, lauf_modus, quellen_je_property, stufen_des_laufs,
    stufen_pids,
)
from materialswiki.cli import STUFEN_PIDS


def test_die_infoboxen_ergeben_zusammen_die_wikipedia_stufe():
    """Kaeme in materialswiki ein Feld dazu, ohne hier einer Vorlage
    zugeordnet zu werden, verschwaende es lautlos aus der Quellenspalte."""
    vereinigung = set().union(*(stufen_pids(k) for k in WP_SCHLUESSEL))
    assert vereinigung == set(STUFEN_PIDS["wikipedia"])


@pytest.mark.parametrize("population, modus", [
    ("minerale", "gruppe"),
    ("legierungen", "gruppe"),
    ("subtree", "gruppe"),
    ("metalle", "elemente"),
    ("periodensystem", "elemente"),
])
def test_population_kennt_ihren_lauf(population, modus):
    assert lauf_modus(population) == modus


def test_elementlauf_hat_keine_ableitungen():
    """build_periodic_table_proposals ruft weder die Punktgruppen- noch die
    Formelstufe auf - P589 haengt dort allein an COD."""
    stufen = stufen_des_laufs("periodensystem")
    assert "punktgruppe" not in stufen and "formel" not in stufen
    assert quellen_je_property("periodensystem")["P589"] == ["COD"]
    assert quellen_je_property("minerale")["P589"] == ["COD", "WD"]


def test_formelstufe_wird_eingeklammert():
    """--formel ist per Default aus; P527 und P2670 kommen ohne den Schalter
    in keinem Lauf vor."""
    assert quellen_je_property("minerale")["P527"] == ["(Formel)"]


def test_mineralinfobox_liefert_nur_dichte_und_mohshaerte():
    """Gemessen am Lauf vom 2026-08-28 (650 Minerale): aus der deutschen
    Wikipedia kamen genau P2054 und P1088 - die uebrigen Feldnamen stehen in
    der Element- bzw. Chemikalieninfobox, nicht in {{Infobox Mineral}}."""
    quellen = quellen_je_property("minerale")
    aus_wikipedia = {pid for pid, q in quellen.items()
                     if any(k.startswith("WP") for k in q)}
    assert aus_wikipedia == {"P2054", "P1088"}
    # Waermeleitfaehigkeit und CAS-Nummer stehen dort NICHT.
    assert "P2068" not in quellen and "P231" not in quellen


def test_legierungen_bekommen_chemikalieninfobox_und_chembox():
    """Gemessen am Lauf vom 2026-08-28: Dichte, CAS, Schmelz- und Siedepunkt
    aus beiden Wikipedias."""
    quellen = quellen_je_property("legierungen")
    assert quellen["P231"] == ["WPde-Chem", "WPen-Chem"]
    assert quellen["P2101"] == ["WPde-Chem", "WPen-Chem"]


def test_laengenausdehnung_nur_im_elementlauf():
    """P5672 haengt allein an der englischen Elementvorlage, und die wird
    nur im Periodensystem-Modus geholt."""
    assert quellen_je_property("periodensystem")["P5672"] == ["WPen-El"]
    assert "P5672" not in quellen_je_property("minerale")


def test_property_map_deckt_die_projektseite_ab():
    """PROPERTY_MAP kennt jede Property aus dem Snapshot.

    Eintragen heisst nicht liefern - die meisten dieser Properties bedient
    keine Stufe. Der Test haelt nur fest, dass die Tabelle die Projektseite
    vollstaendig abbildet; faellt er nach einem neuen Snapshot, ist der neue
    Eintrag nachzutragen (Datentyp und Einheit von wikidata.org, nicht
    geraten).
    """
    import json
    import os

    from materialswiki.cli import PROPERTY_MAP

    pfad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "benchmark", "properties_snapshot.json")
    with open(pfad, encoding="utf-8") as f:
        snapshot = json.load(f)

    aus_snapshot = {pid for pids in snapshot.values() for pid in pids}
    bekannt = {info["pid"] for info in PROPERTY_MAP.values()}
    assert aus_snapshot <= bekannt, sorted(aus_snapshot - bekannt)


def test_jede_property_taucht_nur_einmal_auf():
    """Zwei Schluessel auf dieselbe PID waeren eine stille Doppelpflege."""
    from materialswiki.cli import PROPERTY_MAP

    pids = [info["pid"] for info in PROPERTY_MAP.values()]
    assert len(pids) == len(set(pids))
