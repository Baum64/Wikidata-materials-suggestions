"""Ableitungsregeln der Anwendungs-Entwuerfe - netzwerkfrei.

Geprueft wird nur, was ueber die Zeile ENTSCHEIDET: welche Klasse als
Verwendung durchgeht, was die Ueberdeckung wegnimmt und wo die Rueckkante
P186 einspielbar ist und wo nicht. Die Abfragen selbst brauchen kein Test -
sie holen, was sie holen; die Regeln daneben sind das, was falsch sein kann.
"""
import importlib.util
import os

import pytest

# Anwendung/ ist kein Paket (wie P279-structure/ auch nicht) - das Modul
# kommt deshalb ueber den Pfad herein, nicht ueber einen Import.
_PFAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "Anwendung", "Anwendung.py")
_spec = importlib.util.spec_from_file_location("anwendung_modul", _PFAD)
anwendung = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anwendung)


def objekte(n, praefix="Q9"):
    """n verschiedene Beleg-QIDs."""
    return {f"{praefix}{i:04d}" for i in range(n)}


# --- Aggregation: was wird zur Verwendung? --------------------------------

def test_schwelle_haelt_zufallstreffer_raus():
    nach_klasse = {"QBronze": {"QGlocke": objekte(2)}}
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, {}, {}, {},
                                             min_belege=3, min_sprachen=0)
    assert treffer == []

    nach_klasse = {"QBronze": {"QGlocke": objekte(3)}}
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, {}, {}, {},
                                             min_belege=3, min_sprachen=0)
    assert [b["quickstatements"] for b in treffer] == ["QBronze\tP366\tQGlocke"]
    assert treffer[0]["kennzahl"] == 3


def test_vorhandene_aussage_wird_nicht_wiederholt():
    nach_klasse = {"QBronze": {"QGlocke": objekte(50)}}
    treffer = anwendung.pruefe_p366_aus_p186(
        nach_klasse, {"QBronze": {"QGlocke"}}, {}, {}, {}, min_belege=3,
        min_sprachen=0)
    assert treffer == []


@pytest.mark.parametrize("gesperrt", sorted(anwendung.KLASSEN_SPERRE))
def test_sperrliste_greift_fuer_jede_klasse(gesperrt):
    """Fundumstand, Schutzstatus und Wikimedia-Innenleben sind keine
    Verwendungen - auch nicht mit tausend Belegen."""
    nach_klasse = {"QBronze": {gesperrt: objekte(1000)}}
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, {}, {}, {},
                                             min_belege=3, min_sprachen=0)
    assert treffer == []


def test_werkstoff_als_verwendung_faellt_weg():
    """Ein Werkstoff, der aus einem Werkstoff besteht, ist eine
    Materialbeziehung (P527/P186) und keine Anwendung."""
    nach_klasse = {"QBronze": {"QMessing": objekte(40)}}
    rollen = {"QMessing": {anwendung.MATERIAL_QID}}
    assert anwendung.pruefe_p366_aus_p186(nach_klasse, {}, rollen, {}, {},
                                          min_belege=3, min_sprachen=0) == []


# --- Ueberdeckung ---------------------------------------------------------

def test_allgemeinere_klasse_verdraengt_die_engere():
    nach_klasse = {"QBronze": {"QSkulptur": objekte(100),
                               "QStatue": objekte(30, "Q8"),
                               "QStatuette": objekte(10, "Q7")}}
    oberklassen = {"QStatue": {"QSkulptur"},
                   "QStatuette": {"QStatue", "QSkulptur"}}
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, {}, oberklassen,
                                             {}, min_belege=3, min_sprachen=0)
    einspielbar = [b for b in treffer if b["befund"] == "p366-aus-p186"]
    ueberdeckt = [b for b in treffer if b["befund"] == "p366-ueberdeckt"]
    assert [b["ziel_qid"] for b in einspielbar] == ["QSkulptur"]
    assert sorted(b["ziel_qid"] for b in ueberdeckt) == ["QStatue", "QStatuette"]
    # Die verdraengten Zeilen bleiben vollstaendig - nur auskommentiert.
    assert ueberdeckt[0]["quickstatements"].startswith("QBronze\tP366\t")


