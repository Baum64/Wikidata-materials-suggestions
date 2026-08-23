"""NIST Chemistry WebBook: Bildungsenthalpie und Standardentropie.

Der Beleg ist NIE das WebBook: NIST-Standardreferenzdaten sind nach dem
Standard Reference Data Act urheberrechtlich geschuetzt. Zitiert wird die
Originalarbeit, der das WebBook den Wert zuschreibt (JANAF bzw. CODATA);
Werte ohne solche Zuschreibung werden uebergangen und gemeldet.
"""

import collections
import html as htmlmodul
import re
import sys
import time
from typing import Optional

from .. import netz, wikidata
from ..ausgabe import Reference, make_row, round_significant
from ..formeln import parse_formula
from ..properties import (
    AGGREGAT_FEST, AGGREGAT_FLUESSIG, AGGREGAT_GAS, AGGREGAT_PID,
    PROPERTY_MAP, ist_plausibel,
)

# ---------------------------------------------------------------------------
# NIST Chemistry WebBook: Bildungsenthalpie und Standardentropie
# ---------------------------------------------------------------------------
#
# Zwei Groessen, die keine andere Quelle hier liefert: ΔfH° (P3078) und S°
# (P3071), je Aggregatzustand. Gesucht wird ueber die CAS-Nummer am Item.
#
# WICHTIG - warum NICHT das WebBook selbst als Beleg dasteht: NIST-
# Standardreferenzdaten sind nach dem Standard Reference Data Act
# (15 U.S.C. 290e) urheberrechtlich geschuetzt ("All rights reserved"), anders
# als sonstige US-Bundeswerke. Uebernommen wird deshalb nur, was das WebBook
# einer ZITIERBAREN Originalarbeit zuschreibt, und belegt wird mit dieser
# Arbeit - dieselbe Linie wie bei COD (DOI der Originalarbeit statt der
# Datenbank). Das WebBook bleibt Fundstelle in der Notiz. Lizenz, Abdeckung
# und Grenzen: README, "NIST Chemistry WebBook".
NIST_WEBBOOK = "https://webbook.nist.gov/cgi/cbook.cgi"
# robots.txt des WebBook verlangt Crawl-delay: 5 (geprueft 2026-08-23).
NIST_DELAY_SEC = 5.0
_NIST_LETZTE_ANFRAGE = 0.0

# Quellenkuerzel des WebBook -> zitierbare Originalarbeit. NUR was hier steht,
# wird uebernommen; alles andere waere ein Wert ohne Beleg. Beide ISBNs am
# 2026-08-23 ueber OpenLibrary geprueft: Titel, Jahr und Seitenzahl stimmen
# mit der Zitation des WebBook ueberein.
NIST_QUELLEN = {
    # "Monograph 9, 1998, 1-1951" - OpenLibrary loest die ISBN auf ebendiese
    # 1951 Seiten der Reihe "J. Phys. Chem. Ref. Data, no. 9" auf. Es gibt
    # drei ISBNs (Gesamtwerk und die beiden Teile), alle mit demselben Titel.
    "Chase, 1998": {
        "isbn": "978-1-56396-820-4",
        "werk": "Chase, NIST-JANAF Thermochemical Tables, 4. Aufl., "
                "J. Phys. Chem. Ref. Data Monograph 9 (1998)",
    },
    # Das WebBook datiert auf 1984 (CODATA-Bericht), das gedruckte Werk
    # erschien 1989 bei Hemisphere - die ISBN gehoert zu diesem Buch.
    "Cox, Wagman, et al., 1984": {
        "isbn": "0-89116-758-7",
        "werk": "Cox/Wagman/Medvedev, CODATA Key Values for Thermodynamics, "
                "Hemisphere (1989)",
    },
}
# Reihenfolge bei mehreren Quellen: die CODATA-Schluesselwerte sind die
# international abgestimmten, JANAF die breitere Sammlung.
NIST_QUELLEN_RANG = ["Cox, Wagman, et al., 1984", "Chase, 1998"]

