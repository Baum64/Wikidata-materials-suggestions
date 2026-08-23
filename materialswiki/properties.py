"""Was womit nach Wikidata geht: Properties, Einheiten, Schranken.

Reine Tabellen und die zwei kleinen Funktionen, die sie auswerten. Kein Netz,
keine Logik der Stufen - deshalb eine eigene Datei, die jedes Modul laden
kann, ohne den ganzen Apparat mitzuziehen.

NUR mit auf wikidata.org verifizierten Properties befuellen; welche bewusst
fehlen und warum, steht im README ("Abgedeckte Properties").
"""

# MP-Feldpfad -> (interner Schluessel, Faktor auf die Wikidata-Einheit).
# Der Faktor ist der Knackpunkt: die Moduln liefert MP in GPa, Wikidata will
# Pascal. Die DICHTE dagegen kommt in g/cm^3 - genau der Einheit, in der sie
# auch nach Wikidata geht (siehe PROPERTY_MAP) - und bleibt deshalb, wie sie
# ist.
#
# Welche MP-Felder bewusst NICHT uebernommen sind (band_gap und weitere) und
# warum: README, "Abgedeckte Properties".
MP_FIELD_MAP = {
    "density": ("density", 1.0),                       # g/cm^3, unveraendert
    "symmetry.crystal_system": ("crystal_system", None),  # itemwertig
    "bulk_modulus.vrh": ("bulk_modulus", 1e9),         # GPa     -> Pa
    "shear_modulus.vrh": ("shear_modulus", 1e9),       # GPa     -> Pa
    "homogeneous_poisson": ("poisson_ratio", 1.0),     # dimensionslos
}

# Groessen, die MP zwar liefert, die aber nur der Qualitaetsbewertung dienen
# und nie zu einer Aussage werden. Sie landen als Kontext in der CSV.
MP_META_FIELDS = ("material_id", "formula_pretty", "theoretical", "is_stable",
                  "energy_above_hull", "database_IDs")

# ---------------------------------------------------------------------------
# Bestimmungsmethode: gerechnete Werte als solche kennzeichnen
# ---------------------------------------------------------------------------
#
# Jede MP-Aussage traegt P459 -> Q1048589 ("berechnet, DFT"). Warum das noetig
# ist, wie weit die Rechnung vom Messwert abweicht und warum es Q1048589 sein
# muss und nicht der gleichnamige Stub Q1209474: README, "Die Werte sind
# gerechnet, nicht gemessen". Infobox-Werte bekommen bewusst KEINEN
# Qualifikator - dort steht die Methode nicht dabei.
DETERMINATION_PID = "P459"
DFT_QID = "Q1048589"
DFT_LABEL = "Dichtefunktionaltheorie"

# ---------------------------------------------------------------------------
# Messbedingungen der Dichte (P2054)
# ---------------------------------------------------------------------------
#
# P2054 verlangt laut Nutzungsanweisung Temperatur (P2076) und
# Aggregatzustand (P515) als Qualifikatoren. Begruendung und Belege:
# README, "Die Dichte traegt ihre Messbedingungen".
TEMPERATUR_PID = "P2076"
AGGREGAT_PID = "P515"
CELSIUS_QID = "Q25267"
KELVIN_QID = "Q11579"
AGGREGAT_FEST = "Q11438"      # Festkoerper
AGGREGAT_FLUESSIG = "Q11435"  # Fluessigkeit
AGGREGAT_GAS = "Q11432"       # Gas

# Vorgabe, wenn die Quelle keine Messtemperatur nennt. Nicht willkuerlich:
# die deutschen Elementinfoboxen schreiben ueberwiegend "(20 °C)".
STANDARD_TEMPERATUR_C = 20.0

# Die Temperatur JEDER MP-Groesse. Eine DFT-Rechnung kennt keine thermische
# Anregung: Dichte wie Elastizitaetstensor gehoeren zum relaxierten
# Grundzustand, also zu 0 K. Das ist keine Annahme ueber eine Messung,
# sondern eine Eigenschaft der Rechnung - und genau die Groesse, an der die
# systematische Abweichung von den Handbuchwerten haengt.
DFT_TEMPERATUR = (TEMPERATUR_PID, f"0U{KELVIN_QID[1:]}", "0 K (DFT-Grundzustand)")