def test_kaputte_oberklassenkante_loescht_die_bestbelegte_zeile_nicht():
    """Wikidata fuehrt Muenze als Unterklasse von Skulptur. Ueber diese Kante
    darf die besser belegte Muenz-Zeile die Skulptur-Zeile nicht kippen -
    verdraengt wird nur von OBEN nach unten."""
    nach_klasse = {"QBronze": {"QMuenze": objekte(200),
                               "QSkulptur": objekte(100, "Q8")}}
    oberklassen = {"QMuenze": {"QSkulptur"}}
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, {}, oberklassen,
                                             {}, min_belege=3, min_sprachen=0)
    einspielbar = sorted(b["ziel_qid"] for b in treffer
                         if b["befund"] == "p366-aus-p186")
    assert einspielbar == ["QMuenze", "QSkulptur"]


def test_gleichstand_faellt_zugunsten_der_oberklasse():
    """Bei gleicher Belegzahl sagt die engere Zeile mehr, ohne besser belegt
    zu sein - dann gewinnt die allgemeinere."""
    nach_klasse = {"QBronze": {"QSkulptur": objekte(40),
                               "QStatue": objekte(40, "Q8")}}
    treffer = anwendung.pruefe_p366_aus_p186(
        nach_klasse, {}, {}, {"QStatue": {"QSkulptur"}}, {}, min_belege=3,
        min_sprachen=0)
    assert [b["ziel_qid"] for b in treffer
            if b["befund"] == "p366-aus-p186"] == ["QSkulptur"]


# --- Verbundgegenstand: kleiner Anteil ------------------------------------

def test_verbundgegenstand_kommt_nicht_in_abschnitt_eins():
    """Ein Wolkenkratzer besteht nicht aus Stahl, er hat ein Stahlskelett."""
    nach_klasse = {"QStahl": {"QWolkenkratzer": objekte(500)}}
    rollen = {"QWolkenkratzer": {"Q41176"}}   # Gebaeude
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, rollen, {}, {},
                                             min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-verbund"]
    # Die Zeile bleibt vollstaendig erhalten, nur eben auskommentiert.
    assert treffer[0]["quickstatements"] == "QStahl\tP366\tQWolkenkratzer"
    assert "Gebäude" in treffer[0]["begruendung"]


@pytest.mark.parametrize("wurzel", sorted(anwendung.VERBUND_WURZELN))
def test_jede_verbundwurzel_greift(wurzel):
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QStahl": {"QDing": objekte(500)}}, {}, {"QDing": {wurzel}}, {}, {},
        min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-verbund"]


def test_monolithischer_gegenstand_bleibt_einspielbar():
    """Muenze, Glocke, Skulptur haengen unter keiner Verbundwurzel."""
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QBronze": {"QGlocke": objekte(500)}}, {}, {"QGlocke": {"Q223557"}},
        {}, {}, min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-aus-p186"]


def test_verbund_verdraengt_keine_gute_klasse():
    """Die Ueberdeckung darf nicht ueber eine aussortierte Klasse laufen:
    sonst nimmt die Bruecke (Verbund, 500 Belege) die Glocke mit."""
    nach_klasse = {"QStahl": {"QBruecke": objekte(500),
                              "QGlocke": objekte(20, "Q8")}}
    rollen = {"QBruecke": {"Q12280"}}
    oberklassen = {"QGlocke": {"QBruecke"}}   # konstruiert, aber genau der Fall
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, rollen,
                                             oberklassen, {}, min_belege=3,
                                             min_sprachen=0)
    nach_art = {b["befund"]: b["ziel_qid"] for b in treffer}
    assert nach_art == {"p366-verbund": "QBruecke",
                        "p366-aus-p186": "QGlocke"}


def test_bauwerk_selbst_gilt_als_verbund():
    """Bauwerk haengt UEBER den Verbundwurzeln, nicht unter ihnen - die
    Subtree-Pruefung findet es nicht, der exakte Vergleich schon."""
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QSchmiedeeisen": {"Q811979": objekte(86)}}, {}, {}, {}, {},
        min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-verbund"]


@pytest.mark.parametrize("klasse", sorted(anwendung.TEILWERKSTOFF_KLASSEN))
def test_kuratierte_teilwerkstoff_klassen(klasse):
    """Gemaelde und Kleidung sind keine Gebaeude - die Hierarchie faengt sie
    nicht, die Liste schon. Der Grund steht in der Zeile."""
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QMetall": {klasse: objekte(300)}}, {}, {}, {}, {},
        min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-verbund"]
    assert anwendung.TEILWERKSTOFF_KLASSEN[klasse] in treffer[0]["begruendung"]


