"""
Sammelbefehl: messen, vorschlagen, Struktur pruefen
==================================================

EIN Einstiegspunkt fuer alle Werkzeuge dieses Repos, mit kurzer Eingabe und
einem gemeinsamen Ausgabeordner. Je Werkstoffgruppe koennen bis zu drei
Schritte laufen:

  1. benchmark      - wie gut ist die Gruppe in Wikidata belegt?
  2. materialswiki  - Messwert-Vorschlaege fuer genau diese Gruppe
  3. struktur       - Klassenhierarchie pruefen (P279/P31, chemische
                      Metaklasse) -> gestaffelte Empfehlung
                      ("Material class structure/ClassCheck.py")

Ohne Schalter laufen 1 und 2; --struktur haengt 3 an, --nur-struktur macht
nur 3. Alle Schritte benutzen DIESELBE Grundgesamtheit; die Muster kommen
aus materialswiki.cli und werden importiert, nicht kopiert. Ohne das misst
der Benchmark leicht etwas anderes, als der Vorschlagslauf beackert.

Die Reihenfolge ist Absicht: der Benchmark laeuft in Minuten und zeigt, ob
sich der Vorschlagslauf (Stunden) ueberhaupt lohnt. Bricht ein Schritt ab,
startet der naechste gar nicht erst.

Nur die Strukturpruefung, fuer JEDE ClassCheck-Grundgesamtheit
--------------------------------------------------------------
  python -m lauf struktur <population> [--limit N] [--stempel S] [-- ...]

Als Gruppenschalter (--struktur / --nur-struktur) gibt es die Strukturpruefung
nur dort, wo Gruppe und ClassCheck-Grundgesamtheit zusammenfallen
(legierungen, benannte-legierungen, oxide, periodensystem, polymer,
magnetwerkstoffe). Der Unterbefehl
'struktur' nimmt daneben auch metallischer-werkstoff und material und braucht
weder Benchmark noch materialswiki-Gegenstueck. Ausgabe wie sonst nach
proposals/.

  python -m lauf struktur benannte-legierungen
  python -m lauf struktur oxide
  python -m lauf struktur material --limit 500
  python -m lauf struktur periodensystem -- --ohne-dichte

Gruppen
-------
  legierungen    568 Legierungen unter Q37756, ohne den falsch modellierten
                 Metalle-Zweig (Wikidata fuehrt "Metalle" als Unterklasse von
                 "Legierung"; ohne Filter waeren es 3718 Items samt Isotopen).
                 Magere Ausbeute: nur 10 tragen eine Summenformel
  minerale       6301 IMA-Mineralarten. Die ergiebigste Gruppe: 5694 mit
                 Summenformel, aber KEINE EINZIGE mit COD-ID, und 3916 ohne
                 Raumgruppe. Ein voller Lauf dauert Stunden - mit --limit
                 anfangen
  oxide          die 154 Oxide mit Summenformel. Der volle Subtree unter
                 Q50690 hat 27670 Items, ist aber fast nur labelloser
                 Massenimport
  carbide        die 27 Carbide unter Q241906 - technische Hartstoffe wie
                 SiC, WC, TiC und B4C. Die kleinste Gruppe, in Minuten durch;
                 10 tragen noch keine Summenformel
  metalle        98 metallische und halbmetallische Elemente
  periodensystem alle 118 chemischen Elemente
  polymer        Polymere/Kunststoffe unter Q11474 (~795 Items, 206 Klassen).
                 Nur 8 tragen eine Summenformel - der Ertrag liegt in Struktur
                 und Infobox-Kennzahlen, nicht in COD/MP
  magnetwerkstoffe  Magnetwerkstoffe unter Q949573, ohne Isotope (~10 Klassen).
                 Sehr klein; vor allem fuer die Strukturpruefung gedacht

Aufruf
------
  python -m lauf minerale                    # Chargen zu je 500 Items
  python -m lauf minerale --weiter --stempel 2026-08-16_1830 --nur-vorschlaege
  python -m lauf minerale --limit 50
  python -m lauf oxide
  python -m lauf legierungen --nur-benchmark
  python -m lauf legierungen --struktur            # 1+2+3 in einem Ordner
  python -m lauf struktur benannte-legierungen     # nur die Strukturpruefung
  python -m lauf struktur material --limit 500
  python -m lauf legierungen -- --no-wikipedia     # nach -- an materialswiki
  python -m lauf struktur legierungen -- --pruefungen metaklasse   # nach --
                                                     an ClassCheck.py
Alle erzeugten Dateien tragen denselben Zeitstempel und liegen in
--out-dir (Default: proposals/ - CLAUDE.md, "Arbeitsweise" Punkt 2).

Chargen
-------
Die Gruppenlaeufe arbeiten in Chargen zu je --batch-size Items (Default 500).
Nach JEDER Charge liegen CSV und QuickStatements fertig vor - man kann also
einspielen, waehrend der Rest noch laeuft, und ein Abbruch kostet hoechstens
die angefangene Charge. Bei 6301 Mineralen sind das 13 Chargen; der Stand
steht in <qs>.fortschritt.json.
"""