# ---------------------------------------------------------------------------
# Groessen, die NICHT mit der Rechnung belegt werden
# ---------------------------------------------------------------------------
#
# Fuer das Kristallsystem ist die DFT-Rechnung der schwaechere Beleg als jedes
# Standardwerk. Solche Groessen bekommen deshalb einen LITERATURBELEG und
# folgerichtig KEINEN P459-Qualifikator. Warum, und was das fuer die Pruefung
# der Zeile bedeutet: README, "Das Kristallsystem wird mit Literatur belegt".
# ---------------------------------------------------------------------------
# Physikalische Plausibilitaet
# ---------------------------------------------------------------------------
#
# Die API-Filter sagen etwas ueber das MATERIAL aus, nichts ueber die einzelne
# Rechnung - MP liefert vereinzelt Rechenmuell (Zink: Schubmodul -2781 GPa).
# Der Fall im Detail: README, "Physikalisch Unmoegliches wird abgefangen".
#
# Geprueft wird gegen physikalische Schranken, in Wikidata-Einheiten:
#   Moduln       muessen positiv sein; die Obergrenze liegt weit ueber
#                Diamant (Kompressionsmodul ~443 GPa, Schubmodul ~535 GPa)
#   Poissonzahl  ist fuer isotrope lineare Elastizitaet thermodynamisch auf
#                [-1; 0,5] beschraenkt - ausserhalb ist sie unmoeglich
#   Dichte       zwischen Lithium (0,534 g/cm^3) und Osmium (22,59 g/cm^3),
#                grosszuegig gefasst
#
# Unplausible Werte werden NICHT still verworfen, sondern als
# MANUELLE_KLAERUNG_NOETIG ausgewiesen: sonst faellt nie auf, dass die
# Datenbank an dieser Stelle kaputt ist.
PLAUSIBEL = {
    "density": (0.01, 30.0),               # g/cm^3
    "bulk_modulus": (1e6, 1e12),           # Pa, also 0,001 bis 1000 GPa
    "shear_modulus": (1e6, 1e12),          # Pa
    "poisson_ratio": (-1.0, 0.5),          # dimensionslos, thermodynamisch
    # Bildungsenthalpie: von rund -2300 kJ/mol (Al2O3, ThO2) bis gut
    # +800 kJ/mol (einatomige Gase schwerer Metalle). Entropie ist nach dem
    # dritten Hauptsatz nie negativ; nach oben reicht sie bei schweren
    # Molekuelen ueber 400 J/(mol*K).
    "formation_enthalpy": (-3000.0, 1500.0),    # kJ/mol
    "molar_entropy": (0.0, 1000.0),             # J/(mol*K)
    # Spannweite an den 62 Elementwerten der englischen Infoboxen: 2,556
    # (Silicium) bis 92,6 (Caesium). Grosszuegig gefasst - unterhalb von 0
    # waere die Angabe aber physikalisch kaum noch ein Elementwert, und
    # oberhalb von 200 steht dort etwas anderes.
    "linear_thermal_expansion": (0.0, 200.0),   # um/(m*K)
}


def ist_plausibel(internal_key: str, wert) -> bool:
    """False, wenn der Wert physikalisch unmoeglich ist."""
    grenzen = PLAUSIBEL.get(internal_key)
    if grenzen is None or not isinstance(wert, (int, float)):
        return True
    return grenzen[0] <= wert <= grenzen[1]


# ---------------------------------------------------------------------------
# Groessen, die gar keinen Beleg bekommen
# ---------------------------------------------------------------------------
#
# Externe Identifikatoren belegen sich selbst; sie gehen ohne S-Angabe raus,
# die Herkunft bleibt in ref_note. Warum: README, "Identifikatoren bekommen
# gar keinen Beleg". Entschieden ueber den DATENTYP statt ueber einzelne
# P-Nummern - was external-id ist, ist per Definition ein Identifikator.
OHNE_BELEG_DATENTYPEN = {"external-id"}

