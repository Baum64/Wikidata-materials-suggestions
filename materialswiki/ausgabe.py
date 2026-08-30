"""Ausgabe: Referenzmodell, Vorschlagszeile, CSV und QuickStatements.

Alles, was aus den Befunden der Stufen eine PRUEFBARE Datei macht. Die
Sicherheitseigenschaft des Entwurfs steht in write_quickstatements_draft:
ausserhalb von Abschnitt 1 beginnt jede Zeile mit '#'.
"""

import csv
import datetime as dt
import os
import re
import sys
from decimal import Decimal, InvalidOperation

from .properties import (
    DETERMINATION_PID, DFT_LABEL, DFT_QID, OHNE_BELEG_DATENTYPEN,
)

WIKIPEDIA_EN_QID = "Q328"  # englischsprachige Wikipedia


# ---------------------------------------------------------------------------
# Referenz-Modell: DOI bevorzugt, sonst Referenz-URL + Abrufdatum
# ---------------------------------------------------------------------------

WIKIPEDIA_EN_QID = "Q328"  # englischsprachige Wikipedia


class Reference:
    """Belegt einen Wert. Drei Arten, in absteigender Belastbarkeit:

      DOI      -> S356                                 (stabil, zitierfaehig)
      Import   -> S143 <Projekt-QID> + S4656 <URL>     (Wikimedia-Import)
      URL      -> S854 + S813 (abgerufen am)           (Notnagel)

    P143 "importiert aus Wikimedia-Projekt" zusammen mit P4656
    "Wikimedia-Import-URL" ist die vorgesehene Form fuer aus einer Wikipedia
    uebernommene Werte. Als Import-URL wird ein Permalink auf die konkrete
    Version (oldid) gesetzt - sonst zeigt der Beleg auf eine Seite, die sich
    nach dem Import beliebig geaendert haben kann.
    """

    def __init__(self, doi=None, isbn=None, url=None, imported_from=None,
                 import_url=None, retrieved=None, note="", dataset_doi=None):
        if not any((doi, isbn, url, import_url)):
            raise ValueError("Reference braucht doi, isbn, url oder import_url")
        self.doi = doi
        # Zweite DOI fuer den konkreten Datensatz, wo die Quelle das verlangt
        # (siehe MP_DATASET_DOI). Beide landen als eigener S356-Snak im
        # SELBEN Referenzblock - die Aussage ist mit beiden Arbeiten belegt.
        self.dataset_doi = dataset_doi
        self.isbn = isbn
        self.url = url
        self.imported_from = imported_from
        self.import_url = import_url
        self.retrieved = retrieved or dt.date.today().isoformat()
        self.note = note

    @property
    def dois(self) -> list:
        return [d for d in (self.doi, self.dataset_doi) if d]

    @property
    def isbn_pid(self) -> str:
        """P212 fuer ISBN-13, P957 fuer ISBN-10 - anhand der Ziffernzahl."""
        ziffern = re.sub(r"[^\dXx]", "", self.isbn or "")
        return "P212" if len(ziffern) == 13 else "P957"

    @property
    def mode(self) -> str:
        if self.doi:
            return "DOI"
        if self.isbn:
            return "ISBN-13" if self.isbn_pid == "P212" else "ISBN-10"
        if self.import_url:
            return "Wikimedia-Import"
        return "URL+Datum"

    def as_csv_fields(self) -> dict:
        return {
            "ref_mode": self.mode,
            "ref_doi": "; ".join(self.dois),
            "ref_isbn": self.isbn or "",
            "ref_url": (
                self.url
                or self.import_url
                or (f"https://doi.org/{self.doi}" if self.doi else "")
            ),
            # Abrufdatum nur wo noetig - DOI und ISBN sind stabil.
            "ref_retrieved": "" if (self.doi or self.isbn) else self.retrieved,
            "ref_note": self.note,
        }

    def as_quickstatements(self) -> str:
        if self.doi:
            return "".join(f'\tS356\t"{d}"' for d in self.dois)
        if self.isbn:
            return f'\t{self.isbn_pid.replace("P", "S")}\t"{self.isbn}"'
        if self.import_url:
            return (
                f"\tS143\t{self.imported_from}"
                f'\tS4656\t"{self.import_url}"'
                f"\tS813\t+{self.retrieved}T00:00:00Z/11"
            )
        return f'\tS854\t"{self.url}"\tS813\t+{self.retrieved}T00:00:00Z/11'


