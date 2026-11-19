"""Pruef-Dokument (QuickStatements) und Export - netzfrei."""
from pathlib import Path

import pytest

from pmdmap.assessment import BEHALTEN, NEU_P1709, NEU_P2888, UMSTELLEN, Assessment
from pmdmap.config import load_config
from pmdmap.ontology import load_ontology_file
from pmdmap.qsdoc import (
    QS_LINE, build_document, chunk, line_key, parse_document, parse_line, previous_state, qs_add,
    qs_date, qs_remove, validate, write_export,
)

from test_pmdmap_assessment import CO, TTL

CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"
STEEL = CO + "PMD_0020096"
CRACK = CO + "PMD_0020202"
SRC = "|S248|Q141572184|S813|+2026-11-19T00:00:00Z/11"
ALLOWED = ["Q39893184", "Q39893449", "Q39894604", "Q39894595", "Q39893967"]
LABELS = {"Q39893184": {"en": "close match"}, "Q39893449": {"en": "exact match"},
          "Q39894604": {"en": "related match"}, "Q39894595": {"en": "broad match"},
          "Q39893967": {"en": "narrow match"}}


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    cfg = load_config(CONFIG)
    p = tmp_path_factory.mktemp("onto") / "mini.ttl"
    p.write_text(TTL, encoding="utf-8")
    return cfg, load_ontology_file(p, cfg.profile)


def snapshot(mappings=()):
    return {
        "retrieved": "2026-11-19", "ontology": {"version": "3.1.2", "retrieved": "2026-11-19"},
        "labels": LABELS, "mapping_relation_allowed": ALLOWED, "e1": {"conflicts": []},
        "entities": {"Q3073047": {"label_de": "Riss", "label_en": "crack"},
                     "Q219239": {"label_de": "Kochrezept", "label_en": "recipe"}},
        "mappings": list(mappings),
    }


def mapping(qid, iri, prop="P1709", refs=0):
    return {"entity": qid, "prop": prop, "value": iri, "p4390": [], "references": refs}


# --- Zeilenformat (Pflicht-Test laut Aufgabe) ------------------------------------
def test_qs_zeile_p1709():
    line = qs_add("Q11427", "P1709", STEEL, "Q141572184", "2026-11-19")
    assert line == 'Q11427|P1709|"https://w3id.org/pmd/co/PMD_0020096"' + SRC
    assert QS_LINE.match(line)


def test_qs_zeile_p2888_mit_p4390():
    line = qs_add("Q1", "P2888", STEEL, "Q141572184", "2026-11-19", "Q39893184")
    assert line == 'Q1|P2888|"https://w3id.org/pmd/co/PMD_0020096"|P4390|Q39893184' + SRC
    p = parse_line(line)
    assert p.qualifiers == {"P4390": "Q39893184"}
    assert p.sources == {"S248": "Q141572184", "S813": "+2026-11-19T00:00:00Z/11"}


def test_qs_loeschzeile():
    assert qs_remove("Q1", "P1709", STEEL) == '-Q1|P1709|"https://w3id.org/pmd/co/PMD_0020096"'
    assert parse_line(qs_remove("Q1", "P1709", STEEL)).remove


def test_qs_datum():
    assert qs_date("2026-11-19") == "+2026-11-19T00:00:00Z/11"
    with pytest.raises(ValueError):
        qs_date("19.11.2026")


# --- Dokument lesen -------------------------------------------------------------
def test_kommentare_und_aktive_zeilen():
    text = "\n".join([
        "## Erläuterung Q1|P1709|\"x\"",          # nie eine Zeile, auch wenn es so aussieht
        'Q1|P1709|"' + STEEL + '"' + SRC,
        '#Q2|P1709|"' + STEEL + '"' + SRC,
        '# -Q3|P1709|"' + STEEL + '"',           # Leerzeichen nach # erlaubt
        "Tippfehler ohne Raute",
        "",
    ])
    lines, junk = parse_document(text)
    assert [(p.subject, p.active) for p in lines] == [("Q1", True), ("Q2", False), ("Q3", False)]
    assert junk and "Zeile 5" in junk[0]


def test_line_key_ohne_quellen():
    a = qs_add("Q1", "P1709", STEEL, "Q141572184", "2026-11-19")
    b = qs_add("Q1", "P1709", STEEL, "Q141572184", "2026-12-01")
    assert line_key(a) == line_key(b)


# --- Dokument bauen ---------------------------------------------------------------
def test_dokument_aktiv_nur_sicheres(env):
    cfg, onto = env
    snap = snapshot([mapping("Q219239", STEEL, refs=1), mapping("Q3073047", CRACK)])
    a_umst = Assessment(UMSTELLEN, "Q39894595", [], "Regel: x | Einschätzung: y", False, BEHALTEN)
    a_keep = Assessment(BEHALTEN, "", [], "Regel: ok", False, BEHALTEN)
    text, stats = build_document(cfg, onto, snap, [(snap["mappings"][0], a_umst), (snap["mappings"][1], a_keep)],
                                 None, [], {})
    lines, junk = parse_document(text)
    assert not junk
    assert stats["active"] == 0                        # nur Paket 0 -> alles auskommentiert
    assert any(p.remove and p.subject == "Q219239" for p in lines)
    assert "1 Quelle(n) – sie gehen mit dem Löschen verloren" in text
    assert any(not p.remove and p.qualifiers.get("P4390") == "Q39894595" for p in lines)


