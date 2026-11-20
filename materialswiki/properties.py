"""Was womit nach Wikidata geht: Properties, Einheiten, Schranken.

Reine Tabellen und die zwei kleinen Funktionen, die sie auswerten. Kein Netz,
keine Logik der Stufen - deshalb eine eigene Datei, die jedes Modul laden
kann, ohne den ganzen Apparat mitzuziehen.

NUR mit auf wikidata.org verifizierten Properties befuellen; welche bewusst
fehlen und warum, steht im README ("Abgedeckte Properties").
"""

# MP-Feldpfad -> (interner Schluessel, Faktor auf die Wikidata-Einheit).
# Seit dem 2026-08-28 ist hier NICHTS mehr umzurechnen: die Moduln gehen in
# GIGAPASCAL nach Wikidata - genau der Einheit, in der MP sie liefert -, und
# die Dichte in g/cm^3, ebenfalls unveraendert. Warum Gigapascal und nicht
# Pascal: der Einheiten-Constraint von P5668 und P5673 laesst NUR Q53448922
# (Gigapascal) zu, am 2026-08-28 ausgelesen. Vorher standen die Werte in
# Pascal, was jede erzeugte Aussage zu einer Constraint-Verletzung machte.
#
# Welche MP-Felder bewusst NICHT uebernommen sind (band_gap und weitere) und
# warum: README, "Abgedeckte Properties".
MP_FIELD_MAP = {
    "density": ("density", 1.0),                       # g/cm^3, unveraendert
    "symmetry.crystal_system": ("crystal_system", None),  # itemwertig
    "bulk_modulus.vrh": ("bulk_modulus", 1.0),         # GPa, unveraendert
    "shear_modulus.vrh": ("shear_modulus", 1.0),       # GPa, unveraendert
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
DRUCK_PID = "P2077"   # Pflicht-Qualifikator der Phasenpunkte (P873)
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
#                Diamant (Kompressionsmodul ~443 GPa, Schubmodul ~535 GPa).
#                Die Schranken stehen in GIGAPASCAL, seit die Moduln so
#                nach Wikidata gehen
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
    "bulk_modulus": (0.001, 1000.0),       # GPa
    "shear_modulus": (0.001, 1000.0),      # GPa
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
    # Mohshaerte: die Skala selbst reicht von Talk (1) bis Diamant (10), und
    # P1088 traegt genau diesen Bereichs-Constraint (am 2026-08-23
    # ausgelesen; der obere Rand 10 ist per Ausnahme nur dem Diamanten
    # Q5283 erlaubt). Weichere Stoffe bekommen in den Infoboxen trotzdem
    # Werte darunter - Caesium steht mit 0,2 in der Elementinfobox. Die
    # landen damit in der manuellen Klaerung statt im Entwurf, und das ist
    # richtig so: in Wikidata waeren sie eine Constraint-Verletzung.
    "mohs_hardness": (1.0, 10.0),               # dimensionslos
    # --- Erweiterung der Infobox-Feldkarten (2026-11-20) -------------------
    # Spannweiten an allen 118 Elementinfoboxen (de und en) abgelesen, wie
    # oben grosszuegig gefasst.
    # Schmelzwaerme: Helium 0,0138 bis Kohlenstoff ~117 kJ/mol.
    "molar_fusion_enthalpy": (0.001, 200.0),        # kJ/mol
    # Verdampfungswaerme: Helium 0,083 bis Wolfram ~824 kJ/mol.
    "molar_vaporization_enthalpy": (0.01, 1000.0),  # kJ/mol
    # Pauling-Skala: Caesium 0,79 bis Fluor 3,98.
    "electronegativity": (0.5, 4.5),                # dimensionslos
    # Erste Ionisierungsenergie: Caesium 375,7 bis Helium 2372,3 kJ/mol.
    "ionization_energy": (300.0, 3000.0),           # kJ/mol
    # Radien in Pikometer: Helium ~28 (kovalent) bis Caesium ~343 (vdW).
    "atomic_radius": (10.0, 400.0),                 # pm
    "covalent_radius": (10.0, 400.0),               # pm
    "van_der_waals_radius": (10.0, 400.0),          # pm
    # E-Modul: Caesium 1,7 GPa bis Diamant ~1050 GPa.
    "tensile_modulus": (0.001, 1500.0),             # GPa
    # Temperaturleitfaehigkeit: Metalle 5 bis ~175 mm^2/s, Diamant >1000.
    "thermal_diffusivity": (0.01, 2000.0),          # mm^2/s
    # Molares Volumen des Festkoerpers: Kohlenstoff 3,4e-6 bis Caesium
    # 70,9e-6 m^3/mol. Ein Gasvolumen (22,4e-3) faellt hier heraus.
    "molar_volume": (1e-6, 1e-4),                   # m^3/mol
    # Dampfdruck: Bismut 5,78e-21 Pa (505 K) bis Brom 4,13e6 Pa.
    "vapor_pressure": (1e-30, 1e9),                 # Pa
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
    # Magnetische Ordnung aus {{Infobox Chemisches Element}}, Feld "Magnetismus"
    # ("ferromagnetisch", "paramagnetisch", ...). P1552 "has characteristic"
    # ist itemwertig; die value_map uebersetzt die deutschen Stichworte in die
    # Items der Phaenomene. Warum P1552 und NICHT eine P279/P31-Kante auf eine
    # Magnetwerkstoff-Klasse: das magnetische Verhalten ist ein Merkmal, das
    # quer zu mehreren Taxonomie-Aesten auftritt - Begruendung in
    # proposals/ferromagnetika_pruefung_2026-08-30.md ("konkrete Werkstoffe /
    # Elemente"). Eisen (Q677) und Nickel (Q744) tragen "P1552 -> Q184207"
    # bereits; die Pruefung "schon vorhanden?" muss deshalb auf den WERT gehen
    # und nicht bloss auf die PID (siehe _infobox_proposals).
    #
    # Ein Wert ausserhalb der value_map wird NICHT geraten, sondern zur
    # manuellen Klaerung markiert; nennt das Feld mehrere Ordnungen (Chrom:
    # "antiferromagnetisch, paramagnetisch"), wird gar nichts vorgeschlagen.
    "magnetism": {
        "pid": "P1552",
        "datatype": "item",
        "unit_qid": "",
        "label": "charakterisiert durch",
        "value_map": {
            "ferromagnetisch": ("Q184207", "Ferromagnetismus"),
            "ferrimagnetisch": ("Q217121", "Ferrimagnetismus"),
            "antiferromagnetisch": ("Q575224", "Antiferromagnetismus"),
            "paramagnetisch": ("Q188479", "Paramagnetismus"),
            "diamagnetisch": ("Q201048", "Diamagnetismus"),
        },
    },
    # Elastische Moduln. MP fuehrt sie als Objekt mit voigt/reuss/vrh;
    # genommen wird das Voigt-Reuss-Hill-Mittel (Pfad "...vrh" in
    # MP_FIELD_MAP), das uebliche Mittel fuer polykristalline Werkstoffe.
    #
    # Einheit ist GIGAPASCAL, nicht Pascal: der Einheiten-Constraint beider
    # Properties (P2302 -> Q21514353, am 2026-08-28 ausgelesen) laesst
    # AUSSCHLIESSLICH Q53448922 zu. Bis dahin schrieb das Werkzeug Pascal und
    # rechnete dafuer eigens mit 1e9 hoch - jede so erzeugte Aussage war eine
    # Constraint-Verletzung. Jetzt geht der MP-Wert unveraendert raus.
    "bulk_modulus": {
        "pid": "P5668",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Gigapascal
        "label": "Kompressionsmodul",
    },
    "shear_modulus": {
        "pid": "P5673",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Gigapascal
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
    # Mohshaerte: eine Ordnungszahl auf der Ritzskala, also dimensionslos -
    # P1088 laesst laut Constraint (2026-08-23) nur die Einheit "1" zu.
    # Quelle sind ausschliesslich die Infoboxen: das Materials Project
    # rechnet keine Haerte, und die deutsche Wikipedia fuehrt das Feld
    # "Mohshaerte" sowohl in {{Infobox Chemisches Element}} als auch in
    # {{Infobox Mineral}} - dieselbe Feldkarte bedient beide.
    "mohs_hardness": {
        "pid": "P1088",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos
        "label": "Mohshaerte",
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
    # Zwei Verwendungen, beide in ableitungen.py:
    #   die UMSTELLUNG weist damit die alte, mereologisch falsche Aussage
    #   "Stoff P527 Element" zum Entfernen aus,
    #   die GRUPPENSTUFE erzeugt damit neue Aussagen - hier ist P527 richtig:
    #   ein Sulfation in Gips IST ein Stueck Materie, keine Klasse.
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
    # =======================================================================
    # Die uebrigen Properties des WikiProject Materials
    # =======================================================================
    #
    # Die 44 Eintraege unten kommen aus benchmark/properties_snapshot.json,
    # also aus den Abschnitten Physics, Mechanical, Thermal, Chemical und
    # "Electric and Magnetic" von [[Wikidata:WikiProject Materials/Properties]].
    # Damit deckt PROPERTY_MAP die Projektseite vollstaendig ab.
    #
    # ACHTUNG - eintragen heisst nicht liefern: fuer die meisten dieser
    # Properties erzeugt KEINE Stufe eine Aussage. Es gibt weder ein MP-Feld
    # noch eine Infobox-Feldkarte dafuer; sie sind hier nur bekannt, nicht
    # bedient. Ausnahmen seit 2026-11-20: E-Modul (P5480) und
    # Temperaturleitfaehigkeit (P5674) liefert die englische Elementinfobox.
    # Was ein Lauf wirklich abfragt, steht in der Spalte "quellen" des
    # Benchmarks, nicht in dieser Tabelle.
    #
    # Datentyp und Einheit sind am 2026-08-28 von wikidata.org geholt
    # (wbgetentities: datatype, und der Einheiten-Constraint P2302 ->
    # Q21514353 mit seinen P2305-Werten), nicht geschaetzt. Wo der Constraint
    # mehrere Einheiten zulaesst, gilt: Gigapascal, wo der Constraint es
    # hergibt (wie bei P5668/P5673), Kelvin bei Temperaturen (wie
    # P2101/P2102), sonst die SI-Einheit. Wo er FEHLT, steht unit_qid leer:
    # eine Einheit zu
    # erfinden waere schlimmer als keine - sie ist festzulegen, sobald eine
    # Quelle den Wert wirklich liefert.
    #
    # Die Datentypen string und commonsMedia (P274, P994, P117) kann
    # ausgabe.py bisher nicht schreiben; auch das faellt erst an, wenn eine
    # Quelle sie liefert.
    # -- Mechanical --------------------------------------------------------
    "kinematic_viscosity": {
        "pid": "P2118",
        "datatype": "quantity",
        "unit_qid": "Q3332099",  # Quadratmeter pro Sekunde (SI)
        "label": "kinematische Viskosität",
    },
    "dynamic_viscosity": {
        "pid": "P3070",
        "datatype": "quantity",
        "unit_qid": "Q21016931",  # Pascalsekunde (SI)
        "label": "dynamische Viskosität",
    },
    "ultimate_tensile_strength": {
        "pid": "P5479",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "Zugfestigkeit",
    },
    "tensile_modulus": {
        "pid": "P5480",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Gigapascal, wie P5668/P5673
        "label": "Elastizitätsmodul",
    },
    "hardness": {
        "pid": "P5483",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint; die Skala haengt am Verfahren
        "label": "Härte",
    },
    "toughness": {
        "pid": "P5520",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "Zähigkeit",
    },
    "yield_strength": {
        "pid": "P5529",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal - Gigapascal ist hier NICHT erlaubt
        "label": "Fließgrenze",
    },
    "coefficient_of_friction": {
        "pid": "P5575",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "Reibungskoeffizient",
    },
    "fatigue_limit": {
        "pid": "P5608",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal - Gigapascal ist hier NICHT erlaubt
        "label": "Dauerfestigkeit",
    },
    "compressive_strength": {
        "pid": "P5669",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "Druckfestigkeit",
    },
    "flexural_strength": {
        "pid": "P5677",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Gigapascal - Pascal ist hier NICHT erlaubt
        "label": "Biegefestigkeit",
    },
    "flexural_modulus": {
        "pid": "P5681",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Constraint laesst NUR Gigapascal zu
        "label": "Biegemodul",
    },
    "tear_resistance": {
        "pid": "P5685",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Constraint laesst NUR Gigapascal zu
        "label": "Reißfestigkeit",
    },
    "shear_strength": {
        "pid": "P5706",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal - Gigapascal ist hier NICHT erlaubt
        "label": "Scherfestigkeit",
    },
    "force": {
        "pid": "P5708",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "force",
    },
    "abrasion_resistance": {
        "pid": "P5709",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "Abriebfestigkeit",
    },
    "elongation_at_break": {
        "pid": "P5811",
        "datatype": "quantity",
        "unit_qid": "Q11229",  # Constraint laesst NUR Prozent zu
        "label": "Bruchdehnung",
    },
    "compressive_modulus": {
        "pid": "P5993",
        "datatype": "quantity",
        "unit_qid": "Q53448922",  # Gigapascal
        "label": "compressive modulus of elasticity",
    },
    "flexural_strain_at_break": {
        "pid": "P6014",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "flexural strain at break",
    },
    # -- Thermal -----------------------------------------------------------
    "emissivity": {
        "pid": "P1295",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "Emissionsgrad",
    },
    "sublimation_temperature": {
        "pid": "P2113",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Sublimationstemperatur",
    },
    "flash_point": {
        "pid": "P2128",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Flammpunkt",
    },
    "autoignition_temperature": {
        "pid": "P2199",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Zündtemperatur",
    },
    "operating_temperature": {
        "pid": "P5066",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Betriebstemperatur",
    },
    "glass_transition_temperature": {
        "pid": "P5670",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Glasübergangstemperatur",
    },
    # Seit 2026-11-20 bedient (englische Elementinfobox, Feld "thermal
    # diffusivity"). Die Vorlage rechnet in mm^2/s, und der Constraint
    # laesst Q26162546 ausdruecklich zu - also die Einheit der Quelle statt
    # der bisherigen Platzhalter-SI-Einheit m^2/s, nichts umzurechnen.
    "thermal_diffusivity": {
        "pid": "P5674",
        "datatype": "quantity",
        "unit_qid": "Q26162546",  # Quadratmillimeter pro Sekunde
        "label": "Temperaturleitfähigkeit",
    },
    "heat_deflection_temperature": {
        "pid": "P5682",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Wärmeformbeständigkeitstemperatur",
    },
    "vicat_softening_point": {
        "pid": "P5947",
        "datatype": "quantity",
        "unit_qid": "Q25267",  # Constraint laesst NUR Grad Celsius zu
        "label": "Vicat softening point",
    },
    "nfpa_fire": {
        "pid": "P994",
        "datatype": "string",
        "unit_qid": "",
        "label": "NFPA-Code für Brandgefahr",
    },
    # -- Chemical ----------------------------------------------------------
    "proportion": {
        "pid": "P1107",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "Anteil",
    },
    "chemical_structure": {
        "pid": "P117",
        "datatype": "commonsMedia",
        "unit_qid": "",  # Bilddatei auf Commons
        "label": "chemische Struktur",
    },
    "solvent": {
        "pid": "P2178",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Lösungsmittel",
    },
    "inchi": {
        "pid": "P234",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "InChI",
    },
    "chemical_formula": {
        "pid": "P274",
        "datatype": "string",
        "unit_qid": "",
        "label": "chemische Formel",
    },
    "part_of": {
        "pid": "P361",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "ist Teil von",
    },
    "monomer_of": {
        "pid": "P4599",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Monomer von",
    },
    "polymer_of": {
        "pid": "P4600",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Polymer aus",
    },
    "lower_limit": {
        "pid": "P5447",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "unterer Grenzwert",
    },
    "upper_limit": {
        "pid": "P5448",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "oberer Grenzwert",
    },
    "moisture_absorption": {
        "pid": "P5594",
        "datatype": "quantity",
        "unit_qid": "Q11229",  # Prozent
        "label": "Feuchtigkeitsaufnahme",
    },
    "pren": {
        "pid": "P5624",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "PREN",
    },
    "permeability": {
        "pid": "P6073",
        "datatype": "quantity",
        "unit_qid": "Q808873",  # Constraint laesst NUR Barrer zu
        "label": "Permeabilität",
    },
    # -- Electric and Magnetic ---------------------------------------------
    "relative_permittivity": {
        "pid": "P5675",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "relative permittivity",
    },
    "relative_permeability": {
        "pid": "P5676",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "relative permeabilität",
    },
    # =======================================================================
    # Ueber die Projektseite hinaus: von den Infoboxen BEDIENT (2026-11-20)
    # =======================================================================
    #
    # Diese Properties stehen NICHT auf [[Wikidata:WikiProject Materials/
    # Properties]], existieren aber und werden von den Elementinfoboxen
    # geliefert. Datentyp, Einheiten- und Pflicht-Qualifikator-Constraint am
    # 2026-11-20 von wikidata.org gelesen. Welche Feldkarte sie fuellt:
    # WIKIPEDIA_DE_FIELDS / WIKIPEDIA_NUMERIC_FIELDS unten; welche
    # Qualifikatoren sie tragen: PFLICHT_TEMPERATUR / FESTE_QUALIFIKATOREN.
    #
    # Verlangt P2076 (Temperatur): der Schmelzpunkt derselben Infobox.
    "molar_fusion_enthalpy": {
        "pid": "P2066",
        "datatype": "quantity",
        "unit_qid": "Q752197",  # Kilojoule pro Mol - Einheit beider Infoboxen
        "label": "molare Schmelzwärme",
    },
    # Verlangt P2076: der Siedepunkt derselben Infobox (die Werte beider
    # Infoboxen sind Verdampfungswaermen am Normalsiedepunkt, de zitiert
    # dafuer durchgehend Zhang et al. 2011).
    "molar_vaporization_enthalpy": {
        "pid": "P2116",
        "datatype": "quantity",
        "unit_qid": "Q752197",  # Kilojoule pro Mol
        "label": "molare Verdampfungswärme",
    },
    # Phasenpunkt: Tripelpunkt und kritischer Punkt, jeweils mit Temperatur
    # (P2076) UND Druck (P2077) als Pflicht-Qualifikator. Der one-of-
    # Constraint laesst genau diese zwei Werte zu. Eine Property, zwei
    # moegliche Aussagen je Item - deshalb eine eigene Stufe
    # (infobox.phasenpunkt_proposals_for_item) statt der Feldkarte, und die
    # Pruefung "schon vorhanden?" geht wie bei P1552 auf den WERT.
    "phase_point": {
        "pid": "P873",
        "datatype": "item",
        "unit_qid": "",
        "label": "Phasenpunkt",
        "value_map": {
            "triple point": ("Q106410", "Tripelpunkt"),
            "critical point": ("Q111059", "kritischer Punkt"),
        },
    },
    # Verlangt P2076: das Feld "RefTempDampfdruck_K" der de-Elementinfobox.
    # Ohne diese Temperatur wird gar nichts vorgeschlagen.
    "vapor_pressure": {
        "pid": "P2119",
        "datatype": "quantity",
        "unit_qid": "Q44395",  # Pascal - die Vorlage haengt "Pa" an
        "label": "Dampfdruck",
    },
    # Bisher an keinem einzigen Item (0 Verwendungen am 2026-11-20). Die
    # Vorlage haengt m^3*mol^-1 an; diese Einheit ist erlaubt, also keine
    # Umrechnung.
    "molar_volume": {
        "pid": "P2807",
        "datatype": "quantity",
        "unit_qid": "Q21615967",  # Kubikmeter pro Mol
        "label": "molares Volumen",
    },
    # Pauling-Skala - beide Vorlagen nennen sie ausdruecklich. Der
    # Constraint verlangt "keine Einheit" (Bestand: Einheit 1, kein
    # Qualifikator).
    "electronegativity": {
        "pid": "P1108",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "Elektronegativität",
    },
    # Verlangt P1545 (Seriennummer): welche Ionisierung gemeint ist. Der
    # Bestand fuehrt die Werte in eV mit P1545 = "1", "2", "3"; kJ/mol ist
    # ebenso erlaubt und die Einheit der en-Vorlage. Die de-Vorlage wird
    # NICHT gelesen: dort steht eV und kJ/mol nebeneinander in {{ZahlExp}}.
    "ionization_energy": {
        "pid": "P2260",
        "datatype": "quantity",
        "unit_qid": "Q752197",  # Kilojoule pro Mol
        "label": "Ionisierungsenergie",
    },
    # Die drei Radien: Constraint nur Pikometer, kein Qualifikator. Beide
    # Vorlagen rechnen in pm. Achtung: de "Atomradius" (Slater, auf 5 pm
    # gerundet) und en "atomic radius" (empirisch) weichen voneinander ab -
    # Eisen traegt deshalb schon zwei P14936-Werte (126 und 140 pm). Weil die
    # Kaskade de vor en fragt und "schon vorhanden" auf die PID prueft, kommt
    # hoechstens EIN neuer Wert dazu.
    "atomic_radius": {
        "pid": "P14936",
        "datatype": "quantity",
        "unit_qid": "Q192274",  # Pikometer
        "label": "Atomradius",
    },
    "covalent_radius": {
        "pid": "P14937",
        "datatype": "quantity",
        "unit_qid": "Q192274",  # Pikometer
        "label": "Kovalenzradius",
    },
    "van_der_waals_radius": {
        "pid": "P14938",
        "datatype": "quantity",
        "unit_qid": "Q192274",  # Pikometer
        "label": "Van-der-Waals-Radius",
    },
    # EG- und ECHA-Nummer: Identifikatoren, gehen also ohne Beleg raus
    # (OHNE_BELEG_DATENTYPEN). Beide Infoboxen (Element wie Chemikalie)
    # fuehren sie unter denselben Feldnamen.
    "ec_number": {
        "pid": "P232",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "EG-Nummer",
    },
    "echa_infocard": {
        "pid": "P2566",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "ECHA-InfoCard-ID",
    },
    # =======================================================================
    # Ueber die Projektseite hinaus: nur BEKANNT, nicht bedient
    # =======================================================================
    #
    # Existieren in Wikidata, stehen nicht auf der Projektseite und werden
    # von KEINER Stufe geliefert. Datentyp und Einheiten-Constraint am
    # 2026-11-20 gelesen; wie oben bleibt unit_qid leer, wo der Constraint
    # fehlt oder offensichtlich falsch ist.
    #
    # Materials Project ID: die MP-Stufe haelt die mp-ID schon in der Hand
    # (MP_META_FIELDS), schreibt sie aber nicht. Offen, weil (a) der
    # Subjekt-Constraint nur "chemical compound" (Q11173) zulaesst - an einem
    # Element waere die Aussage eine Verletzung - und (b) eine mp-ID EIN
    # Polymorph bezeichnet, ein Verbindungs-Item wie Titandioxid aber alle.
    "materials_project_id": {
        "pid": "P9902",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "Materials-Project-ID",
    },
    # OFFENE FRAGE, nicht bedient: P922 "magnetische Ordnung" ist die eigens
    # dafuer angelegte Property (Subjekt-Constraint metal Q11426, one-of genau
    # die fuenf Werte der value_map von "magnetism" oben). Die Hausregel
    # .claude/rules/ontology-magnetismus-p1552.md setzt dagegen P1552. Ob P922
    # statt oder neben P1552 gelten soll, ist nicht entschieden - siehe
    # proposals/review-needed.md ("P922 magnetic ordering"). Bis dahin
    # liefert die Magnetismus-Stufe unveraendert P1552.
    "magnetic_ordering": {
        "pid": "P922",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "magnetische Ordnung",
    },
    # Constraint nennt Hertz und Temperatur - offensichtlich fehlerhaft, der
    # Verlustfaktor tan(delta) ist dimensionslos. Einheit erst festlegen,
    # wenn eine Quelle liefert.
    "dissipation_factor": {
        "pid": "P5678",
        "datatype": "quantity",
        "unit_qid": "",
        "label": "Verlustfaktor",
    },
    "dielectric_strength": {
        "pid": "P14669",
        "datatype": "quantity",
        "unit_qid": "Q3562962",  # Volt pro Meter - einzige erlaubte Einheit
        "label": "Durchschlagfestigkeit",
    },
    # Schwindung und Rauheit stehen auf der Projektseite noch als
    # "Property proposal", existieren aber laengst.
    "shrinkage": {
        "pid": "P7079",
        "datatype": "quantity",
        "unit_qid": "Q11229",  # Prozent - einzige erlaubte Einheit
        "label": "Schwindung",
    },
    "surface_roughness": {
        "pid": "P7083",
        "datatype": "quantity",
        "unit_qid": "",  # kein Constraint
        "label": "Rauheit",
    },
    "combustion_enthalpy": {
        "pid": "P2117",
        "datatype": "quantity",
        "unit_qid": "Q752197",  # Kilojoule pro Mol, wie P2066/P2116
        "label": "Verbrennungsenthalpie",
    },
    "decomposition_point": {
        "pid": "P2107",
        "datatype": "quantity",
        "unit_qid": "Q11579",  # Kelvin, wie P2101/P2102
        "label": "Zersetzungstemperatur",
    },
    "surface_tension": {
        "pid": "P3013",
        "datatype": "quantity",
        "unit_qid": "Q12371104",  # Newton pro Meter (SI)
        "label": "Oberflächenspannung",
    },
    "lower_flammable_limit": {
        "pid": "P2202",
        "datatype": "quantity",
        "unit_qid": "Q2080811",  # Volumenprozent
        "label": "untere Explosionsgrenze",
    },
    "upper_flammable_limit": {
        "pid": "P2203",
        "datatype": "quantity",
        "unit_qid": "Q2080811",  # Volumenprozent
        "label": "obere Explosionsgrenze",
    },
    "oxidation_state": {
        "pid": "P1121",
        "datatype": "quantity",
        "unit_qid": "",  # dimensionslos laut Constraint
        "label": "Oxidationsstufe",
    },
    # Mineralogie: {{Infobox Mineral}} fuehrt die meisten davon, aber als
    # Freitext - itemwertige Properties brauchen erst eine value_map.
    "mindat_mineral_id": {
        "pid": "P6263",
        "datatype": "external-id",
        "unit_qid": "",
        "label": "Mindat-Mineralkennung",
    },
    "ima_mineral_symbol": {
        "pid": "P10113",
        "datatype": "string",
        "unit_qid": "",
        "label": "IMA-Symbol",
    },
    "streak_color": {
        "pid": "P534",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Strichfarbe",
    },
    "crystal_habit": {
        "pid": "P565",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Kristallhabitus",
    },
    "cleavage": {
        "pid": "P693",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Spaltbarkeit",
    },
    "mineral_fracture": {
        "pid": "P538",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Bruch",
    },
    "twinning": {
        "pid": "P537",
        "datatype": "wikibase-item",
        "unit_qid": "",
        "label": "Verzwilligung",
    },
}


NUR_FESTKOERPER = ("bulk_modulus", "shear_modulus", "poisson_ratio",
                   "density", "crystal_system", "space_group", "point_group",
                   "linear_thermal_expansion", "mohs_hardness",
                   # seit 2026-11-20: E-Modul, und das molare Volumen - die
                   # de-Vorlage nennt bei Gasen das des Festkoerpers "(fest)"
                   "tensile_modulus", "molar_volume")
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
    # Steht in der Elementinfobox ("| Mohshärte = 3,0") und - unter genau
    # demselben Feldnamen - in {{Infobox Mineral}} ("| Mohshärte = 7").
    # Ein Artikel traegt immer nur eine der beiden Vorlagen, deshalb genuegt
    # dieser eine Eintrag fuer Elemente wie Minerale.
    "Mohshärte": ("mohs_hardness", 1.0),                 # dimensionslos
    # --- seit 2026-11-20 -------------------------------------------------
    # Einheiten laut Vorlagenquelltext (Vorlage:Infobox Chemisches Element):
    # die Vorlage haengt kJ*mol^-1, pm und m^3*mol^-1 selbst an. Nur
    # "Verdampfungswaerme" schreibt die Einheit ins Feld - parse_de_number
    # trennt sie ab.
    "Schmelzwärme": ("molar_fusion_enthalpy", 1.0),       # kJ/mol
    "Verdampfungswärme": ("molar_vaporization_enthalpy", 1.0),  # kJ/mol
    "Elektronegativität": ("electronegativity", 1.0),     # Pauling-Skala
    # "Atomradius" ist der empirische Wert; der berechnete steht im eigenen
    # Feld "AtomradiusBerechnet" und wird nicht gelesen.
    "Atomradius": ("atomic_radius", 1.0),                 # pm
    "KovalenterRadius": ("covalent_radius", 1.0),         # pm
    "VanDerWaalsRadius": ("van_der_waals_radius", 1.0),   # pm
    "MolaresVolumen": ("molar_volume", 1.0),              # m^3/mol
    # Nur drei Elemente fuellen das Feld (Titan, Kupfer, Blei, 2026-11-20).
    "E-Modul": ("tensile_modulus", 1.0),                  # GPa
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
    "Mohs hardness": ("mohs_hardness", 1.0),          # dimensionslos
    # --- seit 2026-11-20 -------------------------------------------------
    # Einheiten laut {{Infobox element}}: kJ/mol, pm, GPa, mm^2/s. An allen
    # 118 Vorlagen abgelesen; Werte mit Modifikation ("diamond: 1050"),
    # Molekuelbezug ("(N<sub>2</sub>) 0.72") oder Bereich ("130-188")
    # verwirft parse_wiki_number.
    "heat fusion": ("molar_fusion_enthalpy", 1.0),          # kJ/mol
    "heat vaporization": ("molar_vaporization_enthalpy", 1.0),  # kJ/mol
    "electronegativity": ("electronegativity", 1.0),        # Pauling-Skala
    "ionization energy 1": ("ionization_energy", 1.0),      # kJ/mol
    "atomic radius": ("atomic_radius", 1.0),                # pm, empirisch
    "covalent radius": ("covalent_radius", 1.0),            # pm
    "Van der Waals radius": ("van_der_waals_radius", 1.0),  # pm
    # Elastische Konstanten als MESSWERTE. Im Lauf fragt die MP-Stufe vor
    # der Wikipedia; Kompressions-, Schubmodul und Poissonzahl kommen hier
    # also nur an, wo MP nichts liefert (oder mit --no-mp).
    "Young's modulus": ("tensile_modulus", 1.0),            # GPa
    "Shear modulus": ("shear_modulus", 1.0),                # GPa
    "Bulk modulus": ("bulk_modulus", 1.0),                  # GPa
    "Poisson ratio": ("poisson_ratio", 1.0),                # dimensionslos
    "thermal diffusivity": ("thermal_diffusivity", 1.0),    # mm^2/s
}


# ---------------------------------------------------------------------------
# Pflicht-Qualifikatoren der Infobox-Groessen
# ---------------------------------------------------------------------------
#
# Mehrere der seit 2026-11-20 bedienten Properties tragen einen required-
# qualifier-Constraint (am selben Tag gelesen). Ohne den Qualifikator waere
# jede erzeugte Aussage eine Constraint-Verletzung.
#
# PFLICHT_TEMPERATUR: interner Schluessel -> woher die Temperatur (P2076)
# kommt. Ein Schluessel aus derselben Infobox (Wert in Kelvin), oder None
# fuer "die Quelle nennt keine - Raumtemperatur annehmen". Letzteres nach
# derselben Konvention wie bei der Dichte (STANDARD_TEMPERATUR_C), und es
# steht ausdruecklich in der Notiz der Zeile.
#
# Fehlt die Bezugstemperatur (kein Schmelzpunkt in der Infobox), wird die
# Zeile zur MANUELLEN KLAERUNG ausgewiesen, nicht ohne Qualifikator
# vorgeschlagen.
PFLICHT_TEMPERATUR = {
    "molar_fusion_enthalpy": "melting_point",       # P2066 am Schmelzpunkt
    "molar_vaporization_enthalpy": "boiling_point",  # P2116 am Siedepunkt
    # Hilfsschluessel, NICHT in PROPERTY_MAP: die Bezugstemperatur aus
    # "RefTempDampfdruck_K", von wikipedia_de_values mit abgelegt.
    "vapor_pressure": "_dampfdruck_temperatur",      # P2119
    "tensile_modulus": None,                        # P5480, Quelle nennt keine
}

# Qualifikatoren, die fuer jede Aussage der Groesse gleich sind:
# (PID, QuickStatements-Wert, Klartext). P1545 ist eine Zeichenkette und
# steht deshalb in Anfuehrungszeichen.
FESTE_QUALIFIKATOREN = {
    "ionization_energy": [("P1545", '"1"', "erste Ionisierungsenergie")],
}

# Molekulare Elemente: ihre Infobox-Enthalpien sind nicht eindeutig auf
# "pro Mol Atome" oder "pro Mol Molekuele" bezogen - und die de-Vorlage ist
# darin nicht einmal in sich einig. Am Bestand (2026-11-20): Stickstoff
# Schmelzwaerme de 0,36 / en "(N2) 0,72", Chlor 3,2 / 6,406, Brom 5,8 / 10,571,
# Iod 7,76 / 15,52 - de rechnet die Schmelzwaerme pro Atom, die
# Verdampfungswaerme aber pro Molekuel (Stickstoff 5,58 de = 5,57 en).
# Welcher Bezug zum Element-Item gehoert, entscheidet das Werkzeug nicht:
# diese Zeilen gehen in die manuelle Klaerung.
MOLBEZUG_SCHLUESSEL = ("molar_fusion_enthalpy", "molar_vaporization_enthalpy")
MOLEKULARE_ELEMENTE = {
    "Q556": "H2", "Q627": "N2", "Q629": "O2", "Q650": "F2", "Q674": "P4",
    "Q682": "S8", "Q688": "Cl2", "Q879": "Br2", "Q1103": "I2",
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
    # Kristallsystem, CAS-Nummer, Laengenausdehnungskoeffizient, die
    # magnetische Ordnung (P1552, Feld "Magnetismus") und seit 2026-11-20
    # Dampfdruck, Phasenpunkte sowie EG- und ECHA-Nummer.
    "wikipedia": frozenset(
        [PROPERTY_MAP[k]["pid"] for k, _ in WIKIPEDIA_DE_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k, _ in WIKIPEDIA_DE_CHEM_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k, _ in WIKIPEDIA_NUMERIC_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k, _, _ in CHEMBOX_FIELDS.values()]
        + [PROPERTY_MAP[k]["pid"] for k in
           ("crystal_system", "cas_number", "density", "melting_point",
            "boiling_point", "electrical_resistivity",
            "linear_thermal_expansion", "magnetism", "vapor_pressure",
            "phase_point", "ec_number", "echa_infocard")]),
}
