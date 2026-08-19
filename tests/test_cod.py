"""COD-Anbindung: Hill-Notation, Eintragswahl, Belege - netzwerkfrei."""
import pytest

from materialswiki.cli import (
    MP_DATASET_DOI,
    MP_DATASET_WERK,
    MP_DOI,
    Reference,
    _sg_besser,
    cod_best_entry,
    cod_dominante_raumgruppe,
    cod_hill_formula,
    cod_proposals_for_item,
    kristallsystem_aus_nummer,
    # Beim Import gesichert: conftest ersetzt das Modulattribut, nicht
    # diese Referenz. Nur so laesst sich die Funktion selbst pruefen.
    siedepunkt_kelvin as echter_siedepunkt,
    proposals_for_material,
)


# ---------------------------------------------------------------------------
# Hill-Notation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formel, erwartet", [
    ("Fe2O3", "Fe2 O3"),
    ("Al2O3", "Al2 O3"),
    # Der Knackpunkt: COD sortiert alphabetisch, nicht wie die Formel
    # geschrieben wird. "Ti O2" liefert null Treffer, "O2 Ti" 39.
    ("TiO2", "O2 Ti"),
    ("H2O", "H2 O"),
    ("Cu", "Cu"),
    # Mit Kohlenstoff: erst C, dann H, dann der Rest alphabetisch.
    ("CH4", "C H4"),
    ("C8H10N4O2", "C8 H10 N4 O2"),
])
def test_hill_notation(formel, erwartet):
    assert cod_hill_formula(formel) == erwartet


def test_hill_notation_gibt_bei_unlesbarer_formel_none():
    """Lieber gar nicht suchen als mit einer geratenen Formel."""
    assert cod_hill_formula("CuSO4·5H2O") is None
    assert cod_hill_formula("") is None


# ---------------------------------------------------------------------------
# Auswahl des Eintrags
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entries, erwartet, regel", [
    # Nur mit DOI laesst sich die Originalarbeit als Beleg setzen - das ist
    # der ganze Grund, COD dem Materials Project vorzuziehen.
    ([{"file": "1", "year": "2020", "doi": None},
      {"file": "2", "year": "1990", "doi": "10.1/x"}],
     "2", "DOI schlaegt kein-DOI, auch gegen das juengere Jahr"),
    ([{"file": "1", "year": "1990", "doi": "10.1/a"},
      {"file": "2", "year": "2020", "doi": "10.1/b"}],
     "2", "bei gleichem Beleg gewinnt das juengere Jahr"),
    ([{"file": "1", "year": "2020", "doi": "10.1/a", "duplicateof": "999"},
      {"file": "2", "year": "2019", "doi": "10.1/b", "status": "retracted"},
      {"file": "3", "year": "1990", "doi": "10.1/c"}],
     "3", "Duplikate und zurueckgezogene Eintraege fliegen raus"),
])
def test_eintragswahl(entries, erwartet, regel):
    assert cod_best_entry(entries)["file"] == erwartet, regel


def test_bei_voelligem_gleichstand_entscheidet_die_kleinere_cod_id():
    """Sonst haengt die Wahl an der Antwortreihenfolge der API und zwei
    Laeufe schlagen verschiedene Strukturen fuer denselben Stoff vor."""
    a = {"file": "4105681", "year": "2011", "doi": "10.1/a"}
    b = {"file": "4105040", "year": "2011", "doi": "10.1/b"}
    assert cod_best_entry([a, b])["file"] == "4105040"
    assert cod_best_entry([b, a])["file"] == "4105040"


def test_ohne_brauchbaren_eintrag_kommt_none():
    assert cod_best_entry([]) is None
    assert cod_best_entry([{"file": "1", "duplicateof": "9"}]) is None


# ---------------------------------------------------------------------------
# Raumgruppen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nummer, erwartet", [
    (1, "triclinic"), (2, "triclinic"), (3, "monoclinic"), (15, "monoclinic"),
    (16, "orthorhombic"), (74, "orthorhombic"), (75, "tetragonal"),
    (142, "tetragonal"), (143, "trigonal"), (167, "trigonal"),
    (168, "hexagonal"), (194, "hexagonal"), (195, "cubic"), (230, "cubic"),
    (0, None), (231, None),   # ausserhalb der 230 Raumgruppen
])
def test_kristallsystem_aus_raumgruppennummer(nummer, erwartet):
    """Bereiche aus den International Tables - normativ, nicht geraten."""
    assert kristallsystem_aus_nummer(nummer) == erwartet


