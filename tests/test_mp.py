"""Materials-Project-Anbindung: Feldabbildung und Einheiten - netzwerkfrei."""
import pytest

from materialswiki.cli import (
    MP_DOI,
    MP_FIELD_MAP,
    PROPERTY_MAP,
    mp_value,
    proposals_for_material,
)


# Ein realistisches MP-Dokument (Feldnamen aus dem OpenAPI-Schema SummaryDoc).
RUTIL = {
    "material_id": "mp-2657",
    "formula_pretty": "TiO2",
    "formula": "TiO2",
    "theoretical": False,
    "is_stable": True,
    "energy_above_hull": 0.0,
    "database_IDs": {"icsd": ["icsd-33837"]},
    "density": 4.24,                       # g/cm^3
    "symmetry": {"crystal_system": "Tetragonal"},
    "bulk_modulus": {"voigt": 216.0, "reuss": 210.0, "vrh": 213.0},   # GPa
    "shear_modulus": {"voigt": 105.0, "reuss": 99.0, "vrh": 102.0},   # GPa
    "homogeneous_poisson": 0.28,
}

WD = {"qid": "Q320603", "label": "Rutil", "ambiguous": False}


@pytest.fixture(autouse=True)
def leeres_item(monkeypatch):
    """Wikidata-Abfrage abklemmen: das Item traegt noch keine Aussage."""
    monkeypatch.setattr("materialswiki.cli.item_has_statement",
                        lambda qid, pid: False)


def nach_pid(rows):
    return {r["_pid"]: r for r in rows}


# --- Einheitenumrechnung, der eigentliche Fallstrick ----------------------

@pytest.mark.parametrize("pid, erwartet, einheit", [
    # g/cm³ -> kg/m³
    ("P2054", 4240.0, "Q844211"),
    # GPa -> Pa, und zwar das vrh-Mittel (213), nicht voigt (216)/reuss (210)
    ("P5668", 213.0e9, "Q44395"),
    ("P5673", 102.0e9, "Q44395"),
    # dimensionslos, bleibt wie geliefert
    ("P5593", 0.28, ""),
])
def test_einheiten_werden_umgerechnet(pid, erwartet, einheit):
    zeile = nach_pid(proposals_for_material(RUTIL, WD))[pid]
    assert zeile["value"] == pytest.approx(erwartet)
    assert zeile["unit_qid"] == einheit


# --- Kristallsystem -------------------------------------------------------

def test_kristallsystem_wird_trotz_grossschreibung_abgebildet():
    """MP schreibt 'Tetragonal', die value_map fuehrt 'tetragonal'."""
    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    assert zeilen["P556"]["value"] == "Q503601"
    assert zeilen["P556"]["status"] == "VORSCHLAG"


def test_unbekanntes_kristallsystem_wird_nicht_geraten():
    doc = {**RUTIL, "symmetry": {"crystal_system": "Amorph"}}
    zeilen = [r for r in proposals_for_material(doc, WD) if r["_pid"] == "P556"]
    assert "MANUELLE_KLAERUNG_NOETIG" in zeilen[0]["status"]


# --- Beleg ----------------------------------------------------------------

def test_beleg_nennt_doi_mp_id_und_qualitaetsmerkmale():
    """Einzelne MP-Materialien haben keine eigene DOI - belegt wird mit der
    Referenzpublikation, identifiziert ueber die mp-ID. Beim Durchsehen soll
    ausserdem ohne Nachschlagen erkennbar sein, worauf der Wert beruht."""
    zeile = proposals_for_material(RUTIL, WD)[0]
    assert zeile["ref_doi"] == MP_DOI
    for text in ("mp-2657", "experimentell nachgewiesen", "stabil",
                 "icsd-33837"):
        assert text in zeile["ref_note"]


def test_gerechnete_werte_sind_als_berechnet_ausgewiesen():
    """MP-Werte sind DFT-Rechnungen, keine Messungen. Bei den elastischen
    Moduln weichen sie 17-41 % vom Handbuchwert ab - das darf beim
    Durchsehen nicht unsichtbar bleiben."""
    for zeile in nach_pid(proposals_for_material(RUTIL, WD)).values():
        if zeile["_pid"] == "P556":
            continue  # Literaturbeleg, siehe unten
        assert "berechnet (DFT)" in zeile["ref_note"]