def round_significant(value: float, digits: int = 6) -> float:
    """Auf signifikante Stellen runden, nicht auf Nachkommastellen.

    Die Groessen hier reichen von 1e-8 (spezifischer Widerstand in Ohm*m)
    bis 1e4 (Schmelzpunkte in Kelvin, Moduln in Gigapascal). round(x, 6)
    wuerde den Widerstand zu 0.0 machen.
    """
    return float(f"{value:.{digits}g}")


def make_row(status, source, wd_match, prop_info, value, value_label,
             reference, formula="", entry_id="", qualifiers=None,
             ohne_beleg=False, entfernen=False):
    """Baut eine Vorschlagszeile - einheitlich fuer alle Quellen.

    qualifiers ist eine Liste (pid, quickstatements_wert, klartext). Der Wert
    steht bereits in QuickStatements-Schreibweise - "Q1048589" fuer eine
    itemwertige, "20U25267" fuer eine mengenwertige Angabe. Er landet sowohl
    lesbar in der CSV-Spalte "bestimmungsmethode" als auch maschinenlesbar
    im QuickStatements-Entwurf.

    ohne_beleg erzwingt den belegfreien Modus auch fuer Datentypen, die nicht
    in OHNE_BELEG_DATENTYPEN stehen. Gebraucht wird das fuer AUS DEM ITEM
    ABGELEITETE Aussagen (P2670 aus der Summenformel): dort gibt es keine
    externe Quelle, die man zitieren koennte.

    entfernen macht aus der Zeile eine LOESCHZEILE: im Entwurf steht sie mit
    fuehrendem "-", QuickStatements nimmt die Aussage damit vom Item. Das
    braucht genau eine Stufe - die Umstellung P527 -> P2670 -, und nur dort
    darf es gesetzt werden.
    """
    qualifiers = qualifiers or []
    datentyp = prop_info.get("datatype", "quantity")
    row = {
        "status": status,
        "source": source,
        "qid": wd_match["qid"],
        "label": wd_match["label"],
        "property": f"{prop_info['pid']} ({prop_info['label']})",
        "value": value,
        "value_label": value_label,
        "datatype": datentyp,
        "unit_qid": prop_info["unit_qid"],
        "formula": formula,
        "bestimmungsmethode": "; ".join(
            f"{pid}={wert} ({text})" for pid, wert, text in qualifiers
        ),
        "entry_id": entry_id,
    }

    ohne_beleg = ohne_beleg or datentyp in OHNE_BELEG_DATENTYPEN
    if ohne_beleg:
        # Belegspalten leer lassen - eine gefuellte ref_doi wuerde beim
        # Durchsehen suggerieren, dass ein Beleg mitgeschrieben wird.
        # Die HERKUNFT bleibt in ref_note stehen, damit die Zeile pruefbar
        # ist; sie ist nur kein Beleg im Sinne von Wikidata.
        row.update({
            "ref_mode": ("ohne Beleg (Identifikator)"
                         if datentyp in OHNE_BELEG_DATENTYPEN
                         else "ohne Beleg (aus dem Item abgeleitet)"),
            "ref_doi": "", "ref_isbn": "", "ref_url": "", "ref_retrieved": "",
            "ref_note": reference.note,
        })
    else:
        row.update(reference.as_csv_fields())

    row["_ref"] = reference
    row["_pid"] = prop_info["pid"]
    row["_qualifiers"] = qualifiers
    row["_ohne_beleg"] = ohne_beleg
    row["_entfernen"] = entfernen
    if entfernen:
        # Der Status bleibt "VORSCHLAG" - die Zeile ist einspielbar und
        # gehoert in Abschnitt 1. Dass hier etwas WEGGEHT, steht in der
        # Property-Spalte, im Entwurf am fuehrenden "-" und in der Notiz.
        row["property"] = f"{prop_info['pid']} ({prop_info['label']}) - ENTFERNEN"
    return row


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "status",
    "source",
    "qid",
    "label",
    "property",
    "value",
    "value_label",
    "datatype",
    "unit_qid",
    "formula",
    # Qualifikator der Aussage: bei gerechneten Werten P459 -> DFT.
    # Leer bei Literaturwerten aus der Wikipedia.
    "bestimmungsmethode",
    # Nur bei MANUELLE_KLAERUNG_NOETIG belegt: die in Frage kommenden Items,
    # damit die Zeile ohne eigene Recherche abarbeitbar ist.
    "kandidaten",
    "entry_id",
    # Referenz: DOI wenn vorhanden, sonst URL + Abrufdatum
    "ref_mode",
    "ref_doi",
    "ref_isbn",
    "ref_url",
    "ref_retrieved",
    "ref_note",
]


