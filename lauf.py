"""
Sammelbefehl: ein Dialog fuer alle vier Werkzeuge dieses Repos
=============================================================

`python -m lauf` startet KEINEN Lauf mit Schaltern mehr, sondern einen
mehrschichtigen Dialog. Die Fragen kommen in dieser Reihenfolge:

  1. Grundgesamtheit    - welche Population wird bearbeitet?
     -> danach die Ausgabe, wie viele Items das betrifft
  2. Batchgroesse        - nur wenn mehr als 200 Items betroffen sind
     (mind. 100). Der Vorschlagslauf arbeitet dann in Chargen und laesst
     sich fortsetzen
  3. Umfang              - Mehrfachauswahl aus den fuer diese Population
     verfuegbaren Schritten:
         benchmark      wie gut ist die Gruppe in Wikidata belegt?
         vorschlaege    Messwert-Vorschlaege je Item (materialswiki)
         struktur       Klassenhierarchie pruefen (ClassCheck.py)
         anwendungen    P366/P186/P2079 aus den Rueckverweisen (Anwendung.py)

Alle gewaehlten Schritte laufen nacheinander, tragen denselben Zeitstempel
und landen zusammen in proposals/ - je Lauf EIN Protokoll
(lauf_<population>_<stempel>.log) fuer alle Schritte. Die Vorschlags-Stufe
schreibt keine Markdown-Tabelle mehr; ihr QuickStatements-Entwurf
(qs_<population>_<stempel>.txt) traegt ohnehin jede Zeile. Bricht ein Schritt
ab, startet der naechste nicht mehr. Gibt es einen unterbrochenen
Chargenlauf, bietet der Dialog vor der ersten Frage an, ihn fortzusetzen.

Welche Schritte eine Population kennt, steht in POPULATIONEN unten:
'benchmark', 'vorschlaege' und 'struktur' gibt es fuer jede, 'anwendungen'
nur fuer 'legierungen'.
"""

import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
STRUKTUR_SKRIPT = os.path.join(REPO, "Material class structure", "ClassCheck.py")
ANWENDUNG_SKRIPT = os.path.join(REPO, "Anwendung", "Anwendung.py")
# Alle Vorschlagsdateien nach proposals/ (CLAUDE.md, "Arbeitsweise" Punkt 2).
PROPOSALS_DIR = os.path.join(REPO, "proposals")