LITERATUR_BELEG = {
    "crystal_system": {
        # Greenwood/Earnshaw, Chemistry of the Elements, 2. Aufl. 1997.
        # ISBN am 2026-08-15 geprueft: Pruefsumme gueltig, ueber OpenLibrary
        # als dieses Werk bestaetigt. ISBN-10 -> QuickStatements S957.
        "isbn": "0-08-037941-9",
        "werk": "Greenwood/Earnshaw, Chemistry of the Elements, 2. Aufl. 1997",
    },
}

# MP schreibt das Kristallsystem gross ("Tetragonal"), die value_map unten
# klein. Verglichen wird deshalb in Kleinschreibung; das Vokabular ist
# ansonsten identisch (dieselben sieben Systeme).

# Interner Schlüssel -> (Wikidata-Property, Datentyp, Einheit-QID, Beschreibung)
# NUR mit auf wikidata.org verifizierten Properties befüllen!
#
# "datatype" muss zum Wikidata-Datentyp der Property passen:
#   "quantity" -> Zahlwert + unit_qid
#   "item"     -> QID-Wert; "value_map" uebersetzt den Quellstring in ein QID.
#                 Werte ausserhalb der value_map werden NICHT geraten, sondern
#                 zur manuellen Klaerung markiert.
PROPERTY_MAP = {
    # Dichte in GRAMM PRO KUBIKZENTIMETER. Beide Einheiten sind laut
    # Constraint erlaubt (Q844211 kg/m^3, Q13147228 g/cm^3, dazu g/l und
    # g/m^3), aber der Bestand ist eindeutig: 2015 der 2476 P2054-Aussagen
    # stehen in g/cm^3 und nur 461 in kg/m^3 (gemessen 2026-08-19). Es ist
    # ausserdem die Einheit, in der alle hiesigen Quellen liefern - MP wie
    # beide Wikipedias -, also entfaellt jede Umrechnung.
    "density": {
        "pid": "P2054",
        "datatype": "quantity",
        "unit_qid": "Q13147228",  # Gramm pro Kubikzentimeter, g/cm^3
        "label": "Dichte",
    },
    "melting_point": {
        "pid": "P2101",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin
        "label": "Schmelzpunkt",
    },
    "boiling_point": {
        "pid": "P2102",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin
        "label": "Siedepunkt",
    },
    # P556 ist item-wertig. Die QIDs sind nicht geraten, sondern der
    # "one-of"-Constraint der Property, am 2026-08-15 ausgelesen. Er umfasst
    # inzwischen ELF Werte: die sieben Kristallsysteme plus
    #
    #   Q3006714  face-centered cubic  (fcc, kubisch flaechenzentriert)
    #   Q851536   body-centered cubic  (bcc, kubisch raumzentriert)
    #   Q103382   amorphes Material
    #   Q263214   Quasikristall
    #
    # fcc und bcc sind streng genommen Bravais-Gitter und keine
    # Kristallsysteme; Wikidata laesst sie auf P556 dennoch zu, und sie sind
    # die AUSSAGEKRAEFTIGEREN Werte - "kubisch" allein unterschlaegt den
    # Unterschied zwischen Kupfer und Wolfram. Wo die Quelle die Zentrierung
    # hergibt, wird deshalb der spezifischere Wert genommen (siehe
    # verfeinere_zentrierung und die Stichwortlisten der beiden Wikipedias).
    #
    # amorph und Quasikristall stehen bewusst NICHT hier: weder MP noch die
    # Infoboxen liefern sie, und ein Wert ausserhalb der value_map wird
    # ohnehin zur manuellen Klaerung markiert statt geraten.
    "crystal_system": {
        "pid": "P556",
        "datatype": "item",
        "unit_qid": "",
        "label": "Kristallsystem",
        "value_map": {
            "cubic": ("Q473227", "kubisches Kristallsystem"),
            "fcc": ("Q3006714", "kubisch flaechenzentriert"),
            "bcc": ("Q851536", "kubisch raumzentriert"),
            "hexagonal": ("Q663314", "hexagonales Kristallsystem"),
            "monoclinic": ("Q624543", "monoklines Kristallsystem"),
            "orthorhombic": ("Q648961", "orthorhombisches Kristallsystem"),
            "tetragonal": ("Q503601", "tetragonales Kristallsystem"),
            "triclinic": ("Q376927", "triklines Kristallsystem"),
            "trigonal": ("Q588274", "trigonales Kristallsystem"),
        },
    },
    # Elastische Moduln. MP fuehrt sie als Objekt mit voigt/reuss/vrh;
    # genommen wird das Voigt-Reuss-Hill-Mittel (Pfad "...vrh" in
    # MP_FIELD_MAP), das uebliche Mittel fuer polykristalline Werkstoffe.
    # MP rechnet in GPa, Wikidata will Pascal - Faktor steht in MP_FIELD_MAP.
    "bulk_modulus": {
        "pid": "P5668",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal
        "label": "Kompressionsmodul",
    },
    "shear_modulus": {
        "pid": "P5673",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal
        "label": "Schubmodul",
    },
    "thermal_conductivity": {
        "pid": "P2068",
        "datatype": "quantity",
        "unit_qid": "Q1463969",  # Watt pro Meter-Kelvin, W/(m*K)
        "label": "Waermeleitfaehigkeit",
    },
    "electrical_conductivity": {
        "pid": "P2055",
        "datatype": "quantity",
        "unit_qid": "Q80842107",  # Siemens pro Meter, S/m
        "label": "Elektrische Leitfaehigkeit",
    },
    # Aus der Wikipedia-Infobox kommt der spezifische Widerstand direkt;
    # er wird als solcher uebernommen und NICHT zur Leitfaehigkeit
    # umgerechnet - so steht in der Aussage, was die Quelle wirklich sagt.
    "electrical_resistivity": {
        "pid": "P5679",
        "datatype": "quantity",
        "unit_qid": "Q1441459",  # Ohm-Meter, Ohm*m
        "label": "Spezifischer Widerstand",
    },
    # Spezifische Waermekapazitaet - MP fuehrt sie nicht, aber die deutsche
    # Wikipedia fuehrt sie als Skalar in J/(kg*K).
    "specific_heat_capacity": {
        "pid": "P2056",
        "datatype": "quantity",
        "unit_qid": "Q3085309",  # Joule pro Kilogramm-Kelvin, J/(kg*K)
        "label": "Spezifische Waermekapazitaet",
    },
    "speed_of_sound": {
        "pid": "P2075",
        "datatype": "quantity",
        "unit_qid": "Q182429",  # Meter pro Sekunde, m/s
        "label": "Schallgeschwindigkeit",
    },
    "poisson_ratio": {
        "pid": "P5593",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos
        "label": "Poissonzahl",
    },
    # CAS-Nummer: Datentyp external-id, also eine Zeichenkette ohne Einheit.
    # Q102507 ("CAS-Nummer") traegt P1687 -> P231; das ist die Property.
    "cas_number": {
        "pid": "P231",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "CAS-Nummer",
    },
    # Raumgruppe. Itemwertig, aber OHNE value_map: die Zielitems sind die 230
    # Raumgruppen, die per P9733 (Raumgruppennummer) aus Wikidata selbst
    # aufgeloest werden - siehe fetch_space_group_qids. Eine handgepflegte
    # Tabelle mit 230 Eintraegen waere sofort veraltet.
    "space_group": {
        "pid": "P690",
        "datatype": "item",
        "unit_qid": "",
        "label": "Raumgruppe",
    },
    # Laengenausdehnungskoeffizient. Einzige laut Constraint erlaubte
    # Einheit ist Q56025776 (Mikrometer pro Meterkelvin) - genau die, in der
    # die englischen Elementinfoboxen rechnen: "{{val|16.64|e=-6}}/K" sind
    # 16,64 um/(m*K). Am Bestand traegt die Property noch KEINE einzige
    # Aussage (gemessen 2026-08-19); Quelle und Grenzen: README,
    # "Laengenausdehnungskoeffizient (P5672)".
    "linear_thermal_expansion": {
        "pid": "P5672",
        "datatype": "quantity",
        "unit_qid": "Q56025776",  # Mikrometer pro Meterkelvin, um/(m*K)
        "label": "Laengenausdehnungskoeffizient",
    },
    # Punktgruppe. Wie die Raumgruppe itemwertig und ohne value_map - die 32
    # kristallographischen Punktgruppen stehen als Items in Wikidata und
    # haengen dort schon an den Raumgruppen (230 der 236 Raumgruppen-Items
    # tragen P589, gemessen 2026-08-19). Abgelesen statt abgebildet: eine
    # eigene Tabelle waere eine zweite Wahrheit.
    "point_group": {
        "pid": "P589",
        "datatype": "item",
        "unit_qid": "",
        "label": "Punktgruppe",
    },
    "cod_id": {
        "pid": "P9824",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "COD-ID",
    },
    # Die chemischen Elemente eines Stoffs, je Element eine Aussage.
    # Itemwertig, aufgeloest ueber fetch_element_qids - eine value_map waere
    # hier eine zweite Elementtabelle.
    #
    # P2670 "enthaelt Elemente von", NICHT P527 "besteht aus": das Item eines
    # Elements ist die KLASSE seiner Atome, kein einzelnes Stueck Materie.
    # "Wasser besteht aus Wasserstoff" waere mereologisch falsch, "Wasser
    # enthaelt Teile der Klasse Wasserstoff" trifft es. Vorbild im Bestand
    # sind Kohlenstoffdioxid (Q1997) und Kohlenstoffmonoxid (Q2025): P2670 ->
    # Element mit P1114 als Anzahl. Genau diese Form wird erzeugt.
    "has_part_of_class": {
        "pid": "P2670",
        "datatype": "item",
        "unit_qid": "",
        "label": "enthaelt Elemente von",
    },
    # Nur fuer die UMSTELLUNG gebraucht: die alte, mereologisch falsche
    # Aussage wird damit zum Entfernen ausgewiesen. Erzeugt wird P527 nie.
    "has_part": {
        "pid": "P527",
        "datatype": "item",
        "unit_qid": "",
        "label": "besteht aus",
    },
    # Thermochemie aus dem NIST Chemistry WebBook. Beide Properties
    # VERLANGEN laut Constraint den Aggregatzustand als Qualifikator (P515) -
    # ohne ihn ist die Zahl bedeutungslos, weil ΔfH° von Feststoff, Fluessig-
    # keit und Gas verschieden ist. Genau in dieser Aufteilung liefert das
    # WebBook sie auch ("ΔfH°solid", "ΔfH°gas").
    "formation_enthalpy": {
        "pid": "P3078",
        "datatype": "quantity",
        "unit_qid": "Q752197",  # Kilojoule pro Mol, kJ/mol
        "label": "Standardbildungsenthalpie",
    },
    "molar_entropy": {
        "pid": "P3071",
        "datatype": "quantity",
        "unit_qid": "Q20966455",  # Joule pro Molkelvin, J/(mol*K)
        "label": "molare Standardentropie",
    },
}