def test_raumgruppen_dubletten_werden_deterministisch_aufgeloest():
    """Sechs Raumgruppennummern haben mehr als ein Wikidata-Item. Item MIT
    Kristallsystem gewinnt, bei Gleichstand die kleinere Q-Nummer."""
    mit = {"qid": "Q99", "cs_qid": "Q473227"}
    ohne = {"qid": "Q10", "cs_qid": ""}
    assert _sg_besser(mit, ohne) is True
    assert _sg_besser(ohne, mit) is False

    alt = {"qid": "Q15040793", "cs_qid": "Q588274"}
    neu = {"qid": "Q56235829", "cs_qid": "Q588274"}
    assert _sg_besser(neu, alt) is False
    assert _sg_besser(alt, neu) is True


# ---------------------------------------------------------------------------
# Vorschlagszeilen aus einem COD-Eintrag
# ---------------------------------------------------------------------------

EINTRAG_KUPFER = {
    "file": "4105040",
    "formula": "- Cu -",
    "sg": "F m -3 m",
    "sgNumber": "225",
    "doi": "10.1021/ja9052569",
    "journal": "Journal of the American Chemical Society",
    "year": "2009",
    "method": "powder diffraction",
    "celltemp": "180",
}

RAUMGRUPPEN = {
    225: {"qid": "Q15041891", "label": "Raumgruppe 225",
          "cs_qid": "Q473227", "cs_label": "Kubisches Kristallsystem",
          "pg_qid": "Q13359931", "pg_label": "kubisch-hexakisoktaedrisch"},
}


@pytest.fixture
def cod_zeilen(monkeypatch):
    from materialswiki import cli
    monkeypatch.setattr(cli, "fetch_space_group_qids", lambda: RAUMGRUPPEN)
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    wd = {"qid": "Q753", "label": "Kupfer"}
    return cod_proposals_for_item(wd, [EINTRAG_KUPFER])


def test_cod_liefert_cod_id_raumgruppe_punktgruppe_und_kristallsystem(cod_zeilen):
    pids = [z["_pid"] for z in cod_zeilen]
    assert pids == ["P9824", "P690", "P589", "P556"]
    assert all(z["source"] == "COD" for z in cod_zeilen)


def test_punktgruppe_wird_am_raumgruppen_item_abgelesen(cod_zeilen):
    """Jede der 230 Raumgruppen gehoert zu genau einer der 32 Punktgruppen,
    und Wikidata weiss das am Raumgruppen-Item bereits. Belegt wird sie
    deshalb mit derselben Originalarbeit wie die Raumgruppe."""
    punktgruppe = [z for z in cod_zeilen if z["_pid"] == "P589"][0]
    assert punktgruppe["value"] == "Q13359931"
    assert punktgruppe["ref_doi"] == "10.1021/ja9052569"


def test_ohne_punktgruppe_am_raumgruppen_item_wird_nichts_behauptet(monkeypatch):
    """Sechs der 236 Raumgruppen-Items fuehren keine Punktgruppe. Dann faellt
    die Zeile weg - geraten wird nicht."""
    from materialswiki import cli
    monkeypatch.setattr(cli, "fetch_space_group_qids", lambda: {
        225: {"qid": "Q15041891", "label": "Raumgruppe 225",
              "cs_qid": "Q473227", "cs_label": "kubisch",
              "pg_qid": "", "pg_label": ""},
    })
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    zeilen = cod_proposals_for_item({"qid": "Q753", "label": "Kupfer"},
                                    [EINTRAG_KUPFER])
    assert "P589" not in [z["_pid"] for z in zeilen]


def test_kristallsystem_wird_auf_fcc_verfeinert(cod_zeilen):
    """F-Zentrierung im Hermann-Mauguin-Symbol -> kubisch flaechenzentriert.
    "kubisch" allein unterschlaegt den Unterschied zu Wolfram."""
    kristallsystem = [z for z in cod_zeilen if z["_pid"] == "P556"][0]
    assert kristallsystem["value"] == "Q3006714"
    assert kristallsystem["value_label"] == "kubisch flaechenzentriert"


def test_beleg_ist_die_originalarbeit_nicht_die_datenbank(cod_zeilen):
    raumgruppe = [z for z in cod_zeilen if z["_pid"] == "P690"][0]
    assert raumgruppe["ref_doi"] == "10.1021/ja9052569"
    assert "COD 4105040" in raumgruppe["ref_note"]
    # Messbedingungen gehoeren in die Notiz, damit die Zeile pruefbar ist
    assert "powder diffraction" in raumgruppe["ref_note"]
    assert "180 K" in raumgruppe["ref_note"]