# ---------------------------------------------------------------------------
# Die Grundgesamtheiten und was sich mit ihnen anstellen laesst
# ---------------------------------------------------------------------------
#
# Je Population:
#   beschreibung  einzeilig fuer die Auswahlliste
#   zaehl         wie die Itemzahl ermittelt wird:
#                   "gruppe"  -> materialswiki.gruppen.gruppen_qids(name)
#                   sonst der Schluessel in _zaehl_sparql_muster() unten
#   schritte      {name: konfig} - nur die hier genannten Schritte werden
#                 fuer diese Population angeboten:
#                   benchmark    {"population": <benchmark --population>}
#                   vorschlaege  {"cli": [<schalter fuer python -m materialswiki>]}
#                   struktur     {"population": <ClassCheck --population>}
#                   anwendungen  {"population": <Anwendung --population>}
POPULATIONEN = {
    "legierungen": {
        "beschreibung": "Legierungen (Q37756, ohne Elemente/Isotope) - kaum eine traegt eine Summenformel",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "legierungen"},
            "vorschlaege": {"cli": ["--group", "legierungen"]},
            "struktur": {"population": "legierungen"},
            "anwendungen": {"population": "legierungen"},
        },
    },
    "minerale": {
        "beschreibung": "Mineralarten (Q12089225, IMA-gefuehrt) - ergiebigste Gruppe, fast alle mit Summenformel",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "minerale"},
            "vorschlaege": {"cli": ["--group", "minerale"]},
            "struktur": {"population": "minerale"},
        },
    },
    "oxide": {
        "beschreibung": "Oxide mit Summenformel (Q50690)",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "oxide"},
            "vorschlaege": {"cli": ["--group", "oxide"]},
            "struktur": {"population": "oxide"},
        },
    },
    "carbide": {
        "beschreibung": "Carbide (Q241906) - technische Hartstoffe wie SiC, WC, TiC, B4C; ~27 Items",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "carbide"},
            "vorschlaege": {"cli": ["--group", "carbide"]},
            "struktur": {"population": "carbide"},
        },
    },
    "periodensystem": {
        "beschreibung": "alle 118 chemischen Elemente",
        "zaehl": "periodensystem",
        "schritte": {
            "benchmark": {"population": "periodensystem"},
            "vorschlaege": {"cli": ["--periodic-table", "--no-nur-metalle"]},
            "struktur": {"population": "periodensystem"},
        },
    },
    "polymer": {
        "beschreibung": "Polymere / Kunststoffe (Q11474) - ~795 Items, 206 Klassen",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "polymer"},
            "vorschlaege": {"cli": ["--group", "polymer"]},
            "struktur": {"population": "polymer"},
        },
    },
    "magnetwerkstoffe": {
        "beschreibung": "Magnetwerkstoffe (Q949573, ohne Isotope) - ~17 Klassen",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "magnetwerkstoffe"},
            "vorschlaege": {"cli": ["--group", "magnetwerkstoffe"]},
            "struktur": {"population": "magnetwerkstoffe"},
        },
    },
    "keramik": {
        "beschreibung": "Keramik-Klassen (Q45621, ohne Objekt-Instanzen) - ~1021 Klassen",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "keramik"},
            "vorschlaege": {"cli": ["--group", "keramik"]},
            "struktur": {"population": "keramik"},
        },
    },
    "glas": {
        "beschreibung": "Glas / Glaswerkstoffe (Q11469) - ~1160 Items, ~165 Klassen",
        "zaehl": "gruppe",
        "schritte": {
            "benchmark": {"population": "glas"},
            "vorschlaege": {"cli": ["--group", "glas"]},
            "struktur": {"population": "glas"},
        },
    },
}

# Reihenfolge, in der die Schritte laufen: erst der schnelle Benchmark (er
# zeigt, ob sich der stundenlange Vorschlagslauf lohnt), dann die Vorschlaege,
# dann die beiden Analysen.
SCHRITT_REIHENFOLGE = ["benchmark", "vorschlaege", "struktur", "anwendungen"]

SCHRITT_TEXT = {
    "benchmark": "Benchmark - wie gut ist die Gruppe in Wikidata belegt? (Minuten)",
    "vorschlaege": "Vorschlaege - Messwert-Vorschlaege je Item aus COD/MP/NIST/Wikipedia (Stunden)",
    "struktur": "Klassenstruktur - P279/P31, chemische Metaklasse (ClassCheck.py)",
    "anwendungen": "Anwendungen - P366/P186/P2079 aus den Rueckverweisen (Anwendung.py)",
}


# ---------------------------------------------------------------------------
# Wie viele Items betrifft eine Population?
# ---------------------------------------------------------------------------

def _zaehl_sparql_muster() -> dict:
    """Zaehl-Muster fuer die Populationen, die keine materialswiki-Gruppe sind.

    Lazy, weil der Import von benchmark.benchmark den ganzen Apparat
    mitzieht - und der Dialog laeuft auch ohne den Elementlauf.
    """
    from benchmark.benchmark import DEFAULT_MAX_Z, PERIODENSYSTEM_PATTERN

    return {"periodensystem": PERIODENSYSTEM_PATTERN.format(max_z=DEFAULT_MAX_Z)}


def _sparql_count(muster: str) -> int:
    from materialswiki import netz
    from materialswiki.konfiguration import WIKIDATA_SPARQL

    resp = netz.get_with_retry(WIKIDATA_SPARQL, {
        "query": f"SELECT (COUNT(DISTINCT ?i) AS ?n) WHERE {{ {muster} }}",
        "format": "json",
    })
    return int(resp.json()["results"]["bindings"][0]["n"]["value"])