import argparse
import datetime as dt
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
STRUKTUR_SKRIPT = os.path.join(REPO, "Material class structure", "ClassCheck.py")
# Alle Vorschlagsdateien nach proposals/ (CLAUDE.md, "Arbeitsweise" Punkt 2).
PROPOSALS_DIR = os.path.join(REPO, "proposals")

# Je Gruppe:
#   population   Grundgesamtheit fuer benchmark.benchmark
#   cli          Schalter fuer 'python -m materialswiki'
#   struktur     Grundgesamtheit fuer die Strukturpruefung
#                ("Material class structure/ClassCheck.py"),
#                oder None, wenn es dort keine Entsprechung gibt
GRUPPEN = {
    "legierungen": {
        "population": "legierungen",
        "cli": ["--group", "legierungen"],
        "struktur": "legierungen",
        "beschreibung": "Legierungen (Q37756, ohne Metalle-Zweig)",
    },
    "benannte-legierungen": {
        "population": "legierungen",
        "cli": ["--group", "benannte-legierungen"],
        "struktur": "benannte-legierungen",
        "beschreibung": "benannte Legierungen aus [[en:List of named alloys]]",
    },
    "minerale": {
        "population": "minerale",
        "cli": ["--group", "minerale"],
        "struktur": None,
        "beschreibung": "Mineralarten (Q12089225, IMA-gefuehrt)",
    },
    "oxide": {
        "population": "oxide",
        "cli": ["--group", "oxide"],
        "struktur": "oxide",
        "beschreibung": "Oxide mit Summenformel (Q50690)",
    },
    "carbide": {
        "population": "carbide",
        "cli": ["--group", "carbide"],
        "struktur": None,
        "beschreibung": "Carbide (Q241906)",
    },
    "metalle": {
        "population": "metalle",
        "cli": ["--periodic-table", "--nur-metalle"],
        "struktur": None,
        "beschreibung": "metallische und halbmetallische Elemente",
    },
    "periodensystem": {
        "population": "periodensystem",
        "cli": ["--periodic-table", "--no-nur-metalle"],
        "struktur": "periodensystem",
        "beschreibung": "alle chemischen Elemente",
    },
    "polymer": {
        "population": "polymer",
        "cli": ["--group", "polymer"],
        "struktur": "polymer",
        "beschreibung": "Polymere / Kunststoffe (Q11474)",
    },
    "magnetwerkstoffe": {
        "population": "magnetwerkstoffe",
        "cli": ["--group", "magnetwerkstoffe"],
        "struktur": "magnetwerkstoffe",
        "beschreibung": "Magnetwerkstoffe (Q949573, ohne Isotope)",
    },
}

# Alle Grundgesamtheiten von ClassCheck.py - fuer den Unterbefehl 'struktur'.
# Mehr als die GRUPPEN oben kennen: material und metallischer-werkstoff haben
# kein Benchmark- oder materialswiki-Gegenstueck.
CLASSCHECK_POPULATIONEN = {
    "benannte-legierungen": "Prueferliste aus [[en:List of named alloys]]",
    "legierungen": "Legierungen unter Q37756 (ohne Elemente/Isotope)",
    "metallischer-werkstoff": "Klassen unter Q1924900 - braucht --limit N",
    "material": "Klassen unter Q214609 - braucht --limit N (~936.000 gesamt)",
    "oxide": "Oxide mit Summenformel (Q50690) - wie 'lauf oxide'",
    "periodensystem": "die 118 chemischen Elemente",
    "polymer": "Polymere / Kunststoffe unter Q11474 - wie 'lauf polymer'",
    "magnetwerkstoffe": "Magnetwerkstoffe unter Q949573 (ohne Isotope)",
}


def struktur_befehl(population: str, verzeichnis: str, stempel: str,
                    limit=None, extra=()) -> tuple:
    """(befehl, log-pfad) fuer einen ClassCheck-Lauf.

    Eine Stelle fuer beide Aufrufwege - den Gruppenschalter --struktur und
    den Unterbefehl 'struktur'. Die Dateinamen tragen die Population, nicht
    die Gruppe: fuer die drei Gruppen mit Strukturpruefung sind beide gleich.
    """
    basis = os.path.join(verzeichnis, "{}_" + f"{population}_{stempel}")
    befehl = [sys.executable, STRUKTUR_SKRIPT, "--population", population,
              "--out", basis.format("qs_class") + ".txt",
              "--csv", basis.format("qs_class_befunde") + ".csv",
              "--review-needed", os.path.join(PROPOSALS_DIR, "review-needed.md")]
    if limit is not None and population != "periodensystem":
        befehl += ["--limit", str(limit)]
    return befehl + list(extra), basis.format("qs_class") + ".log"