# --- Bestimmungsmethode (P459) -------------------------------------------

def test_gerechnete_aussagen_tragen_p459_dft():
    """Der Beleg sagt WOHER der Wert kommt, der Qualifikator WIE er
    bestimmt wurde. Ohne ihn stuende am Wikidata-Item eines Werkstoffs eine
    Rechnung, die wie eine Messung aussieht."""
    from materialswiki.cli import DETERMINATION_PID, DFT_QID

    zeilen = nach_pid(proposals_for_material(RUTIL, WD))
    for pid in ("P2054", "P5668", "P5673", "P5593"):
        assert (DETERMINATION_PID, DFT_QID, "Dichtefunktionaltheorie") \
            in zeilen[pid]["_qualifiers"], pid
    # und lesbar in der CSV
    assert zeilen["P5668"]["bestimmungsmethode"] == \
        "P459=Q1048589 (Dichtefunktionaltheorie)"


# --- Literaturbeleg statt Rechnung ---------------------------------------

def test_kristallsystem_wird_mit_literatur_belegt():
    """Dass Rutil tetragonal ist, ist etablierte Kristallographie - eine
    DFT-Symmetrieanalyse dafuer zu zitieren waere die schlechtere Quelle.
    Ein Literaturwert mit dem Vermerk "berechnet" waere zugleich falsch, und
    die Herkunft aus MP muss trotzdem pruefbar bleiben: sonst ist nicht
    erkennbar, welche Modifikation gemeint ist."""
    zeile = nach_pid(proposals_for_material(RUTIL, WD))["P556"]

    assert zeile["ref_isbn"] == "0-08-037941-9"
    assert zeile["ref_doi"] == ""
    assert zeile["ref_mode"] == "ISBN-10"

    assert zeile["_qualifiers"] == []
    assert zeile["bestimmungsmethode"] == ""
    assert "berechnet (DFT)" not in zeile["ref_note"]

    for text in ("mp-2657", "Greenwood/Earnshaw", "pruefen"):
        assert text in zeile["ref_note"]


# --- Identifikatoren ohne Beleg -------------------------------------------

def _cas_zeile():
    """Eine CAS-Zeile, wie sie aus der Wikipedia-Infobox entsteht."""
    from materialswiki.cli import Reference, make_row

    return make_row(
        "VORSCHLAG", "Wikipedia (de)", WD, PROPERTY_MAP["cas_number"],
        "7440-50-8", "",
        Reference(imported_from="Q48183",
                  import_url="https://de.wikipedia.org/x",
                  note="Infobox-Feld 'CAS'"),
    )


def test_cas_nummer_geht_ohne_beleg_raus(tmp_path):
    """Ein Identifikator belegt sich selbst: 7440-50-8 IST der Verweis ins
    CAS-Register. 'importiert aus Wikipedia' belegt nur, wo abgeschrieben
    wurde - nicht, dass es stimmt. Spurlos ist das trotzdem nicht: die
    Herkunft bleibt in ref_note, die Belegspalten bleiben leer."""
    from materialswiki.cli import write_quickstatements_draft

    zeile = _cas_zeile()
    assert zeile["ref_mode"] == "ohne Beleg (Identifikator)"
    assert zeile["ref_url"] == zeile["ref_doi"] == zeile["ref_isbn"] == ""
    assert zeile["ref_note"] == "Infobox-Feld 'CAS'"

    pfad = tmp_path / "e.txt"
    write_quickstatements_draft([zeile], str(pfad))
    text = pfad.read_text(encoding="utf-8")
    aussage = [z for z in text.splitlines() if z.startswith("Q320603")][0]

    assert aussage == 'Q320603\tP231\t"7440-50-8"'
    assert "\tS" not in aussage
    assert "Infobox-Feld 'CAS'" in text
    assert "ohne Beleg, Identifikator" in text


def test_mengenwerte_behalten_ihren_beleg():
    """Die Ausnahme gilt nur fuer Identifikatoren, nicht generell."""
    zeile = nach_pid(proposals_for_material(RUTIL, WD))["P2054"]
    assert zeile["_ohne_beleg"] is False
    assert zeile["ref_doi"] == MP_DOI


