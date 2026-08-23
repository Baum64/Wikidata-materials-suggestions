"""Summenformeln: normalisieren, zerlegen, schreiben.

Reine Rechnerei ohne Netz und ohne Wikidata-Wissen - deshalb eine eigene
Datei. Zwei Parser mit verschiedenen Anspruechen leben hier nebeneinander:

    parse_formula        streng, fuer den ITEM-ABGLEICH ("O2Ti" == "TiO₂")
    elemente_aus_formel  tolerant, fuer die Frage WELCHE Elemente drinstecken

Warum beide noetig sind und wie weit jeder traegt: README,
"Formel-Normalisierung" und "enthaelt Elemente von (P2670) aus der
Summenformel".
"""

import collections
import re
from typing import Optional

# Formel-Normalisierung
# ---------------------------------------------------------------------------
#
# Datenbanken und Wikidata schreiben dieselbe Verbindung unterschiedlich auf -
# in Zeichensatz ("TiO2" gegen "TiO₂") wie in Reihenfolge ("O2Ti" gegen
# "TiO₂"). Ein direkter Stringvergleich muss daran scheitern. Deshalb wird die
# Formel in ihre Zusammensetzung {Element: Anzahl} zerlegt und daraus werden
# die plausiblen Schreibweisen ERZEUGT, gegen die dann abgefragt wird.
# Belege und Trefferzahlen: README, "Formel-Normalisierung".

_TIEFGESTELLT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_NORMALZIFFERN = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

# Elektronegativitaet nach Pauling - sie entscheidet, wer in der
# konventionellen Schreibweise vorn steht. Edelgase und einige Actinoide
# haben keinen etablierten Wert; sie fallen auf _EN_UNBEKANNT zurueck und
# werden dadurch nur ueber die alphabetische Variante gefunden.
_EN_UNBEKANNT = 2.2
PAULING = {
    "H": 2.20, "Li": 0.98, "Be": 1.57, "B": 2.04, "C": 2.55, "N": 3.04,
    "O": 3.44, "F": 3.98, "Na": 0.93, "Mg": 1.31, "Al": 1.61, "Si": 1.90,
    "P": 2.19, "S": 2.58, "Cl": 3.16, "K": 0.82, "Ca": 1.00, "Sc": 1.36,
    "Ti": 1.54, "V": 1.63, "Cr": 1.66, "Mn": 1.55, "Fe": 1.83, "Co": 1.88,
    "Ni": 1.91, "Cu": 1.90, "Zn": 1.65, "Ga": 1.81, "Ge": 2.01, "As": 2.18,
    "Se": 2.55, "Br": 2.96, "Kr": 3.00, "Rb": 0.82, "Sr": 0.95, "Y": 1.22,
    "Zr": 1.33, "Nb": 1.60, "Mo": 2.16, "Tc": 1.90, "Ru": 2.20, "Rh": 2.28,
    "Pd": 2.20, "Ag": 1.93, "Cd": 1.69, "In": 1.78, "Sn": 1.96, "Sb": 2.05,
    "Te": 2.10, "I": 2.66, "Xe": 2.60, "Cs": 0.79, "Ba": 0.89, "La": 1.10,
    "Ce": 1.12, "Pr": 1.13, "Nd": 1.14, "Pm": 1.13, "Sm": 1.17, "Eu": 1.20,
    "Gd": 1.20, "Tb": 1.10, "Dy": 1.22, "Ho": 1.23, "Er": 1.24, "Tm": 1.25,
    "Yb": 1.10, "Lu": 1.27, "Hf": 1.30, "Ta": 1.50, "W": 2.36, "Re": 1.90,
    "Os": 2.20, "Ir": 2.20, "Pt": 2.28, "Au": 2.54, "Hg": 2.00, "Tl": 1.62,
    "Pb": 2.33, "Bi": 2.02, "Po": 2.00, "At": 2.20, "Fr": 0.70, "Ra": 0.90,
    "Ac": 1.10, "Th": 1.30, "Pa": 1.50, "U": 1.38, "Np": 1.36, "Pu": 1.28,
    "Am": 1.13, "Cm": 1.28, "Bk": 1.30, "Cf": 1.30, "Es": 1.30, "Fm": 1.30,
    "Md": 1.30, "No": 1.30, "Lr": 1.30,
}

# Ein Token ist entweder ein Elementsymbol mit optionaler Anzahl oder eine
# Klammer mit optionaler Anzahl. Alles andere macht die Formel unbrauchbar.
_FORMEL_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)|(\()|(\)(\d*))")