def test_cod_zeilen_tragen_kein_berechnet_dft(cod_zeilen):
    """COD-Eintraege sind gemessen. Der P459-Qualifikator der MP-Zeilen
    waere hier schlicht falsch."""
    assert all(not z["bestimmungsmethode"] for z in cod_zeilen)


def test_cod_id_bekommt_keinen_beleg(cod_zeilen):
    """Externe Identifikatoren belegen sich selbst - wie die CAS-Nummer."""
    cod_id = [z for z in cod_zeilen if z["_pid"] == "P9824"][0]
    assert cod_id["_ohne_beleg"] is True
    assert cod_id["ref_doi"] == ""


def test_skip_pids_unterdrueckt_bereits_belegte_properties(monkeypatch):
    from materialswiki import cli
    monkeypatch.setattr(cli, "fetch_space_group_qids", lambda: RAUMGRUPPEN)
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    zeilen = cod_proposals_for_item(
        {"qid": "Q753", "label": "Kupfer"}, [EINTRAG_KUPFER],
        skip_pids={"P690", "P556", "P589"},
    )
    assert [z["_pid"] for z in zeilen] == ["P9824"]


def test_ohne_raumgruppennummer_kommt_nur_die_cod_id(monkeypatch):
    from materialswiki import cli
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    zeilen = cod_proposals_for_item(
        {"qid": "Q753", "label": "Kupfer"}, [{"file": "123", "sgNumber": None}])
    assert [z["_pid"] for z in zeilen] == ["P9824"]


def test_ohne_treffer_keine_zeilen():
    assert cod_proposals_for_item({"qid": "Q1", "label": "x"}, []) == []


# ---------------------------------------------------------------------------
# Welche Modifikation ist die uebliche?
# ---------------------------------------------------------------------------

def _eintraege(*paare):
    """(sgNumber, anzahl) -> Trefferliste."""
    out = []
    for nummer, anzahl in paare:
        out += [{"file": str(1000 + len(out) + i), "sgNumber": str(nummer),
                 "year": "2000", "doi": "10.1/x"} for i in range(anzahl)]
    return out


def test_haeufigste_raumgruppe_gewinnt_nicht_die_juengste():
    """Fe2O3 real: 13x Haematit (167), 2x monoklin (15). Die Wahl nach
    Jahrgang lieferte 15 - also die exotische Phase statt der ueblichen."""
    nummer, anzahl, gesamt, eindeutig = cod_dominante_raumgruppe(
        _eintraege((167, 13), (15, 2)))
    assert (nummer, anzahl, gesamt) == (167, 13, 15)
    assert eindeutig is True


def test_knappe_mehrheit_gilt_als_uneindeutig():
    """TiO2 real: 12x Rutil (136), 11x Anatas (141). Beide sind gaengig -
    "das" Kristallsystem von TiO2 gibt es nicht."""
    _, _, _, eindeutig = cod_dominante_raumgruppe(_eintraege((136, 12), (141, 11)))
    assert eindeutig is False


def test_einstimmigkeit_ist_eindeutig():
    """Cu real: 22 von 22 Eintraegen Raumgruppe 225."""
    nummer, _, _, eindeutig = cod_dominante_raumgruppe(_eintraege((225, 22)))
    assert (nummer, eindeutig) == (225, True)


def test_ohne_raumgruppenangabe_kommt_none():
    assert cod_dominante_raumgruppe([{"file": "1"}]) is None


def test_uneindeutige_modifikation_wird_zur_klaerung_markiert(monkeypatch):
    """Nicht still den haeufigeren Wert vorschlagen - das waere geraten."""
    from materialswiki import cli
    monkeypatch.setattr(cli, "fetch_space_group_qids", lambda: {
        136: {"qid": "Q1", "label": "Raumgruppe 136",
              "cs_qid": "Q503601", "cs_label": "tetragonal",
              "pg_qid": "Q13363960", "pg_label": "Ditetragonal-dipyramidal"},
    })
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    zeilen = cod_proposals_for_item(
        {"qid": "Q0", "label": "TiO2"}, _eintraege((136, 12), (141, 11)))

    struktur = [z for z in zeilen if z["_pid"] in ("P690", "P556", "P589")]
    assert struktur, "Raumgruppe, Punktgruppe und Kristallsystem muessen auftauchen"
    for z in struktur:
        assert z["status"].startswith("MANUELLE_KLAERUNG_NOETIG")
        assert "12 von 23" in z["status"]
    # Die COD-ID bleibt ein normaler Vorschlag - sie ist unabhaengig davon
    cod_id = [z for z in zeilen if z["_pid"] == "P9824"][0]
    assert cod_id["status"] == "VORSCHLAG"