def anzahl_items(name: str) -> int:
    """Wie viele Wikidata-Items die Population `name` umfasst."""
    if POPULATIONEN[name]["zaehl"] == "gruppe":
        from materialswiki.gruppen import gruppen_qids
        return len(gruppen_qids(name))
    return _sparql_count(_zaehl_sparql_muster()[POPULATIONEN[name]["zaehl"]])


# ---------------------------------------------------------------------------
# Die Fragen
# ---------------------------------------------------------------------------

def _frage(text: str) -> str:
    """input() mit sauberem Abbruch bei Ctrl-D / Ctrl-C."""
    try:
        return input(text).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(1)


def frage_population() -> str:
    namen = list(POPULATIONEN)
    print("\nWelche Grundgesamtheit?\n")
    for i, nm in enumerate(namen, 1):
        print(f"  {i:2d}) {nm}\n      {POPULATIONEN[nm]['beschreibung']}")
    while True:
        wahl = _frage("\nNummer oder Name (q = Abbruch): ")
        if wahl.lower() in ("q", "quit", "exit", ""):
            raise SystemExit(0)
        if wahl.isdigit() and 1 <= int(wahl) <= len(namen):
            return namen[int(wahl) - 1]
        if wahl in POPULATIONEN:
            return wahl
        print("  Bitte eine der Nummern oder einen der Namen oben.")


def frage_groesse(anzahl, vorgabe: int = 500) -> int:
    """Batchgroesse fuer den Vorschlagslauf, mindestens 100."""
    if anzahl is not None:
        print(f"\n{anzahl} Eintraege - der Vorschlagslauf arbeitet dann in "
              f"Chargen (und laesst sich fortsetzen).")
    while True:
        roh = _frage(f"Batchgroesse (mind. 100, Enter fuer {vorgabe}, "
                     f"q = Abbruch): ")
        if roh.lower() in ("q", "quit", "exit"):
            raise SystemExit(0)
        if not roh:
            return vorgabe
        if roh.isdigit() and int(roh) >= 100:
            return int(roh)
        print("  Bitte eine ganze Zahl >= 100.")


def frage_umfang(name: str) -> list:
    verfuegbar = [s for s in SCHRITT_REIHENFOLGE
                  if s in POPULATIONEN[name]["schritte"]]
    print("\nUmfang? Mehrfachauswahl - Nummern mit Komma oder Leerzeichen "
          "trennen, 'a' = alle.\n")
    for i, s in enumerate(verfuegbar, 1):
        print(f"  {i}) {SCHRITT_TEXT[s]}")
    while True:
        roh = _frage("\nAuswahl (q = Abbruch): ").lower()
        if roh in ("q", "quit", "exit"):
            raise SystemExit(0)
        if roh in ("a", "alle", "all"):
            return verfuegbar
        teile = [t for t in re.split(r"[,\s]+", roh) if t]
        if teile and all(t.isdigit() and 1 <= int(t) <= len(verfuegbar)
                         for t in teile):
            gewaehlt = {verfuegbar[int(t) - 1] for t in teile}
            return [s for s in verfuegbar if s in gewaehlt]
        print("  Bitte mindestens eine der Nummern oben.")


# ---------------------------------------------------------------------------
# Einen unterbrochenen Chargenlauf fortsetzen
# ---------------------------------------------------------------------------

def unterbrochene_laeufe() -> list:
    """Alle Fortschrittsdateien in proposals/, deren Lauf nicht fertig ist.

    Der Chargenbetrieb von materialswiki schreibt nach jeder Charge
    qs_<gruppe>_<stempel>.fortschritt.json. Steht dort erledigt < gesamt,
    laesst sich der Lauf mit --weiter genau dort fortsetzen.
    """
    offen = []
    muster = os.path.join(PROPOSALS_DIR, "qs_*_*.fortschritt.json")
    for pfad in sorted(glob.glob(muster)):
        try:
            with open(pfad, encoding="utf-8") as f:
                stand = json.load(f)
        except (OSError, ValueError):
            continue
        gruppe = stand.get("gruppe")
        if gruppe not in POPULATIONEN:
            continue
        if stand.get("erledigt", 0) >= stand.get("gesamt", 0):
            continue
        basis = os.path.basename(pfad)[:-len(".fortschritt.json")]
        stempel = basis[len(f"qs_{gruppe}_"):]
        offen.append({"gruppe": gruppe, "stempel": stempel, "stand": stand})
    return offen