def test_isbn10_wird_als_s957_ausgegeben(tmp_path):
    """ISBN-10 gehoert auf P957, ISBN-13 auf P212 - sonst landet die Nummer
    in der falschen Property."""
    from materialswiki.cli import write_quickstatements_draft

    zeilen = [nach_pid(proposals_for_material(RUTIL, WD))["P556"]]
    pfad = tmp_path / "e.txt"
    write_quickstatements_draft(zeilen, str(pfad))
    aussage = [z for z in pfad.read_text(encoding="utf-8").splitlines()
               if z.startswith("Q320603")][0]
    felder = aussage.split("\t")
    assert felder[:3] == ["Q320603", "P556", "Q503601"]
    assert felder[3] == "S957"           # ISBN-10
    assert felder[4] == '"0-08-037941-9"'
    assert "P459" not in aussage


def test_qualifikator_landet_vor_dem_beleg_in_quickstatements(tmp_path):
    """QuickStatements V1: Aussage, dann Qualifikatoren (P...), dann Belege
    (S...) - alles in einer Zeile. Steht der Beleg vor dem Qualifikator,
    haengt QuickStatements den Qualifikator an die Referenz statt an die
    Aussage."""
    from materialswiki.cli import write_quickstatements_draft

    zeilen = [r for r in proposals_for_material(RUTIL, WD)
              if r["_pid"] == "P2054"]
    pfad = tmp_path / "e.txt"
    write_quickstatements_draft(zeilen, str(pfad))
    aussage = [z for z in pfad.read_text(encoding="utf-8").splitlines()
               if z.startswith("Q320603")][0]
    felder = aussage.split("\t")
    assert felder[:3] == ["Q320603", "P2054", "4240.0U844211"]
    # Erst alle Qualifikatoren (P...), dann der Beleg (S...)
    assert felder[3:9] == ["P459", "Q1048589",
                           "P2076", "0U11579",
                           "P515", "Q11438"]
    assert felder[9].startswith("S")


def test_wikipedia_werte_bekommen_keine_methode():
    """Literaturwerte: mit welcher Methode sie bestimmt wurden, steht in der
    Infobox nicht - eine Methode zu behaupten waere geraten."""
    from materialswiki.cli import Reference, make_row

    zeile = make_row(
        "VORSCHLAG", "Wikipedia (de)", WD, PROPERTY_MAP["density"],
        4230.0, "", Reference(imported_from="Q48183",
                              import_url="https://de.wikipedia.org/x"),
    )
    assert zeile["_qualifiers"] == []
    assert zeile["bestimmungsmethode"] == ""


# --- Paginierung ----------------------------------------------------------

class FakeResponse:
    status_code = 200
    ok = True

    def __init__(self, docs):
        self._docs = docs

    def json(self):
        return {"data": self._docs, "meta": {"max_limit": 1000}}


def test_mehr_als_eine_seite_wird_nachgeholt(monkeypatch):
    """Regression: frueher stand hier min(max_entries, 100). Die API liefert
    dann klaglos 100 Dokumente statt der angeforderten 250 - man merkt es
    nicht, die Ausbeute ist einfach still gedeckelt."""
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "test")
    monkeypatch.setattr(cli, "MP_MAX_LIMIT", 100)  # kleine Seiten erzwingen
    gesehen = []

    def fake(method, url, **kw):
        p = kw["params"]
        gesehen.append((p["_skip"], p["_limit"]))
        start = p["_skip"]
        return FakeResponse([
            {"material_id": f"mp-{i}", "formula_pretty": "TiO2"}
            for i in range(start, start + p["_limit"])
        ])

    monkeypatch.setattr(cli, "request_with_retry", fake)
    mats = cli.fetch_mp_materials(["Ti"], 250)

    assert len(mats) == 250
    assert len({m["material_id"] for m in mats}) == 250  # keine Dubletten
    assert gesehen == [(0, 100), (100, 100), (200, 50)]


def test_kurze_seite_beendet_die_schleife(monkeypatch):
    """Weniger Treffer als angefordert: nicht endlos weiterfragen."""
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "test")
    aufrufe = []

    def fake(method, url, **kw):
        aufrufe.append(kw["params"]["_skip"])
        return FakeResponse([
            {"material_id": "mp-1", "formula_pretty": "TiO2"},
            {"material_id": "mp-2", "formula_pretty": "TiO2"},
        ])

    monkeypatch.setattr(cli, "request_with_retry", fake)
    assert len(cli.fetch_mp_materials(["Ti"], 500)) == 2
    assert aufrufe == [0]  # genau eine Anfrage