NUR_FESTKOERPER = ("bulk_modulus", "shear_modulus", "poisson_ratio",
                   "density", "crystal_system", "space_group", "point_group",
                   "linear_thermal_expansion")
RAUMTEMPERATUR_K = 293.15

# P2102 wird in Wikidata in drei Einheiten gefuehrt (am Bestand: 32x Celsius,
# 27x Fahrenheit, 11x Kelvin). Wikidatas normalisierte Werte (psn:) helfen
# nicht: Celsius -> Kelvin ist eine Verschiebung, und normalisiert wird nur
# multiplikativ. Deshalb hier selbst umrechnen - sonst gilt Fluor mit "-307"
# (Fahrenheit) als absurd kalt und Iod mit "184,4" (Celsius) als Gas.
TEMPERATUR_NACH_KELVIN = {
    "Q11579": lambda x: x,                      # Kelvin
    "Q25267": lambda x: x + 273.15,             # Grad Celsius
    "Q42289": lambda x: (x - 32) * 5 / 9 + 273.15,   # Grad Fahrenheit
}


# ---------------------------------------------------------------------------
# Feldkarten der Wikipedia-Infoboxen
# ---------------------------------------------------------------------------
#
# Feldname der Vorlage -> (interner Schluessel, Faktor auf die
# Wikidata-Einheit). Reine Tabellen; wie die Felder gelesen werden, steht
# in infobox.py.