def test_dokument_behaelt_stand_der_vorigen_fassung(env, tmp_path):
    cfg, onto = env
    snap = snapshot([mapping("Q219239", STEEL)])
    a = Assessment(UMSTELLEN, "Q39894595", [], "Regel: x", False, BEHALTEN)
    text, _ = build_document(cfg, onto, snap, [(snap["mappings"][0], a)], None, [], {})
    # Nutzer aktiviert beide Zeilen der Umstellung
    edited = "\n".join(l[1:] if l.startswith("#") and not l.startswith("##") else l for l in text.splitlines())
    doc = tmp_path / "quickstatements.txt"
    doc.write_text(edited, encoding="utf-8")
    text2, stats = build_document(cfg, onto, snap, [(snap["mappings"][0], a)], None, [], previous_state(doc))
    assert stats["active"] == 2 and stats["orphans"] == 0
    assert sum(p.active for p in parse_document(text2)[0]) == 2


def test_aktive_zeile_ohne_vorschlag_bleibt_auskommentiert_erhalten(env, tmp_path):
    """Die Datei wird als Ganzes eingefuegt - eine nicht mehr vorgeschlagene
    Zeile darf nicht unbemerkt aktiv bleiben, aber auch nicht verschwinden."""
    cfg, onto = env
    doc = tmp_path / "quickstatements.txt"
    doc.write_text('Q999|P1709|"' + STEEL + '"' + SRC + "\n", encoding="utf-8")
    text, stats = build_document(cfg, onto, snapshot(), [], None, [], previous_state(doc))
    assert stats["orphans"] == 1 and stats["active"] == 0
    assert '#Q999|P1709|"' + STEEL + '"' + SRC in text.splitlines()


def test_ganze_datei_einfuegen_nur_gueltige_aktive_zeilen(env):
    """So wie QuickStatements sie sieht: #-Zeilen weg, Rest muss gueltig sein."""
    cfg, onto = env
    snap = snapshot([mapping("Q219239", STEEL, refs=1), mapping("Q3073047", CRACK)])
    a1 = Assessment(UMSTELLEN, "Q39894595", [], "Regel: x", False, BEHALTEN)
    a2 = Assessment(BEHALTEN, "", [], "Regel: ok", False, BEHALTEN)
    cands = {"classes": {STEEL: {"pilot": {"paket": "1", "label": "steel", "iri": STEEL, "reason": "x",
                                           "hint": "", "linked": []}, "candidates": [], "properties": []}},
             "entities": {"Q11427": {"label_de": "Stahl"}}, "labels": {}, "missing": {"1": ["wood"]}}
    text, _ = build_document(cfg, onto, snap, [(snap["mappings"][0], a1), (snap["mappings"][1], a2)], cands,
                             [(cands["classes"][STEEL]["pilot"], "Q11427",
                               Assessment(NEU_P1709, "", [], "Regel: ok", False, NEU_P1709))], {})
    seen_by_qs = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    assert seen_by_qs == ['Q11427|P1709|"' + STEEL + '"' + SRC]
    assert all(QS_LINE.match(l) for l in seen_by_qs)


def test_kandidat_sicher_nur_wenn_regel_und_einschaetzung_gleich(env):
    cfg, onto = env
    cands = {"classes": {STEEL: {"pilot": {"paket": "1", "label": "steel", "iri": STEEL, "reason": "x",
                                           "hint": "", "linked": []}, "candidates": [], "properties": []}},
             "entities": {"Q11427": {"label_de": "Stahl"}, "Q5": {"label_de": "X"}}, "labels": {}, "missing": {}}
    sicher = Assessment(NEU_P1709, "", [], "Regel: ok", False, NEU_P1709)
    geaendert = Assessment(NEU_P1709, "", [], "Regel: offen | Einschätzung: doch", False, "offen")
    text, stats = build_document(cfg, onto, snapshot(), [], cands,
                                 [(cands["classes"][STEEL]["pilot"], "Q11427", sicher),
                                  (cands["classes"][STEEL]["pilot"], "Q5", geaendert)], {})
    act = {p.subject: p.active for p in parse_document(text)[0]}
    assert act == {"Q11427": True, "Q5": False}


# --- Export-Pruefung ------------------------------------------------------------------
def pruefe(env, zeilen, mappings=()):
    cfg, onto = env
    lines, _ = parse_document("\n".join(zeilen))
    return validate(lines, cfg, onto, snapshot(mappings), None)


def test_gueltiger_export_ohne_befund(env):
    r = pruefe(env, [qs_add("Q11427", "P1709", STEEL, "Q141572184", "2026-11-19")])
    assert not r.errors and not r.warnings