def charge_fortsetzen(eintrag: dict) -> int:
    gruppe, stempel, stand = (eintrag["gruppe"], eintrag["stempel"],
                              eintrag["stand"])
    batch = stand.get("batch_size") or 500
    pfad = _pfad_fabrik(gruppe, stempel)
    log_pfad = pfad("lauf", ".log")
    befehl = [PY, "-m", "materialswiki", "--group", gruppe, "--weiter",
              "--batch-size", str(batch), "--no-tabelle",
              "--qs-out", pfad("qs", ".txt")]
    if _mp_schluessel_fehlt():
        print("Hinweis: kein MP_API_KEY - Fortsetzung laeuft mit --no-mp "
              "(Materials Project uebersprungen).", file=sys.stderr)
        befehl.append("--no-mp")
    print(f"\nSetze '{gruppe}' fort bei Item {stand.get('erledigt', 0) + 1} "
          f"von {stand.get('gesamt', '?')} (Charge {stand.get('letzte_charge', '?')} "
          f"war die letzte fertige).")
    # An die bestehende Log-Datei des Laufs anhaengen - die Fortsetzung
    # gehoert zu demselben Zeitstempel.
    with open(log_pfad, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 72}\nFORTGESETZT "
                f"{dt.datetime.now():%Y-%m-%d %H:%M}\n{'=' * 72}\n")
    code = schritt("VORSCHLAEGE - fortgesetzt", befehl, log_pfad)
    if code == 0:
        _fertig(PROPOSALS_DIR, f"_{gruppe}_{stempel}")
    return code


# ---------------------------------------------------------------------------
# Die Schritte ausfuehren
# ---------------------------------------------------------------------------

def _pfad_fabrik(name: str, stempel: str):
    return lambda stamm, endung: os.path.join(
        PROPOSALS_DIR, f"{stamm}_{name}_{stempel}{endung}")


def _mp_schluessel_fehlt() -> bool:
    """True, wenn kein MP_API_KEY in der Umgebung (bzw. .env.api-keys) steht.

    Die Materials-Project-Stufe des Vorschlagslaufs bricht ohne Schluessel
    mit HTTP 401 ab und riss bislang den ganzen Sammellauf mit. Fehlt der
    Schluessel, haengt lauf.py stattdessen --no-mp an: der Schritt laeuft
    dann ohne MP weiter, COD/NIST/Wikipedia tragen ohnehin den groesseren
    Teil bei. konfig.py spiegelt .env.api-keys beim Import hinein.
    """
    try:
        import konfig
    except ImportError:
        return False
    return not konfig.wert("MP_API_KEY")


def struktur_befehl(population: str, verzeichnis: str, stempel: str,
                    limit=None, extra=()) -> list:
    """Der ClassCheck-Aufruf fuer eine Grundgesamtheit.

    Die Dateinamen tragen die Population; --limit wirkt nicht im
    Periodensystem-Modus (dort ist die Grundgesamtheit abgeschlossen).
    """
    basis = os.path.join(verzeichnis, "{}_" + f"{population}_{stempel}")
    befehl = [PY, STRUKTUR_SKRIPT, "--population", population,
              "--out", basis.format("qs_class") + ".txt",
              "--md", basis.format("qs_class_befunde") + ".md",
              "--review-needed", os.path.join(PROPOSALS_DIR, "review-needed.md")]
    if limit is not None and population != "periodensystem":
        befehl += ["--limit", str(limit)]
    return befehl + list(extra)