# Infobox-Feld -> (interner Schluessel, Faktor auf die Wikidata-Einheit)
WIKIPEDIA_DE_FIELDS = {
    "Schmelzpunkt_K": ("melting_point", 1.0),            # K
    "Siedepunkt_K": ("boiling_point", 1.0),              # K
    "Dichte": ("density", 1.0),                          # g/cm^3
    "Wärmeleitfähigkeit": ("thermal_conductivity", 1.0),  # W/(m*K)
    "ElektrischeLeitfähigkeit": ("electrical_conductivity", 1.0),  # S/m
    "SpezifischeWärmekapazität": ("specific_heat_capacity", 1.0),  # J/(kg*K)
    "Schallgeschwindigkeit": ("speed_of_sound", 1.0),    # m/s
    "Poissonzahl": ("poisson_ratio", 1.0),               # dimensionslos
}


# Verbindungen stehen in der deutschen Wikipedia nicht in der Elementinfobox,
# sondern in {{Infobox Chemikalie}}. Deren Felder heissen anders und - der
# entscheidende Unterschied - die Temperaturen stehen in GRAD CELSIUS:
#   | Schmelzpunkt = 1855 [[Grad Celsius|°C]]<ref .../>
#   | Siedepunkt   = 2900 °C
#   | Dichte       = 4,23 g·cm<sup>−3</sup>
#   | CAS          = {{CASRN|13463-67-7}}
# Ein Artikel traegt immer nur eine der beiden Infoboxen, deshalb koennen
# beide Feldsaetze gefahrlos nacheinander auf denselben Wikitext angewendet
# werden.
WIKIPEDIA_DE_CHEM_FIELDS = {
    "Dichte": ("density", 1.0),   # g/cm^3
}