def _fertig(verzeichnis: str, muster: str) -> None:
    print(f"\n{'=' * 72}\nFertig. Dateien in {verzeichnis}:")
    for datei in sorted(os.listdir(verzeichnis)):
        if muster in datei:
            print(f"  {datei}")


def struktur_main(argv) -> int:
    """Unterbefehl 'struktur': nur ClassCheck.py, fuer jede Grundgesamtheit."""
    p = argparse.ArgumentParser(
        prog="lauf struktur",
        description="Nur die Strukturpruefung (ClassCheck.py) - P279/P31, "
                    "chemische Metaklasse -> gestaffelte Empfehlung nach "
                    "proposals/.")
    p.add_argument("population", choices=sorted(CLASSCHECK_POPULATIONEN),
                   help="; ".join(f"{k}: {v}"
                                  for k, v in CLASSCHECK_POPULATIONEN.items()))
    p.add_argument("--out-dir", default=PROPOSALS_DIR,
                   help="Zielordner (Default: proposals/ im Repo)")
    p.add_argument("--limit", type=int, default=None,
                   help="nur die ersten N Items; wirkt nicht im "
                        "Periodensystem-Modus")
    p.add_argument("--stempel", default=None,
                   help="Zeitstempel der Dateinamen vorgeben")
    p.add_argument("cli_args", nargs="*",
                   help="alles nach -- geht an ClassCheck.py "
                        "(z. B. -- --pruefungen metaklasse)")
    a = p.parse_args(argv)

    verzeichnis = os.path.abspath(a.out_dir)
    os.makedirs(verzeichnis, exist_ok=True)
    stempel = a.stempel or dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    befehl, log = struktur_befehl(a.population, verzeichnis, stempel,
                                  a.limit, a.cli_args)

    print(f"Grundgesamtheit: {CLASSCHECK_POPULATIONEN[a.population]}")
    print(f"Zeitstempel:     {stempel}")
    code = schritt("STRUKTURPRUEFUNG - Klassenhierarchie", befehl, log)
    if code == 0:
        _fertig(verzeichnis, f"_{a.population}_{stempel}")
    return code