def test_taetigkeit_taugt_nicht_als_abgeleitete_verwendung():
    """Die Kandidaten kommen aus dem P31 von Gegenstaenden. Steht dort eine
    Taetigkeit, ist die P31-Aussage falsch - kein Vorschlag daraus."""
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QMetall": {"QMetallverarbeitung": objekte(36)}}, {},
        {"QMetallverarbeitung": {"Q1914636", "Q3249551"}}, {}, {},
        min_belege=3, min_sprachen=0)
    assert treffer == []


def test_taetigkeit_die_auch_gegenstand_ist_bleibt_kandidat():
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QMetall": {"QMokumeGane": objekte(36)}}, {},
        {"QMokumeGane": {"Q1914636", "Q223557"}}, {}, {},
        min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-aus-p186"]


# --- Zu spezielle Klasse --------------------------------------------------

def test_klasse_mit_wenigen_sprachversionen_faellt_raus():
    nach_klasse = {"QBronze": {"QCarteluhr": objekte(57),
                               "QMuenze": objekte(500, "Q8")}}
    sitelinks = {"QCarteluhr": 4, "QMuenze": 129}
    treffer = anwendung.pruefe_p366_aus_p186(nach_klasse, {}, {}, {},
                                             sitelinks, min_belege=3,
                                             min_sprachen=10)
    nach_art = {b["befund"]: b["ziel_qid"] for b in treffer}
    assert nach_art == {"p366-zu-speziell": "QCarteluhr",
                        "p366-aus-p186": "QMuenze"}
    assert "4 Wikipedia-Sprachversionen" in [
        b for b in treffer if b["befund"] == "p366-zu-speziell"][0]["begruendung"]


def test_fehlende_sitelink_angabe_gilt_als_null():
    """Wer die Zahl nicht liefert, hat keine Sprachversionen - nicht
    unendlich viele."""
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QBronze": {"QUnbekannt": objekte(50)}}, {}, {}, {}, {},
        min_belege=3, min_sprachen=10)
    assert [b["befund"] for b in treffer] == ["p366-zu-speziell"]


def test_sprachfilter_abschaltbar():
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QBronze": {"QCarteluhr": objekte(50)}}, {}, {}, {},
        {"QCarteluhr": 4}, min_belege=3, min_sprachen=0)
    assert [b["befund"] for b in treffer] == ["p366-aus-p186"]


def test_verbund_geht_dem_sprachfilter_vor():
    """Beide Gruende treffen zu - gemeldet wird der inhaltliche."""
    treffer = anwendung.pruefe_p366_aus_p186(
        {"QMg": {"QKameraModell": objekte(54)}}, {},
        {"QKameraModell": {"Q11019"}}, {}, {"QKameraModell": 0},
        min_belege=3, min_sprachen=10)
    assert [b["befund"] for b in treffer] == ["p366-verbund"]


# --- Rueckkante P186: der Quantorensprung ---------------------------------

def test_einzelding_ja_klasse_nein():
    p366 = {"QNeusilber": {"QMuenzeKlasse", "QdieseGlocke"}}
    rollen = {"QMuenzeKlasse": {"Q223557"}, "QdieseGlocke": {"Q223557"}}
    einzeln, klassenfall, taetigkeiten = anwendung.pruefe_p186_rueckkante(
        p366, rollen, klassen={"QMuenzeKlasse"}, vorhanden=set())
    assert [b["quickstatements"] for b in einzeln] == [
        "QdieseGlocke\tP186\tQNeusilber"]
    assert [b["quickstatements"] for b in klassenfall] == [
        "QMuenzeKlasse\tP186\tQNeusilber"]
    assert taetigkeiten == 0


def test_taetigkeit_bekommt_keine_rueckkante():
    """Ein Vorgang besteht aus keinem Material - das ist kein fehlendes
    Statement, sondern gar keins."""
    p366 = {"QLot": {"QLoeten"}}
    rollen = {"QLoeten": {"Q1914636", "Q3249551"}}
    einzeln, klassenfall, taetigkeiten = anwendung.pruefe_p186_rueckkante(
        p366, rollen, klassen=set(), vorhanden=set())
    assert (einzeln, klassenfall, taetigkeiten) == ([], [], 1)


def test_taetigkeit_die_auch_ein_ding_ist_zaehlt_als_ding():
    """Mokume-Gane ist Technik UND Objekt - dann gilt die Objektrolle."""
    p366 = {"QLegierung": {"QMokumeGane"}}
    rollen = {"QMokumeGane": {"Q1914636", "Q223557"}}
    einzeln, _, taetigkeiten = anwendung.pruefe_p186_rueckkante(
        p366, rollen, klassen=set(), vorhanden=set())
    assert taetigkeiten == 0
    assert [b["quickstatements"] for b in einzeln] == [
        "QMokumeGane\tP186\tQLegierung"]


