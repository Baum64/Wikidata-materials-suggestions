"""Crystallography Open Database: gemessene Strukturen, CC0.

Primaere Quelle fuer Raumgruppe, Punktgruppe, Kristallsystem und COD-ID -
CC0 statt CC BY, gemessen statt gerechnet, und belegt mit der DOI der
ORIGINALARBEIT statt mit der Datenbank. Wie die Modifikation gewaehlt wird
(Mehrheit ueber alle Treffer, nicht Jahrgang): README, "Quellenkaskade".
"""

import collections
import re
import sys
from typing import Optional

import requests

from .. import netz, wikidata
from ..ausgabe import Reference, make_row
from ..formeln import parse_formula
from ..properties import NUR_FESTKOERPER, PROPERTY_MAP
from .mp import verfeinere_zentrierung

# ---------------------------------------------------------------------------
# Crystallography Open Database (COD) - primaere Strukturquelle
# ---------------------------------------------------------------------------
#
# Warum COD vor dem Materials Project steht (CC0 statt CC BY, DOI der
# Originalarbeit statt Sammel-DOI, gemessen statt gerechnet) und wie die
# Modifikation gewaehlt wird: README, "Quellenkaskade". MP bleibt Fallback.
#
# Kein API-Schluessel noetig; dokumentierte RESTful-API
# (https://wiki.crystallography.net/RESTful_API/, geprueft am 2026-08-16).
COD_API = "https://www.crystallography.net/cod/result"
COD_ENTRY_URL = "https://www.crystallography.net/cod/{cod_id}.html"

def cod_hill_formula(formula: str) -> Optional[str]:
    """Summenformel -> Hill-Notation, wie die COD-Suche sie verlangt.

    COD sortiert STRIKT nach Hill: Kohlenstoff zuerst, dann Wasserstoff,
    dann alle uebrigen alphabetisch; ohne Kohlenstoff rein alphabetisch.
    Elemente durch Leerzeichen getrennt, die Anzahl direkt am Symbol.
    Die Reihenfolge ist nicht kosmetisch - "Ti O2" liefert NULL Treffer,
    "O2 Ti" deren 39 (am 2026-08-16 geprueft).
    """
    zusammensetzung = parse_formula(formula)
    if not zusammensetzung:
        return None
    rest = sorted(el for el in zusammensetzung if el not in ("C", "H"))
    reihenfolge = ([el for el in ("C", "H") if el in zusammensetzung] + rest
                   if "C" in zusammensetzung else
                   sorted(zusammensetzung))
    return " ".join(
        el + ("" if zusammensetzung[el] == 1 else str(zusammensetzung[el]))
        for el in reihenfolge
    )


def fetch_cod_entries(element_symbol: Optional[str] = None,
                      formula: Optional[str] = None,
                      max_entries: int = 20) -> list:
    """Strukturen aus der COD holen.

    Bei element_symbol wird auf den REINEN Stoff eingegrenzt (strictmin=
    strictmax=1, also genau ein Element) - sonst liefert el1=Cu auch jede
    kupferhaltige Organometallverbindung.

    include_duplicates/include_errors werden NICHT gesetzt; COD liefert dann
    nur die bereinigten Eintraege.
    """
    params = {"format": "json"}
    if element_symbol:
        params.update({"el1": element_symbol, "strictmin": 1, "strictmax": 1})
    elif formula:
        hill = cod_hill_formula(formula)
        if not hill:
            return []  # nicht deutbare Formel - lieber nichts als Falsches
        params["formula"] = hill
    else:
        raise ValueError("fetch_cod_entries braucht element_symbol oder formula")

    resp = netz.get_with_retry(COD_API, params)
    try:
        daten = resp.json()
    except ValueError:
        # COD antwortet bei leerer Treffermenge mit einem leeren Rumpf
        return []
    if not isinstance(daten, list):
        return []
    return daten[:max_entries]