# --- Periodensystem: Platzhalter und Robustheit ---------------------------

BINDINGS = [
    {"e": {"value": "http://www.wikidata.org/entity/Q716"},
     "sym": {"value": "Ti"}, "eLabel": {"value": "Titan"},
     "enLabel": {"value": "titanium"}, "deTitle": {"value": "Titan (Element)"}},
    {"e": {"value": "http://www.wikidata.org/entity/Q1098"},
     "sym": {"value": "U"}, "eLabel": {"value": "Uran"},
     "enLabel": {"value": "uranium"}, "deTitle": {"value": "Uran"}},
    # Systematischer IUPAC-Platzhalter fuer ein unentdecktes Element
    {"e": {"value": "http://www.wikidata.org/entity/Q1región"},
     "sym": {"value": "Ubb"}, "eLabel": {"value": "Unbibium"},
     "enLabel": {"value": "unbibium"}, "deTitle": {"value": ""}},
]


def test_systematische_platzhalter_werden_aussortiert(monkeypatch):
    """Regression: Wikidata fuehrt 56 IUPAC-Platzhalter fuer unentdeckte
    Elemente (Ubb, Uue, ...) korrekt als P31=Q11344. Materials Project
    antwortet darauf mit HTTP 400 und riss einen Lauf bei Element 112 von
    174 ab. Echte Symbole haben 1-2 Zeichen, Platzhalter immer 3."""
    from materialswiki import cli

    class R:
        def json(self):
            return {"results": {"bindings": BINDINGS}}

    monkeypatch.setattr(cli, "get_with_retry", lambda *a, **k: R())
    symbole = cli.fetch_element_qids()

    assert set(symbole) == {"Ti", "U"}
    assert "Ubb" not in symbole


def test_ein_gescheitertes_element_beendet_den_lauf_nicht(monkeypatch):
    """Ueber 118 Elemente dauert ein Lauf Stunden. Faellt eines aus, muessen
    die uebrigen trotzdem durchlaufen."""
    from materialswiki import cli

    monkeypatch.setattr(cli, "fetch_element_qids", lambda: {
        s: {"qid": f"Q{i}", "label": s, "name_en": s, "title_de": s}
        for i, s in enumerate(["Ti", "U", "V"])
    })

    def fake_fetch(elements, max_entries, pure_element=None, **kw):
        if pure_element == "U":
            raise RuntimeError("MP-Query fehlgeschlagen (400): kaputt")
        return [{"material_id": f"mp-{pure_element}",
                 "formula_pretty": pure_element, "formula": pure_element,
                 "density": 4.0}]

    monkeypatch.setattr(cli, "fetch_mp_materials", fake_fetch)
    monkeypatch.setattr(cli, "item_has_statement", lambda q, p: False)

    # cod=False: hier wird die MP-Stufe geprueft, und die COD-Stufe wuerde
    # sonst wirklich ins Netz gehen - die Tests laufen offline.
    zeilen = list(cli.build_periodic_table_proposals(1, None, wikipedia=False,
                                                     cod=False))
    geliefert = {z["label"] for z in zeilen}

    assert geliefert == {"Ti", "V"}      # U faellt aus, V kommt trotzdem
    assert len(zeilen) == 2


def test_fehlender_schluessel_bricht_sehr_wohl_ab(monkeypatch):
    """Der trifft jedes Element - 118-mal weitermachen waere sinnlos."""
    from materialswiki import cli

    monkeypatch.setattr(cli, "fetch_element_qids", lambda: {
        "Ti": {"qid": "Q716", "label": "Ti", "name_en": "ti", "title_de": "Ti"}
    })

    def fake_fetch(*a, **kw):
        raise cli.MissingApiKey("MP_API_KEY fehlt")

    monkeypatch.setattr(cli, "fetch_mp_materials", fake_fetch)
    with pytest.raises(cli.MissingApiKey):
        list(cli.build_periodic_table_proposals(1, None, wikipedia=False))


# --- User-Agent -----------------------------------------------------------