@pytest.mark.parametrize("zeile, fehler", [
    ('Q1|P2888|"' + STEEL + '"' + SRC, "ohne P4390"),
    ('Q1|P1709|"' + STEEL + '"|P4390|Q39893184' + SRC, "P1709 ohne P4390"),
    ('Q1|P2888|"' + STEEL + '"|P4390|Q1' + SRC, "nicht erlaubt"),
    ('Q1|P1709|"https://w3id.org/pmd/co/Steel"' + SRC, "keine PMDco-Klassen-IRI"),
    ('Q1|P1709|"' + CO + 'PMD_0000825"' + SRC, "veraltet"),
    ('Q1|P1709|"' + STEEL + '"', "Quelle fehlt"),
    ('P2054|P1709|"' + STEEL + '"' + SRC, "P1709 gehört an einen Eintrag"),
    ('Q1|P1628|"' + STEEL + '"' + SRC, "P1628 gehört an eine Wikidata-Eigenschaft"),
    ('-Q1|P1709|"' + STEEL + '"|P4390|Q39893184', "Löschzeile mit Qualifiern"),
])
def test_export_fehler(env, zeile, fehler):
    r = pruefe(env, [zeile])
    assert any(fehler in e for e in r.errors), r.errors


def test_doppelte_aktive_zeile(env):
    line = qs_add("Q1", "P1709", STEEL, "Q141572184", "2026-11-19")
    assert any("2× aktiv" in e for e in pruefe(env, [line, line]).errors)


def test_hinweise_loeschen_mit_quelle_und_doppeltes_p1709(env):
    r = pruefe(env, [qs_remove("Q219239", "P1709", STEEL),
                     qs_add("Q219239", "P2888", STEEL, "Q141572184", "2026-11-19", "Q39894595"),
                     qs_add("Q5", "P1709", CRACK, "Q141572184", "2026-11-19")],
               mappings=[mapping("Q219239", STEEL, refs=2), mapping("Q5", CO + "PMD_0000100")])
    assert not r.errors
    assert any("2 Quelle(n)" in w for w in r.warnings)
    assert any("Q5 hätte 2× P1709" in w for w in r.warnings)


def test_halbe_umstellung_meldet(env):
    r = pruefe(env, [qs_remove("Q219239", "P1709", STEEL)], mappings=[mapping("Q219239", STEEL)])
    assert any("ohne neue Zeile" in w for w in r.warnings)


def test_vorhandene_aussage_nur_hinweis(env):
    r = pruefe(env, [qs_add("Q3073047", "P1709", CRACK, "Q141572184", "2026-11-19")],
               mappings=[mapping("Q3073047", CRACK)])
    assert not r.errors and any("existiert schon" in w for w in r.warnings)


# --- Ausgabe --------------------------------------------------------------------------
def test_bloecke_trennen_umstellung_nie():
    units = [["a"]] * 49 + [["-x", "y"]]
    parts = chunk(units, 50)
    assert [len(p) for p in parts] == [49, 2]


def test_export_dateien_ohne_kommentare(env, tmp_path):
    zeilen = [qs_add(f"Q{i}", "P1709", STEEL, "Q141572184", "2026-11-19") for i in range(1, 56)]
    zeilen += [qs_remove("Q900", "P1709", CRACK), qs_add("Q900", "P2888", CRACK, "Q141572184", "2026-11-19", "Q39893184"),
               qs_add("P2054", "P1628", CO + "PMD_0000597", "Q141572184", "2026-11-19"),
               "#" + qs_add("Q999", "P1709", STEEL, "Q141572184", "2026-11-19"), "## Erklärung"]
    (tmp_path / "qs_neu_part09.txt").write_text("alt", encoding="utf-8")      # alter Rest
    (tmp_path / "qs_neu_part01.qs").write_text("alt", encoding="utf-8")       # fruehere Endung
    files = write_export(parse_document("\n".join(zeilen))[0], tmp_path, "2026-11-19", "PMDco")
    names = sorted(f.name for f in files)
    assert names == ["manuell_eigenschaften.md", "qs_eigenschaften_part01.txt", "qs_neu_part01.txt",
                     "qs_neu_part02.txt", "qs_umstellen_part01.txt"]
    assert not (tmp_path / "qs_neu_part09.txt").exists() and not (tmp_path / "qs_neu_part01.qs").exists()
    neu1 = (tmp_path / "qs_neu_part01.txt").read_text(encoding="utf-8").splitlines()
    assert len(neu1) == 50 and not any(l.startswith("#") or not l for l in neu1)
    assert (tmp_path / "qs_umstellen_part01.txt").read_text(encoding="utf-8").splitlines()[0].startswith("-Q900")
    assert "Q999" not in "".join(f.read_text(encoding="utf-8") for f in files)
    assert "Property:P2054" in (tmp_path / "manuell_eigenschaften.md").read_text(encoding="utf-8")
