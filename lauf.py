"""
Kombinierter Lauf: erst messen, dann vorschlagen
================================================

Fuehrt fuer eine Werkstoffgruppe beide Schritte nacheinander aus:

  1. benchmark   - wie gut ist die Gruppe in Wikidata belegt?
  2. materialswiki - Vorschlaege fuer genau diese Gruppe

Beide Schritte benutzen DIESELBE Grundgesamtheit; die Muster kommen aus
materialswiki.cli und werden vom Benchmark importiert, nicht kopiert. Ohne
das misst der Benchmark leicht etwas anderes, als der Vorschlagslauf
beackert - und die Abdeckungszahlen passen dann nicht zur Ausbeute.

Die Reihenfolge ist Absicht: der Benchmark laeuft in Minuten und zeigt, ob
sich der Vorschlagslauf (Stunden) ueberhaupt lohnt. Bricht der Benchmark ab,
startet der zweite Schritt gar nicht erst.

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
  metalle        98 metallische und halbmetallische Elemente
  periodensystem alle 118 chemischen Elemente

Aufruf
------
  python -m lauf minerale                    # Chargen zu je 150 Items
  python -m lauf minerale --weiter --stempel 2026-08-16_1830 --nur-vorschlaege
  python -m lauf minerale --limit 50
  python -m lauf oxide
  python -m lauf legierungen
  python -m lauf legierungen --nur-benchmark
  python -m lauf legierungen -- --no-wikipedia     # alles nach -- geht an
                                                     materialswiki
Alle erzeugten Dateien tragen denselben Zeitstempel und liegen in
--out-dir (Default: das aktuelle Verzeichnis).

Chargen
-------
Die Gruppenlaeufe arbeiten in Chargen zu je --batch-size Items (Default 150).
Nach JEDER Charge liegen CSV und QuickStatements fertig vor - man kann also
einspielen, waehrend der Rest noch laeuft, und ein Abbruch kostet hoechstens
die angefangene Charge. Bei 6301 Mineralen sind das 43 Chargen; der Stand
steht in <quickstatements>.fortschritt.json.
"""

import argparse
import datetime as dt
import os
import subprocess
import sys

GRUPPEN = {
    "legierungen": {
        "population": "legierungen",
        "cli": ["--group", "legierungen"],
        "beschreibung": "Legierungen (Q37756, ohne Metalle-Zweig)",
    },
    "minerale": {
        "population": "minerale",
        "cli": ["--group", "minerale"],
        "beschreibung": "Mineralarten (Q12089225, IMA-gefuehrt)",
    },
    "oxide": {
        "population": "oxide",
        "cli": ["--group", "oxide"],
        "beschreibung": "Oxide mit Summenformel (Q50690)",
    },
    "metalle": {
        "population": "metalle",
        "cli": ["--periodic-table", "--nur-metalle"],
        "beschreibung": "metallische und halbmetallische Elemente",
    },
    "periodensystem": {
        "population": "periodensystem",
        "cli": ["--periodic-table", "--no-nur-metalle"],
        "beschreibung": "alle chemischen Elemente",
    },
}


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
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gruppe", choices=sorted(GRUPPEN))
    parser.add_argument("--out-dir", default=".",
                        help="Zielverzeichnis fuer CSV, Entwurf und Protokolle")
    parser.add_argument("--limit", type=int, default=None,
                        help="nur die ersten N Items (bei den Gruppen "
                             "legierungen, minerale, oxide)")
    parser.add_argument("--batch-size", type=int, default=150, metavar="N",
                        help="Items je Charge; nach jeder Charge werden CSV "
                             "und QuickStatements geschrieben (Default: 150). "
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
                        help="den Benchmark ueberspringen")
    parser.add_argument("cli_args", nargs="*",
                        help="alles nach -- wird an materialswiki "
                             "durchgereicht, z. B. -- --no-wikipedia")
    args = parser.parse_args(argv)

    gruppe = GRUPPEN[args.gruppe]
    os.makedirs(args.out_dir, exist_ok=True)
    stempel = args.stempel or dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    pfad = lambda name: os.path.join(args.out_dir, f"{name}_{args.gruppe}_{stempel}")

    print(f"Werkstoffgruppe: {gruppe['beschreibung']}")
    print(f"Zeitstempel:     {stempel}")

    if not args.nur_vorschlaege:
        code = schritt(
            "SCHRITT 1/2  Benchmark - wie gut ist die Gruppe belegt?",
            [sys.executable, "-m", "benchmark.benchmark",
             "--population", gruppe["population"],
             "--csv", pfad("abdeckung") + ".csv"],
            pfad("benchmark") + ".log",
        )
        if code != 0:
            print(f"\nBenchmark fehlgeschlagen (Code {code}) - der "
                  f"Vorschlagslauf wird nicht gestartet.", file=sys.stderr)
            return code
        if args.nur_benchmark:
            return 0

    befehl = [sys.executable, "-m", "materialswiki", *gruppe["cli"],
              "--out", pfad("vorschlaege") + ".csv",
              "--qs-out", pfad("quickstatements") + ".txt"]
    if args.limit is not None:
        befehl += ["--limit", str(args.limit)]
    # Chargenbetrieb nur fuer die Gruppenmodi - der Periodensystem-Modus
    # kennt weder --batch-size noch --limit.
    if gruppe["cli"][0] == "--group":
        if args.batch_size:
            befehl += ["--batch-size", str(args.batch_size)]
        if args.weiter:
            befehl += ["--weiter"]
    befehl += args.cli_args

    code = schritt("SCHRITT 2/2  materialswiki - Vorschlaege erzeugen",
                   befehl, pfad("vorschlaege") + ".log")
    if code != 0:
        return code

    print(f"\n{'=' * 72}\nFertig. Dateien mit Zeitstempel {stempel} in "
          f"{os.path.abspath(args.out_dir)}:")
    verzeichnis = os.path.abspath(args.out_dir)
    muster = f"_{args.gruppe}_{stempel}"
    for datei in sorted(os.listdir(verzeichnis)):
        if muster in datei:
            print(f"  {datei}")
    if args.batch_size and gruppe["cli"][0] == "--group":
        print(f"\nNaechste Charge: python -m lauf {args.gruppe} --weiter "
              f"--stempel {stempel} --out-dir {args.out_dir} --nur-vorschlaege")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