def test_mp_user_agent_enthaelt_kein_bot():
    """Regression: die MP-WAF antwortet auf jede Kennung mit 'Bot' im Namen
    mit HTTP 403 - noch bevor sie den API-Schluessel prueft. Der
    Wikimedia-User-Agent traegt 'Bot' und muss das auch; fuer MP braucht es
    deshalb eine eigene Kennung."""
    from materialswiki.cli import MP_USER_AGENT, USER_AGENT

    assert "bot" not in MP_USER_AGENT.lower(), MP_USER_AGENT
    assert "Bot" in USER_AGENT  # Wikimedia-Richtlinie, bleibt so
    assert MP_USER_AGENT != USER_AGENT


def test_mp_header_setzt_schluessel_oder_meldet_sich_verstaendlich(monkeypatch):
    from materialswiki import cli

    monkeypatch.setattr(cli, "MP_API_KEY", "testschluessel")
    kopf = cli.mp_headers()
    assert kopf["X-API-KEY"] == "testschluessel"
    assert "bot" not in kopf["User-Agent"].lower()

    monkeypatch.setattr(cli, "MP_API_KEY", "")
    with pytest.raises(cli.MissingApiKey, match="MP_API_KEY"):
        cli.mp_headers()


# --- Physikalische Plausibilitaet -----------------------------------------

# Reale kaputte Daten: MP fuehrt Zink (mp-aaaaaadb) als experimentell
# nachgewiesen UND stabil, die Reuss-Schranke der Elastizitaet ist aber
# havariert und reisst das VRH-Mittel mit.
ZINK_KAPUTT = {
    "material_id": "mp-aaaaaadb",
    "formula_pretty": "Zn", "formula": "Zn",
    "theoretical": False, "is_stable": True,
    "density": 7.53,
    "symmetry": {"crystal_system": "Hexagonal"},
    "bulk_modulus": {"voigt": 76.283, "reuss": 95.46, "vrh": 85.872},
    "shear_modulus": {"voigt": 44.248, "reuss": -5606.668, "vrh": -2781.21},
    "homogeneous_poisson": -1.153,
}


def test_unplausible_werte_werden_ausgewiesen_statt_verworfen():
    """Ein negativer Schubmodul bedeutet mechanische Instabilitaet, und fuer
    isotrope lineare Elastizitaet gilt -1 <= nu <= 0,5. Zink ist stabil - die
    Werte sind Rechenmuell und duerfen nie nach Wikidata. Still verworfen
    werden sie trotzdem nicht, sonst faellt nie auf, dass die Datenbank an
    dieser Stelle kaputt ist."""
    zeilen = nach_pid(proposals_for_material(ZINK_KAPUTT, WD))

    for pid in ("P5673", "P5593"):
        assert zeilen[pid]["status"].startswith("MANUELLE_KLAERUNG_NOETIG"), pid
    assert "unplausibler Wert" in zeilen["P5673"]["status"]
    assert "mp-aaaaaadb" in zeilen["P5673"]["status"]
    assert zeilen["P5673"]["value"] == pytest.approx(-2.78121e12)


def test_die_gesunden_groessen_desselben_materials_bleiben():
    """Ein kaputter Kennwert darf die uebrigen nicht mitreissen."""
    zeilen = nach_pid(proposals_for_material(ZINK_KAPUTT, WD))
    assert zeilen["P2054"]["status"] == "VORSCHLAG"   # Dichte 7530 kg/m^3
    assert zeilen["P5668"]["status"] == "VORSCHLAG"   # Kompressionsmodul
    assert zeilen["P556"]["status"] == "VORSCHLAG"    # hexagonal


@pytest.mark.parametrize("key, wert, erwartet", [
    ("shear_modulus", 4.3e10, True),      # Zink real, 43 GPa
    ("shear_modulus", -1.0, False),
    ("shear_modulus", 0.0, False),
    ("bulk_modulus", 4.43e11, True),      # Diamant, 443 GPa
    ("poisson_ratio", 0.34, True),
    ("poisson_ratio", -0.5, True),        # auxetisch, aber moeglich
    ("poisson_ratio", 0.51, False),
    ("poisson_ratio", -1.153, False),
    ("density", 22590.0, True),           # Osmium
    ("density", 534.0, True),             # Lithium
    ("density", -1.0, False),
    ("crystal_system", "hexagonal", True),  # keine Schranken definiert
])
def test_plausibilitaetsschranken(key, wert, erwartet):
    from materialswiki.cli import ist_plausibel

    assert ist_plausibel(key, wert) is erwartet


# --- Robustheit -----------------------------------------------------------