# Infobox-Feld -> (interner Schluessel, Umrechnung in die Wikidata-Einheit)
WIKIPEDIA_NUMERIC_FIELDS = {
    "melting point K": ("melting_point", 1.0),        # schon Kelvin
    "boiling point K": ("boiling_point", 1.0),        # schon Kelvin
    "thermal conductivity": ("thermal_conductivity", 1.0),  # W/(m*K)
}


# Feld -> (interner Schluessel, Faktor, Offset auf die Wikidata-Einheit)
CHEMBOX_FIELDS = {
    "MeltingPtK": ("melting_point", 1.0, 0.0),
    "MeltingPtC": ("melting_point", 1.0, 273.15),
    "BoilingPtK": ("boiling_point", 1.0, 0.0),
    "BoilingPtC": ("boiling_point", 1.0, 273.15),
    "Density": ("density", 1.0, 0.0),             # g/cm^3
}


# Was eine Stufe HOECHSTENS liefern kann. Traegt das Item das alles schon,
# braucht die Quelle gar nicht erst befragt zu werden - das spart bei den
# teuren Stufen den ganzen Abruf, nicht bloss die Zeile.
def _pids(*schluessel) -> frozenset:
    return frozenset(PROPERTY_MAP[k]["pid"] for k in schluessel)


STUFEN_PIDS = {
    "cod": _pids("cod_id", "space_group", "crystal_system", "point_group"),
    "mp": frozenset(PROPERTY_MAP[k]["pid"]
                    for k, _ in MP_FIELD_MAP.values() if k in PROPERTY_MAP),
    "nist": _pids("formation_enthalpy", "molar_entropy"),
    # Die Infoboxen liefern alles, was in den vier Feldkarten steht, dazu
    # Kristallsystem, CAS-Nummer und Laengenausdehnungskoeffizient.
    "wikipedia": frozenset(
        [PROPERTY_MAP[k]["pid"] for k, _ in WIKIPEDIA_DE_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k, _ in WIKIPEDIA_DE_CHEM_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k, _ in WIKIPEDIA_NUMERIC_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k, _, _ in CHEMBOX_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k in
           ("crystal_system", "cas_number", "density", "melting_point",
            "boiling_point", "electrical_resistivity",
            "linear_thermal_expansion")]),
}