def schritt_befehl(stufe: str, name: str, stempel: str, groesse) -> list:
    """Der Aufruf fuer einen der vier Schritte.

    Die Vorschlags-Stufe schreibt KEINE Markdown-Tabelle (--no-tabelle) - der
    QuickStatements-Entwurf traegt ohnehin jede Zeile.
    """
    info = POPULATIONEN[name]
    konfig = info["schritte"][stufe]
    pfad = _pfad_fabrik(name, stempel)

    if stufe == "benchmark":
        return [PY, "-m", "benchmark.benchmark",
                "--population", konfig["population"],
                "--md", pfad("abdeckung", ".md")]

    if stufe == "vorschlaege":
        befehl = [PY, "-m", "materialswiki", *konfig["cli"], "--no-tabelle",
                  "--qs-out", pfad("qs", ".txt")]
        # Chargenbetrieb gibt es nur im Gruppenmodus - der Periodensystem-
        # Modus kennt weder --batch-size noch mehr als 118 Items.
        if konfig["cli"][0] == "--group" and groesse:
            befehl += ["--batch-size", str(groesse)]
        # Ohne MP_API_KEY die MP-Stufe abschalten statt den Lauf abbrechen.
        if _mp_schluessel_fehlt():
            print("Hinweis: kein MP_API_KEY - der Vorschlagslauf laeuft mit "
                  "--no-mp (Materials Project uebersprungen).", file=sys.stderr)
            befehl.append("--no-mp")
        return befehl

    if stufe == "struktur":
        # ClassCheck laeuft ueber die volle Grundgesamtheit - die Batchgroesse
        # betrifft nur den Vorschlagslauf.
        return struktur_befehl(konfig["population"], PROPOSALS_DIR, stempel)

    # anwendungen
    return [PY, ANWENDUNG_SKRIPT, "--population", konfig["population"],
            "--md", pfad("anwendungen_befunde", ".md"),
            "--qs-out", pfad("qs_anwendungen", ".txt")]