def test_fehlende_felder_erzeugen_keine_zeilen():
    mager = {"material_id": "mp-1", "formula_pretty": "XY", "formula": "XY"}
    assert proposals_for_material(mager, WD) == []


def test_nichtzahlen_werden_verworfen_statt_gedeutet():
    assert mp_value("keine Zahl", 1000.0) is None
    assert mp_value(None, 1000.0) is None
    assert mp_value(True, 1000.0) is None


# --- Konsistenz der Abbildung --------------------------------------------

def test_die_feldabbildung_ist_in_sich_stimmig():
    """Ein Tippfehler im Schluessel wuerde die Groesse still verschwinden
    lassen - hier faellt er auf. Und itemwertige Groessen duerfen keinen
    Umrechnungsfaktor tragen."""
    for pfad, (schluessel, faktor) in MP_FIELD_MAP.items():
        assert schluessel in PROPERTY_MAP, f"{pfad} -> unbekannt: {schluessel}"
        ist_item = PROPERTY_MAP[schluessel].get("datatype") == "item"
        assert ist_item == (faktor is None), f"{pfad}: Faktor passt nicht zum Typ"


# --- Messbedingungen der Dichte (P2076 / P515) ----------------------------

def test_mp_dichte_traegt_null_kelvin_und_fest():
    """Eine DFT-Rechnung liefert das Volumen des relaxierten Grundzustands,
    also 0 K - nicht 20 °C. Genau daher ruehrt auch die systematische
    Abweichung von den Handbuchwerten."""
    from materialswiki.cli import AGGREGAT_PID, TEMPERATUR_PID

    zeile = nach_pid(proposals_for_material(RUTIL, WD))["P2054"]
    qual = {pid: wert for pid, wert, _ in zeile["_qualifiers"]}
    assert qual[TEMPERATUR_PID] == "0U11579"   # 0 Kelvin
    assert qual[AGGREGAT_PID] == "Q11438"      # Festkoerper


def test_nur_die_dichte_bekommt_messbedingungen():
    """Ein Schubmodul braucht keinen Aggregatzustand."""
    from materialswiki.cli import AGGREGAT_PID, TEMPERATUR_PID

    for pid in ("P5668", "P5673", "P5593", "P556"):
        zeile = nach_pid(proposals_for_material(RUTIL, WD))[pid]
        pids = {p for p, _, _ in zeile["_qualifiers"]}
        assert TEMPERATUR_PID not in pids and AGGREGAT_PID not in pids, pid


@pytest.mark.parametrize("feld, erwartet", [
    ("8,96&nbsp;g/cm³ (20 [[Grad Celsius|°C]])", 20.0),
    ("4,50 g/cm<sup>3</sup> (25 [[Grad Celsius|°C]])", 25.0),
    ("7,874 g/cm<sup>3</sup>", None),        # keine Angabe -> Vorgabe greift
    ("13,5459 g/cm<sup>3</sup>", None),
])
def test_messtemperatur_wird_aus_der_infobox_gelesen(feld, erwartet):
    """Blind 20 °C anzunehmen waere falsch: Titan und Zink nennen 25 °C."""
    from materialswiki.cli import parse_de_messtemperatur

    assert parse_de_messtemperatur(feld) == erwartet


def test_aggregatzustand_folgt_dem_schmelzpunkt():
    """Quecksilber schmilzt bei 234 K - seine Dichte bei 20 °C meint die
    FLUESSIGKEIT. 'fest' waere hier schlicht falsch."""
    from materialswiki.cli import (AGGREGAT_FEST, AGGREGAT_FLUESSIG,
                                   AGGREGAT_GAS, aggregatzustand_bei)

    quecksilber = {"melting_point": (234.32, "", {}),
                   "boiling_point": (629.88, "", {})}
    eisen = {"melting_point": (1811.0, "", {}),
             "boiling_point": (3134.0, "", {})}
    stickstoff = {"melting_point": (63.15, "", {}),
                  "boiling_point": (77.36, "", {})}

    assert aggregatzustand_bei(20.0, quecksilber) == AGGREGAT_FLUESSIG
    assert aggregatzustand_bei(20.0, eisen) == AGGREGAT_FEST
    assert aggregatzustand_bei(20.0, stickstoff) == AGGREGAT_GAS