def cod_dominante_raumgruppe(entries: list) -> Optional[tuple]:
    """(Raumgruppennummer, Treffer, ausgewertet, eindeutig) ueber alle Eintraege.

    Der juengste Eintrag ist NICHT die uebliche Modifikation. Am Bestand
    geprueft (2026-08-16): fuer Fe2O3 liefert die Wahl nach Jahrgang
    Raumgruppe 15 (monoklin, 2 von 25 Eintraegen), waehrend 13 Eintraege
    Haematit zeigen (167, trigonal). Entschieden wird deshalb nach
    HAEUFIGKEIT - das trifft die Standardmodifikation.

    "eindeutig" ist False, wenn die haeufigste Raumgruppe nicht mindestens
    doppelt so oft vorkommt wie die zweithaeufigste. Dann GIBT es keine
    uebliche Modifikation: TiO2 steht 12:11 zwischen Rutil (136) und Anatas
    (141), und ein Vorschlag waere schlicht geraten.
    """
    zaehler = collections.Counter(
        int(e["sgNumber"]) for e in entries
        if str(e.get("sgNumber") or "").isdigit()
    )
    if not zaehler:
        return None
    haeufigste = zaehler.most_common(2)
    nummer, anzahl = haeufigste[0]
    zweite = haeufigste[1][1] if len(haeufigste) > 1 else 0
    return (nummer, anzahl, sum(zaehler.values()), anzahl >= 2 * zweite)


def cod_best_entry(entries: list, sg_number: Optional[int] = None) -> Optional[dict]:
    """Der belastbarste Eintrag einer Trefferliste.

    Rangfolge: Eintrag mit DOI schlaegt Eintrag ohne (nur mit DOI laesst sich
    die Originalarbeit als Beleg setzen), danach der juengere Jahrgang,
    zuletzt die kleinere COD-ID. Das letzte Kriterium ist kein Geschmack,
    sondern Reproduzierbarkeit: ohne es haengt bei Gleichstand davon ab, in
    welcher Reihenfolge die API antwortet, und zwei Laeufe schlagen
    verschiedene Strukturen fuer denselben Stoff vor.

    Mit `sg_number` wird auf eine Raumgruppe eingeschraenkt - so gehoeren
    die vorgeschlagene COD-ID und die vorgeschlagene Raumgruppe zur selben
    Struktur und nicht zu zwei verschiedenen Modifikationen.

    Duplikate und als fehlerhaft markierte Eintraege fliegen vorher raus.
    """
    brauchbar = [
        e for e in entries
        if not e.get("duplicateof") and (e.get("status") or "").lower() not in
        {"retracted", "errors"}
    ]
    if sg_number is not None:
        brauchbar = [e for e in brauchbar
                     if str(e.get("sgNumber") or "") == str(sg_number)]
    if not brauchbar:
        return None

    def rang(e):
        jahr = int(e["year"]) if str(e.get("year") or "").isdigit() else 0
        cod_id = int(e["file"]) if str(e.get("file") or "").isdigit() else 0
        return (1 if e.get("doi") else 0, jahr, -cod_id)

    return max(brauchbar, key=rang)