def write_csv_streaming(proposals, path: str = "vorschlaege.csv") -> list:
    """Schreibt jede Zeile SOFORT und gibt sie zusaetzlich gesammelt zurueck.

    Ein Periodensystem-Lauf dauert je nach Drosselung viele Minuten. Wuerde
    erst am Ende geschrieben, waere bei Abbruch (Ctrl-C, Netzfehler) alles
    verloren - genau das ist beim Lauf ueber 44 von 174 Elementen passiert.
    Deshalb Zeile fuer Zeile mit flush().
    """
    gesammelt = []
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        f.flush()
        for row in proposals:
            writer.writerow(row)
            f.flush()
            gesammelt.append(row)
    print(
        f"Vorschlagsliste geschrieben nach: {path} ({len(gesammelt)} Zeilen)",
        file=sys.stderr,
    )
    return gesammelt


def write_csv(proposals: list, path: str = "vorschlaege.csv") -> None:
    write_csv_streaming(proposals, path)


def quickstatements_value(row: dict) -> str:
    """Wert einer Aussage in QuickStatements-V1-Schreibweise.

    Mengenwerte MUESSEN ihre Einheit tragen: QuickStatements erwartet
    "<zahl>U<QID-Nummer>", also z. B. "1357.77U11579" fuer Kelvin (Q11579).
    Ohne das "U..." landet der Wert als einheitenlose Zahl in Wikidata -
    eine Dichte stuende dann als blosse 8.96 da.

    Ausserdem wird die Exponentialschreibweise aufgeloest: Python schreibt
    den spezifischen Widerstand als "1.678e-08", QuickStatements liest das
    nicht als Zahl. Ueber Decimal wird daraus "0.00000001678".

    Item-wertige Aussagen (z. B. P556 Kristallsystem) stehen als blankes
    QID - dort waere eine Einheit sinnlos.
    """
    value = row["value"]
    if row.get("datatype") == "item":
        return str(value)
    if row.get("datatype") in ("external-id", "string"):
        # Zeichenketten (z. B. CAS-Nummer) gehoeren in Anfuehrungszeichen,
        # sonst liest QuickStatements sie als Zahl oder QID.
        return f'"{value}"'

    try:
        zahl = format(Decimal(str(value)), "f")
    except (InvalidOperation, ValueError):
        return str(value)

    unit_qid = (row.get("unit_qid") or "").strip()
    if not unit_qid.startswith("Q"):
        return zahl  # dimensionslose Groesse
    return f"{zahl}U{unit_qid[1:]}"