def schritt(titel: str, befehl: list, protokoll: str) -> int:
    """Einen Teilschritt ausfuehren; Ausgabe geht gleichzeitig in eine Datei.

    tee statt Umleitung, damit ein stundenlanger Lauf mitverfolgt werden kann
    und das Protokoll trotzdem vollstaendig ist.
    """
    print(f"\n{'=' * 72}\n{titel}\n{'  ' + ' '.join(befehl)}\n{'=' * 72}",
          flush=True)
    with open(protokoll, "w", encoding="utf-8") as f:
        prozess = subprocess.Popen(befehl, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        for zeile in prozess.stdout:
            sys.stdout.write(zeile)
            sys.stdout.flush()
            f.write(zeile)
        return prozess.wait()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Unterbefehl 'struktur' vor dem Hauptparser abfangen - so bleibt
    # 'python -m lauf <gruppe>' unveraendert.
    if argv and argv[0] == "struktur":
        return struktur_main(argv[1:])

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gruppe", choices=sorted(GRUPPEN),
                        help="Werkstoffgruppe; ODER 'struktur <population>' als "
                             "Unterbefehl fuer die reine Strukturpruefung")
    parser.add_argument("--out-dir", default=PROPOSALS_DIR,
                        help="gemeinsamer Zielordner fuer alle Schritte - CSV, "
                             "Entwuerfe, Empfehlung, Protokolle "
                             "(Default: proposals/ im Repo)")
    parser.add_argument("--limit", type=int, default=None,
                        help="nur die ersten N Items; wirkt nicht im "
                             "Periodensystem-Modus")
    parser.add_argument("--batch-size", type=int, default=500, metavar="N",
                        help="Items je Charge; nach jeder Charge werden CSV "
                             "und QuickStatements geschrieben (Default: 500). "
                             "0 schaltet den Chargenbetrieb ab")
    parser.add_argument("--weiter", action="store_true",
                        help="die naechste Charge aus der Fortschrittsdatei "
                             "fortsetzen. Achtung: dann --out-dir und "
                             "--stempel wie beim ersten Lauf angeben")
    parser.add_argument("--stempel", default=None,
                        help="Zeitstempel der Dateinamen vorgeben, noetig zum "
                             "Fortsetzen eines frueheren Laufs")
    parser.add_argument("--nur-benchmark", action="store_true",
                        help="nach dem Benchmark anhalten")
    parser.add_argument("--nur-vorschlaege", action="store_true",
                        help="nur materialswiki (kein Benchmark, keine Struktur)")
    parser.add_argument("--struktur", action="store_true",
                        help="zusaetzlich die Klassenstruktur pruefen (P279/P31, "
                             "chemische Metaklasse) - schreibt "
                             "qs_class_<gruppe>_<stempel>.txt in denselben "
                             "Ordner. Nur legierungen, benannte-legierungen, "
                             "oxide, periodensystem, polymer, magnetwerkstoffe.")
    parser.add_argument("--nur-struktur", action="store_true",
                        help="NUR die Strukturpruefung - ohne Benchmark und "
                             "materialswiki")
    parser.add_argument("cli_args", nargs="*",
                        help="alles nach -- wird durchgereicht: an materialswiki, "
                             "bei --nur-struktur an die Strukturpruefung "
                             "(z. B. -- --no-wikipedia bzw. -- --vorsichtig)")
    args = parser.parse_args(argv)

    gruppe = GRUPPEN[args.gruppe]
    verzeichnis = os.path.abspath(args.out_dir)
    os.makedirs(verzeichnis, exist_ok=True)
    stempel = args.stempel or dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    pfad = lambda name: os.path.join(verzeichnis, f"{name}_{args.gruppe}_{stempel}")

    # Welche Schritte, in welcher Reihenfolge? Ein --nur-* schaltet auf genau
    # diesen einen; ohne sie laufen Benchmark und materialswiki, und --struktur
    # haengt die Strukturpruefung an.
    if args.nur_benchmark:
        schritte = ["benchmark"]
    elif args.nur_vorschlaege:
        schritte = ["vorschlaege"]
    elif args.nur_struktur:
        schritte = ["struktur"]
    else:
        schritte = ["benchmark", "vorschlaege"]
        if args.struktur:
            schritte.append("struktur")

    if "struktur" in schritte and not gruppe.get("struktur"):
        moeglich = ", ".join(g for g, i in GRUPPEN.items() if i.get("struktur"))
        parser.error(f"--struktur/--nur-struktur gibt es fuer '{args.gruppe}' "
                     f"nicht - nur fuer {moeglich}. Fuer die uebrigen "
                     f"ClassCheck-Grundgesamtheiten: python -m lauf struktur "
                     f"<population>")

    print(f"Werkstoffgruppe: {gruppe['beschreibung']}")
    print(f"Zeitstempel:     {stempel}")
    print(f"Schritte:        {', '.join(schritte)}")

    def lauf_schritt(nr: int, titel: str, befehl: list, log: str) -> int:
        return schritt(f"SCHRITT {nr}/{len(schritte)}  {titel}", befehl, log)

    for nr, name in enumerate(schritte, 1):
        if name == "benchmark":
            code = lauf_schritt(
                nr, "Benchmark - wie gut ist die Gruppe belegt?",
                [sys.executable, "-m", "benchmark.benchmark",
                 "--population", gruppe["population"],
                 "--csv", pfad("abdeckung") + ".csv"],
                pfad("benchmark") + ".log")
            if code != 0:
                print(f"\nBenchmark fehlgeschlagen (Code {code}) - Abbruch.",
                      file=sys.stderr)
                return code

        elif name == "vorschlaege":
            befehl = [sys.executable, "-m", "materialswiki", *gruppe["cli"],
                      "--out", pfad("vorschlaege") + ".csv",
                      "--qs-out", pfad("qs") + ".txt"]
            if args.limit is not None:
                befehl += ["--limit", str(args.limit)]
            # Chargenbetrieb nur fuer die Gruppenmodi - der Periodensystem-
            # Modus kennt weder --batch-size noch --limit.
            if gruppe["cli"][0] == "--group":
                if args.batch_size:
                    befehl += ["--batch-size", str(args.batch_size)]
                if args.weiter:
                    befehl += ["--weiter"]
            befehl += args.cli_args
            code = lauf_schritt(nr, "materialswiki - Vorschlaege erzeugen",
                                befehl, pfad("vorschlaege") + ".log")
            if code != 0:
                return code

        else:  # struktur
            befehl, log = struktur_befehl(
                gruppe["struktur"], verzeichnis, stempel, args.limit,
                args.cli_args if args.nur_struktur else ())
            code = lauf_schritt(nr, "Strukturpruefung - Klassenhierarchie",
                                befehl, log)
            if code != 0:
                return code

    _fertig(verzeichnis, f"_{args.gruppe}_{stempel}")
    if "vorschlaege" in schritte and args.batch_size \
            and gruppe["cli"][0] == "--group":
        print(f"\nNaechste Charge: python -m lauf {args.gruppe} --weiter "
              f"--stempel {stempel} --out-dir {args.out_dir} --nur-vorschlaege")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