def test_cod_id_stammt_aus_der_dominanten_raumgruppe(monkeypatch):
    """Sonst zeigt die COD-ID auf eine andere Modifikation als die
    vorgeschlagene Raumgruppe."""
    from materialswiki import cli
    monkeypatch.setattr(cli, "fetch_space_group_qids", lambda: RAUMGRUPPEN)
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    entries = [
        # juengster Eintrag, aber exotische Modifikation
        {"file": "999", "sgNumber": "15", "year": "2024", "doi": "10.1/neu"},
        {"file": "111", "sgNumber": "225", "year": "1990", "doi": "10.1/a"},
        {"file": "112", "sgNumber": "225", "year": "1991", "doi": "10.1/b"},
        {"file": "113", "sgNumber": "225", "year": "1992", "doi": "10.1/c"},
    ]
    zeilen = cod_proposals_for_item({"qid": "Q753", "label": "Kupfer"}, entries)
    cod_id = [z for z in zeilen if z["_pid"] == "P9824"][0]
    raumgruppe = [z for z in zeilen if z["_pid"] == "P690"][0]
    assert cod_id["value"] == "113"          # nicht 999
    assert raumgruppe["value"] == "Q15041891"


# ---------------------------------------------------------------------------
# MP tritt zurueck, wo COD geliefert hat
# ---------------------------------------------------------------------------

def test_mp_ueberspringt_was_cod_schon_geliefert_hat(monkeypatch):
    from materialswiki import cli
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    material = {"material_id": "mp-30", "formula": "Cu", "density": 8.96,
                "symmetry": {"crystal_system": "Cubic", "symbol": "Fm-3m"}}
    wd = {"qid": "Q753", "label": "Kupfer"}

    ohne_skip = {z["_pid"] for z in proposals_for_material(material, wd)}
    assert "P556" in ohne_skip

    mit_skip = {z["_pid"] for z in
                proposals_for_material(material, wd, skip_pids={"P556"})}
    assert "P556" not in mit_skip
    assert "P2054" in mit_skip      # Dichte liefert MP weiterhin


# ---------------------------------------------------------------------------
# Zitierpflicht des Materials Project
# ---------------------------------------------------------------------------

def test_elastische_groessen_zitieren_zusaetzlich_den_datensatz(monkeypatch):
    """Die Nutzungsbedingungen verlangen fuer den Elastizitaets-Datensatz
    eine eigene Zitierung zusaetzlich zu Jain et al."""
    from materialswiki import cli
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    material = {"material_id": "mp-30", "formula": "Cu",
                "bulk_modulus": {"vrh": 140.0}, "shear_modulus": {"vrh": 46.0},
                "homogeneous_poisson": 0.35}
    zeilen = proposals_for_material(material, {"qid": "Q753", "label": "Cu"})

    for pid in ("P5668", "P5673", "P5593"):
        zeile = [z for z in zeilen if z["_pid"] == pid][0]
        assert zeile["_ref"].dataset_doi == "10.1038/sdata.2015.9"
        assert zeile["ref_doi"] == f"{MP_DOI}; 10.1038/sdata.2015.9"
        assert "de Jong" in zeile["ref_note"]


def test_nicht_elastische_groessen_zitieren_nur_die_hauptpublikation(monkeypatch):
    from materialswiki import cli
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)
    material = {"material_id": "mp-30", "formula": "Cu", "density": 8.96}
    zeile = [z for z in proposals_for_material(
        material, {"qid": "Q753", "label": "Cu"}) if z["_pid"] == "P2054"][0]
    assert zeile["ref_doi"] == MP_DOI


def test_beide_dois_landen_im_quickstatements_referenzblock():
    ref = Reference(doi=MP_DOI, dataset_doi="10.1038/sdata.2015.9")
    qs = ref.as_quickstatements()
    assert qs == f'\tS356\t"{MP_DOI}"\tS356\t"10.1038/sdata.2015.9"'
    # Sonst steht in der Notiz eine nackte DOI, die niemandem etwas sagt.
    for doi in set(MP_DATASET_DOI.values()):
        assert doi in MP_DATASET_WERK