def cod_proposals_for_item(wd_match: dict, entries: list,
                           skip_pids: Optional[set] = None) -> list:
    """Vorschlagszeilen aus den COD-Treffern: COD-ID, Raumgruppe,
    Kristallsystem.

    Bekommt bewusst die GANZE Trefferliste, nicht einen Eintrag: welche
    Raumgruppe die uebliche ist, entscheidet die Haeufigkeit ueber alle
    Treffer (siehe cod_dominante_raumgruppe). Ein einzelner Eintrag waere
    eine beliebige Modifikation.

    Gitterparameter (a, b, c und die Winkel) liefert COD zwar mit, aber
    Wikidata hat dafuer keine Property - am 2026-08-16 gesucht, es gibt
    weder "lattice constant" noch "unit cell". Sie bleiben deshalb aussen
    vor; der eigentliche Strukturinhalt laesst sich nicht eintragen.
    """
    skip_pids = skip_pids or set()
    if not entries:
        return []

    mehrheit = cod_dominante_raumgruppe(entries)
    nummer = mehrheit[0] if mehrheit else None
    eindeutig = mehrheit[3] if mehrheit else False
    # Eintrag aus der dominanten Raumgruppe, damit COD-ID und Raumgruppe
    # dieselbe Struktur meinen.
    entry = cod_best_entry(entries, sg_number=nummer if eindeutig else None)
    if entry is None:
        entry = cod_best_entry(entries)
    if entry is None:
        return []
    cod_id = str(entry.get("file") or "").strip()
    if not cod_id:
        return []

    # Beleg: die Originalarbeit, nicht die Datenbank. Genau das ist der
    # Grund, COD dem Materials Project vorzuziehen.
    quelle_text = ", ".join(
        t for t in (
            entry.get("journal"), str(entry.get("year") or "") or None,
            f"Methode: {entry['method']}" if entry.get("method") else None,
            f"T = {entry['celltemp']} K" if entry.get("celltemp") else None,
        ) if t
    )
    note = f"COD {cod_id}" + (f"; {quelle_text}" if quelle_text else "")
    if entry.get("doi"):
        reference = Reference(doi=entry["doi"], note=note)
    else:
        reference = Reference(url=COD_ENTRY_URL.format(cod_id=cod_id), note=note)

    # Gemessen, nicht gerechnet - der P459-Qualifikator der MP-Zeilen
    # ("berechnet (DFT)") waere hier schlicht falsch und entfaellt.
    proposals = []

    # Ist der Stoff bei 20 C ein Gas, hat er keine Kristallstruktur - die
    # COD-Eintraege beschreiben dann die Tieftemperaturphase.
    gasfoermig = wikidata.ist_bei_raumtemperatur_gas(wd_match["qid"])

    def anfuegen(internal_key, value, value_label="", status=None):
        prop_info = PROPERTY_MAP[internal_key]
        if prop_info["pid"] in skip_pids:
            return
        if gasfoermig and internal_key in NUR_FESTKOERPER:
            return
        if status is None:
            status = ("BEREITS_VORHANDEN"
                      if wikidata.item_has_statement(wd_match["qid"], prop_info["pid"])
                      else "VORSCHLAG")
        proposals.append(make_row(
            status, "COD", wd_match, prop_info, value, value_label,
            reference, formula=(entry.get("formula") or "").strip("- ").strip(),
            entry_id=f"cod-{cod_id}", qualifiers=[],
        ))

    anfuegen("cod_id", cod_id)

    if nummer is None:
        return proposals

    raumgruppen = wikidata.fetch_space_group_qids()
    sg = raumgruppen.get(nummer)
    if sg is None:
        return proposals

    # Keine deutliche Mehrheit heisst: der Stoff hat mehrere gaengige
    # Modifikationen (TiO2 = Rutil ODER Anatas). Dann wird nichts
    # vorgeschlagen, sondern zur Klaerung markiert - raten waere schlimmer.
    _, anzahl, gesamt, _ = mehrheit
    klaerung = None if eindeutig else (
        f"MANUELLE_KLAERUNG_NOETIG (keine eindeutige Modifikation: "
        f"Raumgruppe {nummer} nur in {anzahl} von {gesamt} COD-Eintraegen)"
    )
    anfuegen("space_group", sg["qid"], sg["label"], status=klaerung)

    # Die Punktgruppe folgt zwingend aus der Raumgruppe - jede der 230 gehoert
    # zu genau einer der 32. Sie wird deshalb mit DERSELBEN Quelle belegt und
    # traegt denselben Klaerungsvermerk: ist die Modifikation offen, ist es
    # die Punktgruppe auch.
    if sg["pg_qid"]:
        anfuegen("point_group", sg["pg_qid"], sg["pg_label"], status=klaerung)

    # Kristallsystem: bevorzugt am Raumgruppen-Item abgelesen, sonst ueber
    # die normativen Nummernbereiche. Anschliessend wie bei MP auf fcc/bcc
    # verfeinert, wo das Hermann-Mauguin-Symbol die Zentrierung hergibt.
    cs_qid, cs_label = sg["cs_qid"], sg["cs_label"]
    if not cs_qid:
        name = wikidata.kristallsystem_aus_nummer(nummer)
        mapped = PROPERTY_MAP["crystal_system"]["value_map"].get(name)
        if mapped:
            cs_qid, cs_label = mapped
    if cs_qid:
        verfeinert = verfeinere_zentrierung(
            _cs_name_aus_qid(cs_qid), entry.get("sg"))
        mapped = PROPERTY_MAP["crystal_system"]["value_map"].get(verfeinert)
        if mapped:
            cs_qid, cs_label = mapped
        anfuegen("crystal_system", cs_qid, cs_label, status=klaerung)
    return proposals


def _cs_name_aus_qid(qid: str) -> str:
    """QID eines Kristallsystems -> interner Name der value_map."""
    for name, (q, _) in PROPERTY_MAP["crystal_system"]["value_map"].items():
        if q == qid:
            return name
    return ""