def parse_formula(formula: str) -> Optional[dict]:
    """Summenformel -> {Element: Anzahl}, oder None wenn nicht deutbar.

    Versteht beide Ziffernarten und geschachtelte Klammern ("Ca(OH)₂").
    Bewusst streng: Hydratpunkte ("CuSO4·5H2O"), Ladungen, Freitext und
    unbekannte Elementsymbole fuehren zu None statt zu einer geratenen
    Zusammensetzung - ein falsch gedeuteter Treffer waere schlimmer als
    gar keiner.
    """
    if not formula:
        return None
    s = formula.strip().translate(_NORMALZIFFERN)
    if not s or not re.fullmatch(r"[A-Za-z0-9()]+", s):
        return None

    stapel = [collections.Counter()]
    pos = 0
    while pos < len(s):
        m = _FORMEL_TOKEN.match(s, pos)
        if not m or m.end() == pos:
            return None
        pos = m.end()
        symbol, anzahl, klammer_auf, klammer_zu, klammer_anzahl = m.groups()
        if symbol:
            if symbol not in PAULING and symbol not in ("He", "Ne", "Ar", "Rn"):
                return None  # kein Elementsymbol -> Formel nicht deutbar
            stapel[-1][symbol] += int(anzahl) if anzahl else 1
        elif klammer_auf:
            stapel.append(collections.Counter())
        elif klammer_zu:
            if len(stapel) == 1:
                return None  # schliessende Klammer ohne oeffnende
            gruppe = stapel.pop()
            faktor = int(klammer_anzahl) if klammer_anzahl else 1
            for el, n in gruppe.items():
                stapel[-1][el] += n * faktor
    if len(stapel) != 1:
        return None  # nicht geschlossene Klammer
    return dict(stapel[0]) or None


def _formel_schreiben(zusammensetzung: dict, reihenfolge: list,
                      tiefgestellt: bool) -> str:
    teile = []
    for el in reihenfolge:
        n = zusammensetzung[el]
        ziffern = "" if n == 1 else str(n)
        teile.append(el + (ziffern.translate(_TIEFGESTELLT)
                           if tiefgestellt else ziffern))
    return "".join(teile)


def formula_candidates(zusammensetzung: dict) -> list:
    """Plausible Schreibweisen einer Zusammensetzung, beste zuerst.

    Jeweils tief- und normalgestellt, in dieser Reihenfolge:

      Hill (C, dann H, dann alphabetisch): "C₁₅H₂₂O₃" - fuer ORGANISCHE
        Verbindungen, also solche mit Kohlenstoff UND Wasserstoff. Nur dort
        ist Hill die Konvention; ein Carbid wie SiC waere als "CSi" nirgends
        auffindbar.
      konventionell, elektropositiver Partner zuerst: "TiO₂", "Al₂O₃",
        "NaCl", "SiC", "CO₂" - fuer alles Anorganische.
      alphabetisch: "O₂Ti" - so liefern manche Datenbanken, und vereinzelt
        steht es auch in Wikidata.

    Erzeugt werden immer alle drei; die Reihenfolge bestimmt nur, welche
    Schreibweise zuerst probiert wird. Doppelte fallen raus - bei NaCl
    bleiben so zwei Kandidaten statt sechs.
    """
    elemente = sorted(zusammensetzung)

    hill = ["C"] + (["H"] if "H" in zusammensetzung else [])
    hill += [el for el in elemente if el not in ("C", "H")]
    konventionell = sorted(
        elemente, key=lambda el: (PAULING.get(el, _EN_UNBEKANNT), el))

    organisch = "C" in zusammensetzung and "H" in zusammensetzung
    ordnungen = ([hill, konventionell] if organisch
                 else [konventionell] + ([hill] if "C" in zusammensetzung
                                         else []))

    kandidaten = []
    for reihenfolge in ordnungen + [elemente]:
        for tiefgestellt in (True, False):
            s = _formel_schreiben(zusammensetzung, reihenfolge, tiefgestellt)
            if s not in kandidaten:
                kandidaten.append(s)
    return kandidaten



# ---------------------------------------------------------------------------
# Der TOLERANTE Parser: welche Elemente stecken drin?
# ---------------------------------------------------------------------------
#
# parse_formula oben ist fuer den Abgleich gebaut und deshalb streng. Fuer die
# Frage, WELCHE Elemente vorkommen, ist die Anforderung schwaecher - dafuer
# steht hier ein zweiter Parser. Warum beide noetig sind: README.

# Kurzfassung der Regel, die der Code unten umsetzt:
#   Element sicher, Menge sicher  -> P2670 mit P1114
#   Element sicher, Menge offen   -> P2670 ohne P1114
#   Element nur eine Moeglichkeit -> nichts, nur Klaerungsvermerk
# Sicher ist ein Element, wenn es mindestens einmal AUSSERHALB jeder
# Kommagruppe steht - oder in JEDEM Zweig einer Kommagruppe vorkommt.