def schritt(titel: str, befehl: list, protokoll: str) -> int:
    """Einen Teilschritt ausfuehren; Ausgabe geht gleichzeitig in EIN Protokoll.

    tee statt Umleitung, damit ein stundenlanger Lauf mitverfolgt werden kann
    und das Protokoll trotzdem vollstaendig ist. Angehaengt, nicht ueberschrieben:
    alle Schritte eines Laufs teilen sich dieselbe Log-Datei (siehe
    fuehre_aus), die vorher einmal frisch angelegt wird.
    """
    kopf = f"\n{'=' * 72}\n{titel}\n{'  ' + ' '.join(befehl)}\n{'=' * 72}"
    print(kopf, flush=True)
    with open(protokoll, "a", encoding="utf-8") as f:
        f.write(kopf + "\n")
        f.flush()
        prozess = subprocess.Popen(befehl, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        for zeile in prozess.stdout:
            sys.stdout.write(zeile)
            sys.stdout.flush()
            f.write(zeile)
        return prozess.wait()


def _fertig(verzeichnis: str, muster: str) -> None:
    print(f"\n{'=' * 72}\nFertig. Dateien in {verzeichnis}:")
    for datei in sorted(os.listdir(verzeichnis)):
        if muster in datei:
            print(f"  {datei}")


def _log_anlegen(log_pfad: str, kopf: list) -> None:
    """Die eine Log-Datei des Laufs frisch anlegen (bzw. leeren)."""
    with open(log_pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(kopf) + "\n")


def fuehre_aus(name: str, schritte: list, groesse) -> int:
    os.makedirs(PROPOSALS_DIR, exist_ok=True)
    stempel = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    log_pfad = _pfad_fabrik(name, stempel)("lauf", ".log")

    kopf = [
        "=" * 72,
        f"Grundgesamtheit: {name} - {POPULATIONEN[name]['beschreibung']}",
        f"Zeitstempel:     {stempel}",
        f"Schritte:        {', '.join(schritte)}",
    ]
    if groesse:
        kopf.append(f"Batchgroesse:    {groesse}")
    kopf.append("=" * 72)
    for zeile in kopf:
        print(zeile)
    _log_anlegen(log_pfad, kopf)

    for nr, stufe in enumerate(schritte, 1):
        befehl = schritt_befehl(stufe, name, stempel, groesse)
        code = schritt(f"SCHRITT {nr}/{len(schritte)}  {stufe.upper()}",
                       befehl, log_pfad)
        if code != 0:
            print(f"\n{stufe} fehlgeschlagen (Code {code}) - Abbruch, die "
                  f"folgenden Schritte laufen nicht mehr.", file=sys.stderr)
            return code

    _fertig(PROPOSALS_DIR, f"_{name}_{stempel}")
    if "vorschlaege" in schritte and groesse \
            and POPULATIONEN[name]["schritte"]["vorschlaege"]["cli"][0] == "--group":
        print("\nWurde der Vorschlagslauf unterbrochen: 'python -m lauf' erneut "
              "starten - der Dialog bietet die Fortsetzung an.")
    return 0


# ---------------------------------------------------------------------------
# Der Dialog
# ---------------------------------------------------------------------------

def _pruefe_umgebung() -> None:
    """Bricht mit klarer Ansage ab, wenn die eine Abhaengigkeit fehlt.

    lauf.py selbst braucht nur die Standardbibliothek, ruft aber JEDEN Schritt
    als Unterprozess mit demselben Interpreter (sys.executable) auf - und
    dessen erste Zeile ist `import requests`. Fehlt das Modul, liefe sonst der
    ganze Dialog durch und Schritt 1 stuerzte mit einem Traceback ab.
    """
    try:
        import requests  # noqa: F401
    except ImportError:
        raise SystemExit(
            f"Das Modul 'requests' fehlt in diesem Python ({sys.executable}) - "
            f"ohne es kann kein Schritt laufen.\n"
            f"  Abhilfe (aus dem Repo-Wurzelverzeichnis):\n"
            f"    {sys.executable} -m pip install -r requirements.txt\n"
            f"  oder den venv-Interpreter nehmen, z. B.\n"
            f"    .venv/bin/python -m lauf")


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        print("`python -m lauf` nimmt keine Argumente mehr - es fuehrt durch "
              "einen Dialog.\nDie einzelnen Werkzeuge behalten ihre Schalter: "
              "python -m materialswiki ..., python -m benchmark.benchmark ..., "
              "python \"Material class structure/ClassCheck.py\" ..., "
              "python \"Anwendung/Anwendung.py\" ...", file=sys.stderr)
        return 2

    _pruefe_umgebung()

    print("=" * 72)
    print("lauf - Benchmark, Vorschlaege, Klassenstruktur, Anwendungen")
    print("=" * 72)

    offen = unterbrochene_laeufe()
    if offen:
        print("\nUnterbrochene Vorschlagslaeufe gefunden:\n")
        for i, e in enumerate(offen, 1):
            st = e["stand"]
            print(f"  {i}) {e['gruppe']:22} {st.get('erledigt', 0)}/"
                  f"{st.get('gesamt', '?')} erledigt  (Stand "
                  f"{st.get('zeitpunkt', '?')})")
        wahl = _frage("\nEinen davon fortsetzen? Nummer, oder Enter fuer einen "
                      "neuen Lauf: ")
        if wahl.isdigit() and 1 <= int(wahl) <= len(offen):
            return charge_fortsetzen(offen[int(wahl) - 1])

    name = frage_population()

    try:
        anzahl = anzahl_items(name)
    except Exception as fehler:  # Netz-, SPARQL-, Importfehler
        print(f"\nItemzahl nicht ermittelbar ({fehler}) - es geht ohne "
              f"Zaehl-Angabe weiter.", file=sys.stderr)
        anzahl = None
    else:
        print(f"\n-> Grundgesamtheit '{name}': {anzahl} Eintraege betroffen.")

    groesse = None
    if anzahl is not None and anzahl > 200:
        groesse = frage_groesse(anzahl)

    schritte = frage_umfang(name)
    if not schritte:
        print("Kein Schritt gewaehlt - Abbruch.")
        return 1

    return fuehre_aus(name, schritte, groesse)


if __name__ == "__main__":
    raise SystemExit(main())