def test_ohne_schmelzpunkt_wird_nichts_behauptet():
    """Lieber kein Qualifikator als ein falscher."""
    from materialswiki.cli import aggregatzustand_bei

    assert aggregatzustand_bei(20.0, {}) is None
    assert aggregatzustand_bei(20.0, {"melting_point": (100.0, "", {})}) is None


# --- Kristallsystem: fcc und bcc ------------------------------------------

@pytest.mark.parametrize("system, symbol, erwartet", [
    ("cubic", "Fm-3m", "fcc"),      # Kupfer
    ("cubic", "Im-3m", "bcc"),      # Eisen, Wolfram
    ("cubic", "Pm-3m", "cubic"),    # primitiv -> bleibt kubisch
    ("cubic", "Fd-3m", "fcc"),      # Diamantstruktur
    ("hexagonal", "P6/mmm", "hexagonal"),   # nicht kubisch -> unveraendert
    ("tetragonal", "I4/mmm", "tetragonal"),  # I, aber nicht kubisch
    ("cubic", None, "cubic"),       # ohne Symbol nichts behaupten
    ("cubic", "", "cubic"),
    ("cubic", "Xy-3m", "cubic"),    # unbekannte Zentrierung
])
def test_zentrierung_aus_dem_raumgruppensymbol(system, symbol, erwartet):
    """Der erste Buchstabe des Hermann-Mauguin-Symbols nennt die
    Bravais-Zentrierung. MPs crystal_system sagt nur 'Cubic' und
    unterschlaegt damit den Unterschied zwischen Kupfer und Wolfram."""
    from materialswiki.cli import verfeinere_zentrierung

    assert verfeinere_zentrierung(system, symbol) == erwartet


@pytest.mark.parametrize("symbol, qid, label", [
    ("Fm-3m", "Q3006714", "kubisch flaechenzentriert"),   # Kupfer
    ("Im-3m", "Q851536", "kubisch raumzentriert"),        # Wolfram
])
def test_mp_kubisch_wird_auf_die_zentrierung_verfeinert(symbol, qid, label):
    doc = {**RUTIL, "formula_pretty": "X", "formula": "X",
           "symmetry": {"crystal_system": "Cubic", "symbol": symbol}}
    zeile = nach_pid(proposals_for_material(doc, WD))["P556"]
    assert zeile["value"] == qid
    assert zeile["value_label"] == label


@pytest.mark.parametrize("text, erwartet", [
    ("kubisch flächenzentriert", "Q3006714"),
    ("[[Kubisches Kristallsystem|kubisch]] flächenzentriert", "Q3006714"),
    ("kubisch raumzentriert", "Q851536"),
    ("kubisch-raumzentriert", "Q851536"),
    ("hexagonal", "Q663314"),
])
def test_deutsche_infobox_erkennt_die_zentrierung(text, erwartet):
    """Aluminium schreibt die Zentrierung hinter einen Wikilink - ohne
    Aufloesen zerreisst die Klammer die gesuchte Phrase."""
    from materialswiki.cli import PROPERTY_MAP, wikipedia_de_values

    werte = wikipedia_de_values({"Kristallstruktur": text})
    schluessel = werte["crystal_system"][0]
    assert PROPERTY_MAP["crystal_system"]["value_map"][schluessel][0] == erwartet


@pytest.mark.parametrize("text, erwartet", [
    ("face-centered cubic", "fcc"),
    ("body-centered cubic", "bcc"),
    ("hexagonal close packed", "hexagonal"),
])
def test_englische_infobox_erkennt_die_zentrierung(text, erwartet):
    from materialswiki.cli import wikipedia_values

    assert wikipedia_values({"crystal structure": text})["crystal_system"][0] \
        == erwartet


def test_alle_value_map_werte_stehen_im_constraint():
    """Der one-of-Constraint von P556, am 2026-08-15 ausgelesen. Ein Wert
    ausserhalb waere ein Constraint-Verstoss an jedem Item."""
    erlaubt = {
        "Q376927", "Q624543", "Q648961", "Q503601", "Q588274", "Q663314",
        "Q473227", "Q263214", "Q103382", "Q3006714", "Q851536",
    }
    from materialswiki.cli import PROPERTY_MAP

    for schluessel, (qid, _) in \
            PROPERTY_MAP["crystal_system"]["value_map"].items():
        assert qid in erlaubt, f"{schluessel} -> {qid} nicht im Constraint"