# Groesse im WebBook -> (interner Schluessel, Aggregatzustand-QID).
# "S°gas,1 bar" und "S°solid,1 bar" nennen bloss die Standardbedingung mit.
NIST_GROESSEN = {
    "ΔfH°solid": ("formation_enthalpy", AGGREGAT_FEST),
    "ΔfH°liquid": ("formation_enthalpy", AGGREGAT_FLUESSIG),
    "ΔfH°gas": ("formation_enthalpy", AGGREGAT_GAS),
    "S°solid": ("molar_entropy", AGGREGAT_FEST),
    "S°liquid": ("molar_entropy", AGGREGAT_FLUESSIG),
    "S°gas": ("molar_entropy", AGGREGAT_GAS),
}
NIST_EINHEITEN = {"formation_enthalpy": "kJ/mol", "molar_entropy": "J/mol*K"}
# Zwei Messreihen gelten als vertraeglich, wenn sie sich um weniger als
# diesen Anteil unterscheiden. Darueber wird nichts vorgeschlagen.
NIST_TOLERANZ = 0.01

_NIST_UNBEKANNTE_QUELLEN = collections.Counter()


def nist_fetch(cas: str, mask: str):
    """Rohes HTML einer WebBook-Seite, oder None.

    Die CAS-Nummer wird zur WebBook-ID: 7440-50-8 -> C7440508.
    """
    global _NIST_LETZTE_ANFRAGE
    wait = NIST_DELAY_SEC - (time.monotonic() - _NIST_LETZTE_ANFRAGE)
    if wait > 0:
        time.sleep(wait)
    _NIST_LETZTE_ANFRAGE = time.monotonic()
    resp = netz.request_with_retry("GET", NIST_WEBBOOK, params={
        "ID": "C" + re.sub(r"[^0-9]", "", cas), "Units": "SI", "Mask": mask,
    })
    if resp.status_code != 200:
        return None
    return resp.text


_NIST_ZELLE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_NIST_ZEILE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_NIST_TABELLE = re.compile(r"<table[^>]*>(.*?)</table>", re.S)
_NIST_FORMEL = re.compile(r'"molecularFormula"\s*:\s*"([^"]+)"')


def nist_tabellenzeilen(html: str) -> list:
    """[(Groesse, Wert, Einheit, Methode, Quelle)] aus den Datentabellen."""
    zeilen = []
    for tabelle in _NIST_TABELLE.findall(html):
        for zeile in _NIST_ZEILE.findall(tabelle):
            spalten = [
                htmlmodul.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", z))).strip()
                for z in _NIST_ZELLE.findall(zeile)
            ]
            if len(spalten) >= 5 and spalten[0] and spalten[0] != "Quantity":
                zeilen.append(tuple(spalten[:5]))
    return zeilen


def nist_wert(roh: str) -> Optional[tuple]:
    """"-241.826 ± 0.040" -> (-241.826, 0.040); ohne Streuung (wert, None)."""
    s = roh.replace("&plusmn;", "±").replace("−", "-")
    treffer = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:±\s*(\d+(?:\.\d+)?))?\s*$", s)
    if not treffer:
        return None
    return (float(treffer.group(1)),
            float(treffer.group(2)) if treffer.group(2) else None)


def nist_thermodaten(cas: str, formel: str = "") -> dict:
    """{(Schluessel, Zustand-QID): [(Wert, Streuung, Quellenkuerzel)]}.

    Holt Gas- und Kondensatseite. Ist am Item eine Summenformel bekannt und
    laesst sich die des WebBook deuten, wird gegengeprueft - eine CAS-Nummer
    kann am falschen Item stehen, die Zusammensetzung luegt nicht.
    """
    out = collections.defaultdict(list)
    eigene = parse_formula(formel) if formel else None
    # Mask ist eine Bitmaske: 1 = Gasphase, 2 = kondensierte Phase. 3 liefert
    # BEIDE Abschnitte in einer Antwort. Zwei getrennte Abrufe kosteten wegen
    # des Crawl-delay 10 statt 5 Sekunden je Item - an Kupfer geprueft
    # (2026-08-23): Mask=3 enthaelt alle acht Zeilen der beiden Einzelseiten.
    for mask in ("3",):
        html = nist_fetch(cas, mask)
        if not html:
            continue
        gefunden = _NIST_FORMEL.search(html)
        if eigene and gefunden:
            fremd = parse_formula(gefunden.group(1))
            if fremd and fremd != eigene:
                return {}   # CAS zeigt auf einen anderen Stoff
        for groesse, wert, einheit, _methode, quelle in nist_tabellenzeilen(html):
            name = groesse.replace(",1 bar", "").strip()
            eintrag = NIST_GROESSEN.get(name)
            if eintrag is None:
                continue
            schluessel, zustand = eintrag
            if einheit.replace(" ", "") != NIST_EINHEITEN[schluessel]:
                continue   # unerwartete Einheit - nicht umrechnen, sondern lassen
            zahl = nist_wert(wert)
            if zahl is None:
                continue
            out[(schluessel, zustand)].append((zahl[0], zahl[1], quelle.strip()))
    return dict(out)