def clear_quickstatements_draft(path: str) -> None:
    """Setzt den Entwurf vor dem Lauf auf einen Platzhalter.

    Der Entwurf entsteht erst am Ende. Ohne dieses Leeren stuende nach einem
    Abbruch der vollstaendige Entwurf des VORIGEN Laufs neben der frisch und
    nur teilweise geschriebenen CSV - zwei Dateien, die nicht zusammengehoeren
    und deren Unterschied niemandem auffaellt.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Lauf noch nicht abgeschlossen - dieser Entwurf ist leer "
                "und unvollstaendig.\n")


_TRENNER = "# " + "=" * 70


def _abschnitt_kopf(titel: str, anzahl: int, erklaerung: list,
                    einheit: tuple = ("Zeile", "Zeilen")) -> list:
    """Auskommentierter Abschnittskopf mit Zaehler und Begruendung."""
    zeilen = [
        "",
        _TRENNER,
        f"# {titel} ({anzahl} {einheit[0] if anzahl == 1 else einheit[1]})",
    ]
    zeilen += [f"# {z}" for z in erklaerung]
    zeilen.append(_TRENNER)
    return zeilen


def _vorhandene_zeile(row: dict) -> str:
    """Eine BEREITS_VORHANDEN-Zeile, vollstaendig auskommentiert."""
    ref = row.get("_ref")
    herkunft = f" | Quelle: {row.get('source', '?')}"
    if ref is not None:
        herkunft += f" ({ref.mode})"
    return (f"# {row.get('qid', '')}\t{row.get('_pid', '')}\t"
            f"{row.get('value', '')}{herkunft}")


def _klaerungs_zeilen(row: dict) -> list:
    """Eine MANUELLE_KLAERUNG-Zeile, vollstaendig auskommentiert.

    Zwei Auspraegungen: eine mehrdeutige Formel (dann steht kein Item fest,
    dafuer die Kandidaten) und ein Wert ohne Abbildung in der value_map
    (dann steht das Item fest, aber der Wert laesst sich nicht setzen).
    """
    grund = row.get("status", "").replace("MANUELLE_KLAERUNG_NOETIG", "").strip()
    grund = grund.strip("()") or "unklar"
    if row.get("kandidaten"):
        zeilen = [f"# Formel {row.get('formula', '?')}: {grund}"]
        for kandidat in row["kandidaten"].split("; "):
            zeilen.append(f"#     {kandidat}")
        zeilen.append(f"#     Eintrag {row.get('entry_id', '?')}, "
                      f"DOI {row.get('ref_doi') or '?'}")
        return zeilen
    return [
        f"# {row.get('qid', '')} {row.get('label', '')}: {grund}",
        f"#     Property {row.get('property', '?')}, Rohwert "
        f"{row.get('value', '?')!r}, Quelle {row.get('source', '?')}",
    ]


def write_quickstatements_draft(proposals: list, path: str = "qs_entwurf.txt") -> None:
    """Erzeugt einen QuickStatements-V1-Entwurf aus ALLEN Zeilen.

    Einspielbar ist nur, was status == 'VORSCHLAG' hat (bestehendes Item,
    Property noch nicht gesetzt, Beleg vorhanden). Die beiden anderen
    Status kommen mit in die Datei, aber in eigene, durchgehend
    auskommentierte Abschnitte:

      BEREITS_VORHANDEN         geprueft und bewusst nicht vorgeschlagen
      MANUELLE_KLAERUNG_NOETIG  Entscheidung noetig, die das Skript nicht
                                treffen darf

    Sie stehen dort zur Kenntnis, nicht zur Ausfuehrung: ausserhalb des
    ersten Abschnitts beginnt JEDE Zeile mit '#'. Die Datei laesst sich
    dadurch komplett nach QuickStatements kopieren, ohne dass aus einer
    dieser Zeilen versehentlich eine Aussage wird.

    Die Datei bleibt ein ENTWURF - vor dem Einspielen jede Zeile pruefen!
    """
    vorschlaege = [r for r in proposals if r.get("status") == "VORSCHLAG"]
    vorhanden = [r for r in proposals
                 if r.get("status") == "BEREITS_VORHANDEN"]
    klaerung = [r for r in proposals
                if "KLAERUNG" in (r.get("status") or "")]

    lines = [
        _TRENNER,
        "# ENTWURF - vor Verwendung jede Zeile manuell pruefen!",
        "#",
        "# Aufbau dieser Datei:",
        f"#   ABSCHNITT 1  EINSPIELBAR .......... {len(vorschlaege):4d}  "
        "(die einzigen ausfuehrbaren Zeilen)",
        f"#   ABSCHNITT 2  BEREITS VORHANDEN .... {len(vorhanden):4d}  "
        "(auskommentiert)",
        f"#   ABSCHNITT 3  MANUELLE KLAERUNG .... {len(klaerung):4d}  "
        "(auskommentiert)",
        "#",
        "# Ausserhalb von Abschnitt 1 beginnt jede Zeile mit '#'.",
        "#",
        "# Mengenwerte tragen ihre Einheit als '<zahl>U<QID-Nummer>',",
        "# z. B. 1357.77U11579 = 1357.77 Kelvin (Q11579).",
        "# Beleg, in dieser Rangfolge: S356 = DOI, S212/S957 = ISBN-13/-10",
        "# (beide aus dem Wikipedia-Einzelnachweis des Wertes), sonst",
        "# S143+S4656 = Wikimedia-Import mit Permalink auf die Artikelversion.",
        "#",
        f"# {DETERMINATION_PID} {DFT_QID} als QUALIFIKATOR heisst: der Wert ist",
        f"# gerechnet ({DFT_LABEL}), nicht gemessen. Diese Aussagen",
        "# stammen aus dem Materials Project und beschreiben den idealen",
        "# Einkristall bei 0 K. Kristallsystem und Dichte liegen dicht am",
        "# Handbuchwert, elastische Moduln und Poissonzahl koennen deutlich",
        "# abweichen (Titan-Schubmodul 62 statt 44 GPa) - diese Zeilen vor",
        "# der Uebernahme gegen Literatur pruefen.",
        "# Zeilen OHNE diesen Qualifikator sind Literaturwerte aus einer",
        "# Wikipedia-Infobox - dort Wert und Modifikation gegenpruefen.",
        _TRENNER,
    ]

    geloescht = [r for r in vorschlaege if r.get("_entfernen")]
    erklaerung = ["Nur diese Zeilen sind QuickStatements-Syntax. Trotzdem gilt:",
                  "erst nach zeilenweiser Pruefung einspielen."]
    if geloescht:
        # Eine Loeschzeile nimmt etwas vom Item. Das muss im Kopf stehen,
        # nicht nur am unscheinbaren Minuszeichen der Zeile selbst.
        erklaerung += [
            "",
            f"ACHTUNG: {len(geloescht)} dieser Zeilen beginnen mit '-' und",
            "ENTFERNEN eine bestehende Aussage (Umstellung P527 -> P2670).",
            "Sie gehoeren mit der zugehoerigen P2670-Zeile zusammen - nur",
            "eine von beiden einzuspielen hinterlaesst Dublette oder Luecke.",
        ]
    lines += _abschnitt_kopf(
        "ABSCHNITT 1: EINSPIELBAR", len(vorschlaege), erklaerung,
        einheit=("Aussage", "Aussagen"),
    )
    ohne_einheit = []
    for row in vorschlaege:
        ref = row["_ref"]
        # Item-wertige Aussagen stehen als blankes QID (z. B. Q473227),
        # Mengenwerte als Zahl + Einheit. Ein in Anfuehrungszeichen gesetztes
        # QID wuerde QuickStatements als Zeichenkette interpretieren.
        wert = quickstatements_value(row)
        # Nur melden, wenn eine Einheit HINTERLEGT ist, aber nicht in der
        # Zeile landet. Echt dimensionslose Groessen (Poissonzahl) haben
        # bewusst keine und sind kein Fehler.
        if row.get("unit_qid") and "U" not in wert:
            ohne_einheit.append(f"{row['qid']} {row['_pid']}")
        # Reihenfolge in QuickStatements V1: Aussage, dann Qualifikatoren
        # (P-Praefix), dann Belege (S-Praefix) - alles in EINER Zeile.
        qual = "".join(
            f"\t{pid}\t{wert_qid}"
            for pid, wert_qid, _ in row.get("_qualifiers") or []
        )
        # Identifikatoren gehen ohne S-Angabe raus - siehe
        # OHNE_BELEG_DATENTYPEN. Die Herkunft steht trotzdem im Kommentar.
        beleg = "" if row.get("_ohne_beleg") else ref.as_quickstatements()
        if row.get("_entfernen"):
            # Loeschzeile: fuehrendes "-", und ohne Qualifikatoren und Beleg -
            # QuickStatements sucht die Aussage ueber Property und Wert.
            lines.append(f"-{row['qid']}\t{row['_pid']}\t{wert}")
        else:
            lines.append(
                f"{row['qid']}\t{row['_pid']}\t{wert}{qual}{beleg}"
            )
        klartext = f" ({row['value_label']})" if row.get("value_label") else ""
        if not row.get("_ohne_beleg"):
            modus = ref.mode
        elif row.get("datatype") in OHNE_BELEG_DATENTYPEN:
            modus = "ohne Beleg, Identifikator"
        else:
            modus = "ohne Beleg, aus dem Item abgeleitet"
        lines.append(
            f"# Quelle: {row['source']} ({modus}) - {ref.note}{klartext}")
    if not vorschlaege:
        lines.append("# (keine)")

    lines += _abschnitt_kopf(
        "ABSCHNITT 2: BEREITS VORHANDEN - NICHT EINSPIELEN", len(vorhanden),
        ["Das Item traegt diese Property schon. Hier nur, damit",
         "nachvollziehbar ist, was geprueft und verworfen wurde."],
    )
    lines += [_vorhandene_zeile(r) for r in vorhanden] or ["# (keine)"]

    lines += _abschnitt_kopf(
        "ABSCHNITT 3: MANUELLE KLAERUNG NOETIG - NICHT EINSPIELEN",
        len(klaerung),
        ["Hier ist eine fachliche Entscheidung noetig, die das Skript",
         "nicht treffen darf - etwa welches Polymorph gemeint ist.",
         "Nach der Entscheidung die Aussage von Hand ergaenzen."],
    )
    for row in klaerung:
        lines += _klaerungs_zeilen(row)
    if not klaerung:
        lines.append("# (keine)")

    if ohne_einheit:
        # Sichtbar machen statt still durchgehen lassen - eine Mengenaussage
        # ohne Einheit ist in Wikidata praktisch immer ein Fehler.
        print(
            f"WARNUNG: {len(ohne_einheit)} Mengenaussage(n) ohne Einheit: "
            f"{', '.join(ohne_einheit[:5])}"
            + (" ..." if len(ohne_einheit) > 5 else ""),
            file=sys.stderr,
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(
        f"QuickStatements-Entwurf geschrieben nach: {path} "
        f"({len(vorschlaege)} einspielbar, {len(vorhanden)} vorhanden, "
        f"{len(klaerung)} zur Klaerung)",
        file=sys.stderr,
    )