def test_vorhandene_rueckkante_wird_nicht_erneut_vorgeschlagen():
    p366 = {"QNeusilber": {"QdieseGlocke"}}
    rollen = {"QdieseGlocke": {"Q223557"}}
    einzeln, klassenfall, _ = anwendung.pruefe_p186_rueckkante(
        p366, rollen, klassen=set(),
        vorhanden={("QdieseGlocke", "QNeusilber")})
    assert (einzeln, klassenfall) == ([], [])


# --- P2079 ----------------------------------------------------------------

def test_p2079_wird_nur_ohne_eigenen_wert_vorgeschlagen():
    p2079 = {"QStahl": {"QStahlerzeugung"}, "QEdelstahl": {"QAVerfahren"}}
    eltern = {"QAustenitstahl": {"QStahl"}, "QEdelstahl": {"QStahl"}}
    treffer = anwendung.pruefe_p2079_vererbt(
        ["QAustenitstahl", "QEdelstahl"], p2079, eltern)
    assert [b["qid"] for b in treffer] == ["QAustenitstahl"]
    assert treffer[0]["quickstatements"] == "QAustenitstahl\tP2079\tQStahlerzeugung"


def test_verfahren_als_p366_wird_zur_frage_nicht_zur_aussage():
    p366 = {"QOsemund": {"QOsemundverfahren"}}
    rollen = {"QOsemundverfahren": {"Q1408657"}}
    treffer = anwendung.pruefe_p366_verfahren(p366, rollen)
    assert len(treffer) == 1
    # Umbuchung: neue P2079-Zeile UND Loeschung der alten P366-Aussage.
    assert treffer[0]["quickstatements"].splitlines() == [
        "QOsemund\tP2079\tQOsemundverfahren",
        "-QOsemund\tP366\tQOsemundverfahren",
    ]


def test_verfahren_das_auch_ein_ding_ist_bleibt_unangetastet():
    p366 = {"QLegierung": {"QMokumeGane"}}
    rollen = {"QMokumeGane": {"Q2695280", "Q223557"}}
    assert anwendung.pruefe_p366_verfahren(p366, rollen) == []


# --- Entwurfsdatei: die Sicherheitszusage ---------------------------------

def test_nur_abschnitt_eins_ist_ausfuehrbar(tmp_path):
    """Die Datei muss sich komplett kopieren lassen, ohne dass aus einer
    Meldezeile versehentlich eine Aussage wird."""
    befunde = (
        anwendung.pruefe_p366_aus_p186(
            {"QBronze": {"QSkulptur": objekte(100),
                         "QStatue": objekte(30, "Q8")}},
            {}, {}, {"QStatue": {"QSkulptur"}}, {}, min_belege=3,
            min_sprachen=0)
        + anwendung.pruefe_p2079_vererbt(
            ["QAustenitstahl"], {"QStahl": {"QStahlerzeugung"}},
            {"QAustenitstahl": {"QStahl"}})
        + anwendung.pruefe_p366_verfahren(
            {"QOsemund": {"QOsemundverfahren"}}, {"QOsemundverfahren": {"Q1408657"}})
    )
    pfad = tmp_path / "entwurf.txt"
    anwendung.schreibe_quickstatements(befunde, str(pfad), "legierungen", 3,
                                       {}, vorsichtig=False)
    text = pfad.read_text(encoding="utf-8")

    marke = text.index("# ABSCHNITT 2:")
    kopf, rest = text[:marke], text[marke:]
    assert [z for z in kopf.splitlines()
            if z and not z.startswith("#")] == ["QBronze\tP366\tQSkulptur"]
    assert all(z.startswith("#") for z in rest.splitlines() if z)


def test_vorsichtig_laesst_keine_ausfuehrbare_zeile_uebrig(tmp_path):
    befunde = anwendung.pruefe_p366_aus_p186(
        {"QBronze": {"QSkulptur": objekte(100)}}, {}, {}, {}, {},
        min_belege=3, min_sprachen=0)
    pfad = tmp_path / "entwurf.txt"
    anwendung.schreibe_quickstatements(befunde, str(pfad), "legierungen", 3,
                                       {}, vorsichtig=True)
    text = pfad.read_text(encoding="utf-8")
    assert [z for z in text.splitlines() if z and not z.startswith("#")] == []