def nist_proposals_for_item(wd_match: dict, cas: str, formel: str = "",
                            skip_pids: Optional[set] = None) -> list:
    """P3078- und P3071-Vorschlaege aus dem WebBook, belegt mit der
    Originalarbeit.

    Mehrere Quellen zu derselben Groesse: stimmen sie im Rahmen von
    NIST_TOLERANZ ueberein, gilt die im Rang hoechste. Weichen sie ab, wird
    nichts vorgeschlagen, sondern zur Klaerung ausgewiesen - welche Messreihe
    die bessere ist, entscheidet das Werkzeug nicht.
    """
    skip_pids = skip_pids or set()
    if not cas:
        return []
    daten = nist_thermodaten(cas, formel)
    proposals = []
    for (schluessel, zustand), werte in sorted(daten.items()):
        prop_info = PROPERTY_MAP[schluessel]
        if prop_info["pid"] in skip_pids:
            continue
        zustand_text = {AGGREGAT_FEST: "fest", AGGREGAT_FLUESSIG: "fluessig",
                        AGGREGAT_GAS: "gasfoermig"}[zustand]
        qualifiers = [(AGGREGAT_PID, zustand, zustand_text)]

        # Nur Werte mit zitierbarer Originalarbeit - siehe NIST_QUELLEN.
        belegbar = [w for w in werte if w[2] in NIST_QUELLEN]
        for _, _, quelle in werte:
            if quelle not in NIST_QUELLEN:
                _NIST_UNBEKANNTE_QUELLEN[quelle] += 1
        if not belegbar:
            continue

        zahlen = [w[0] for w in belegbar]
        spanne = max(zahlen) - min(zahlen)
        bezug = max(abs(z) for z in zahlen) or 1.0
        if spanne / bezug > NIST_TOLERANZ:
            proposals.append(make_row(
                f"MANUELLE_KLAERUNG_NOETIG (Quellen uneinig: "
                f"{', '.join(f'{w[0]:g} ({w[2]})' for w in belegbar)} "
                f"{NIST_EINHEITEN[schluessel]}, {zustand_text})",
                "NIST WebBook", wd_match, prop_info, round_significant(zahlen[0]),
                "", Reference(url=f"{NIST_WEBBOOK}?ID=C{re.sub(r'[^0-9]', '', cas)}",
                              note=f"NIST Chemistry WebBook, CAS {cas} - "
                                   f"Quellen uneinig"),
                entry_id=f"nist-{cas}", qualifiers=qualifiers,
            ))
            continue

        belegbar.sort(key=lambda w: NIST_QUELLEN_RANG.index(w[2])
                      if w[2] in NIST_QUELLEN_RANG else len(NIST_QUELLEN_RANG))
        wert, streuung, quelle = belegbar[0]
        if not ist_plausibel(schluessel, wert):
            continue
        werk = NIST_QUELLEN[quelle]
        streutext = f" ± {streuung:g}" if streuung is not None else ""
        vorhanden = wikidata.item_has_statement(wd_match["qid"], prop_info["pid"])
        proposals.append(make_row(
            "BEREITS_VORHANDEN" if vorhanden else "VORSCHLAG",
            "NIST WebBook", wd_match, prop_info, round_significant(wert), "",
            Reference(
                isbn=werk["isbn"],
                note=f"{werk['werk']}; Wert {wert:g}{streutext} "
                     f"{NIST_EINHEITEN[schluessel]} ({zustand_text}), gefunden "
                     f"ueber NIST Chemistry WebBook (CAS {cas})",
            ),
            entry_id=f"nist-{cas}", qualifiers=qualifiers,
        ))
    return proposals


def melde_nist_quellen() -> None:
    """Meldet Quellen, die NIST_QUELLEN noch nicht kennt.

    Ohne diese Meldung verschwaende das Werkzeug still Werte, nur weil ihre
    Originalarbeit in der Tabelle fehlt.
    """
    if not _NIST_UNBEKANNTE_QUELLEN:
        return
    gesamt = sum(_NIST_UNBEKANNTE_QUELLEN.values())
    namen = ", ".join(f"{q} ({n}x)"
                      for q, n in _NIST_UNBEKANNTE_QUELLEN.most_common(5))
    print(f"  {gesamt} WebBook-Werte uebergangen, weil ihre Originalarbeit "
          f"nicht in NIST_QUELLEN steht: {namen}", file=sys.stderr)