_TIEFZIFFERN = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
# Hochgestellte Ziffern und Vorzeichen sind IMMER Ladungen ("Fe³⁺"), nie
# Stoechiometrie; das Leerstellensymbol ☐ steht fuer eine unbesetzte
# Gitterposition. Beides traegt zur Zusammensetzung nichts bei.
_LADUNG_UND_LEERSTELLE = str.maketrans("", "", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻☐□◻ ")
# Hydratschreibweisen: der Punkt trennt die Formeleinheit vom Kristallwasser.
# "*" kommt in Wikidata vereinzelt statt des Punktes vor.
_HYDRAT_TRENNER = re.compile(r"[·⋅•∙*]")
_KLAMMER_AUF, _KLAMMER_ZU = "([{", ")]}"
_EDELGAS_OHNE_EN = ("He", "Ne", "Ar", "Rn")


class _MengeUnbestimmt(Exception):
    """Ein Index ist eine Variable ("Cu₂₋ₓ") - die Menge ist nicht ableitbar."""


def elemente_aus_formel(formel: str) -> Optional[tuple]:
    """Summenformel -> ({Element: Anzahl oder None}, {unsichere Elemente}).

    Erster Rueckgabewert sind die Elemente, die SICHER enthalten sind; steht
    dort None statt einer Zahl, ist das Element sicher und nur seine Menge
    unbestimmt. Zweiter Rueckgabewert sind Elemente, die bloss eine
    Moeglichkeit einer Mischreihe sind - fuer die darf nichts behauptet
    werden.

    None, wenn die Formel gar nicht deutbar ist.
    """
    if not formel:
        return None
    rest = formel.strip().translate(_TIEFZIFFERN).translate(
        _LADUNG_UND_LEERSTELLE)
    # ASCII-Ladungen ("Te6+"): eine Ziffernfolge unmittelbar vor + oder - ist
    # nie ein stoechiometrischer Index, sondern eine Oxidationsstufe.
    rest = re.sub(r"\d+[+-]", "", rest)
    if not rest:
        return None

    sicher_mit_menge = collections.Counter()
    nur_moeglich = set()
    menge_offen = set()

    for i, teil in enumerate(_HYDRAT_TRENNER.split(rest)):
        if not teil:
            continue
        faktor = 1
        if i > 0:
            # Die Zahl direkt hinter dem Punkt multipliziert den Hydratanteil:
            # "·8H₂O" sind acht Formeleinheiten Wasser.
            treffer = re.match(r"\d+", teil)
            if treffer:
                faktor, teil = int(treffer.group()), teil[treffer.end():]
            else:
                # "·nH₂O" - variable Wassermenge. Die Elemente stehen fest,
                # ihre Anzahl nicht.
                ohne_variable = re.sub(r"^[a-z]+", "", teil)
                if ohne_variable != teil:
                    teil, faktor = ohne_variable, None
        if not teil:
            continue
        if not re.fullmatch(r"[A-Za-z0-9.()\[\]{},]+", teil):
            return None
        try:
            fest, offen, alternativ = _formelausdruck(teil)
        except _MengeUnbestimmt:
            return None
        if fest is None:
            return None

        if faktor is None:
            # Alles aus diesem Abschnitt ist da, aber unbestimmt oft.
            for element in fest:
                sicher_mit_menge.setdefault(element, 0)
            menge_offen |= set(fest) | offen
        else:
            for element, anzahl in fest.items():
                sicher_mit_menge[element] += anzahl * faktor
            menge_offen |= offen
        nur_moeglich |= alternativ

    if not sicher_mit_menge and not nur_moeglich:
        return None

    # Ein Element, das irgendwo unbedingt vorkommt, IST enthalten - auch wenn
    # es zusaetzlich in einer Mischreihe auftaucht. Dann steht nur seine
    # Gesamtmenge nicht fest: in "Al₁₃Si₅O₂₀(OH,F)₁₈Cl" ist Sauerstoff durch
    # O₂₀ gesichert, wie viel davon aus (OH,F) dazukommt aber nicht.
    sicher = {
        element: (None if element in menge_offen or element in nur_moeglich
                  else anzahl)
        for element, anzahl in sicher_mit_menge.items()
    }
    return sicher, {e for e in nur_moeglich if e not in sicher_mit_menge}


def _formelausdruck(rest: str) -> tuple:
    """(feste Zusammensetzung, Elemente mit offener Menge, Alternativen).

    Rekursiv ueber die Klammerebenen. Die feste Zusammensetzung enthaelt nur,
    was unbedingt vorkommt; alles aus einer Kommagruppe landet je nach
    Zweigvergleich in den beiden anderen Mengen.
    """
    fest = collections.Counter()
    offen, alternativ = set(), set()
    pos = 0
    while pos < len(rest):
        zeichen = rest[pos]
        if zeichen in _KLAMMER_AUF:
            ende = _klammer_ende(rest, pos)
            if ende is None:
                return None, offen, alternativ
            inhalt, pos = rest[pos + 1:ende], ende + 1
            faktor, pos = _index_lesen(rest, pos)
            zweige = [_formelausdruck(z) for z in _komma_zerlegen(inhalt)]
            if not zweige or any(f is None for f, _, _ in zweige):
                return None, offen, alternativ
            gruppe, g_offen, g_alternativ = _zweige_vereinen(zweige)
            if faktor is None:
                offen |= set(gruppe)
                faktor = 1
            for element, anzahl in gruppe.items():
                fest[element] += anzahl * faktor
            offen |= g_offen
            alternativ |= g_alternativ
        elif zeichen in _KLAMMER_ZU or zeichen == ",":
            return None, offen, alternativ  # Kommas trennt _komma_zerlegen
        else:
            treffer = re.match(r"([A-Z][a-z]?)(\d+\.\d+|\d*)", rest[pos:])
            if not treffer or not treffer.group(1):
                return None, offen, alternativ
            symbol = treffer.group(1)
            if symbol not in PAULING and symbol not in _EDELGAS_OHNE_EN:
                return None, offen, alternativ
            pos += treffer.end()
            if re.match(r"[a-z]", rest[pos:]):
                raise _MengeUnbestimmt
            index = treffer.group(2)
            if "." in index:
                # Nichtstoechiometrische Phase ("Ag₁.₁Hg₀.₉"): das Element ist
                # da, eine gebrochene Anzahl gehoert aber nicht in P1114.
                offen.add(symbol)
                fest[symbol] += 1
            else:
                fest[symbol] += int(index) if index else 1
    return fest, offen, alternativ


def _zweige_vereinen(zweige: list) -> tuple:
    """Fasst die Zweige einer Kommagruppe zusammen.

    Was in JEDEM Zweig steht, ist gesichert - "(V⁵⁺,V⁴⁺)" ist zweimal
    Vanadium. Nur wo die Zweige sich in der Anzahl unterscheiden, bleibt die
    Menge offen. Alles Uebrige ist eine blosse Moeglichkeit.
    """
    if len(zweige) == 1:
        return zweige[0]

    gemeinsam = set.intersection(*(set(f) for f, _, _ in zweige))
    gruppe = collections.Counter()
    g_offen = set().union(*(o for _, o, _ in zweige))
    g_alternativ = set().union(*(a for _, _, a in zweige))
    for element in gemeinsam:
        mengen = {f[element] for f, _, _ in zweige}
        if len(mengen) == 1:
            gruppe[element] = mengen.pop()
        else:
            gruppe[element] = 0
            g_offen.add(element)
    for fest, _, _ in zweige:
        g_alternativ |= set(fest) - gemeinsam
    return gruppe, g_offen, g_alternativ


def _klammer_ende(rest: str, start: int) -> Optional[int]:
    """Position der zugehoerigen schliessenden Klammer, oder None."""
    tiefe = 0
    for i in range(start, len(rest)):
        if rest[i] in _KLAMMER_AUF:
            tiefe += 1
        elif rest[i] in _KLAMMER_ZU:
            tiefe -= 1
            if tiefe == 0:
                return i
    return None


def _index_lesen(rest: str, pos: int) -> tuple:
    """(Faktor, neue Position) hinter einer schliessenden Klammer.

    Faktor None heisst: dort steht eine Variable statt einer Zahl.
    """
    treffer = re.match(r"\d+\.\d+|\d+", rest[pos:])
    if treffer:
        wert = treffer.group()
        return (None if "." in wert else int(wert)), pos + treffer.end()
    if re.match(r"[a-z]", rest[pos:]):
        raise _MengeUnbestimmt
    return 1, pos


def _komma_zerlegen(rest: str) -> list:
    """Teilt an den Kommas der OBERSTEN Ebene."""
    teile, tiefe, letzter = [], 0, 0
    for i, zeichen in enumerate(rest):
        if zeichen in _KLAMMER_AUF:
            tiefe += 1
        elif zeichen in _KLAMMER_ZU:
            tiefe -= 1
        elif zeichen == "," and tiefe == 0:
            teile.append(rest[letzter:i])
            letzter = i + 1
    teile.append(rest[letzter:])
    return [t for t in teile if t]
