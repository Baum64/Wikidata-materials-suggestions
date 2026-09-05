"""Zugangsdaten aus der Umgebung lesen - und NUR aus der Umgebung.

Alle Skripte dieses Repos holen ihren API-Schluessel und ihre Kontaktadresse
ueber konfig.wert(). Diese Funktion liest ausschliesslich os.environ; es gibt
keine zweite Quelle, keine Suche in Arbeitsverzeichnissen, keinen
Vorgabewert-Fallback ausser dem im Aufruf mitgegebenen.

Damit die Werte nicht bei jedem Aufruf von Hand exportiert werden muessen,
spiegelt dieses Modul beim Import einmalig die Datei .env.api-keys aus dem
Repo-Wurzelverzeichnis in die Umgebung - aber nur Namen, die dort noch nicht
gesetzt sind. Eine echte Umgebungsvariable gewinnt also immer, und ein Lauf
laesst sich voruebergehend umstellen (Zweitschluessel), ohne die Datei zu
aendern.

Bewusst KEIN python-dotenv: das waere eine weitere Abhaengigkeit fuer 20
Zeilen Parser, und dieses Repo kommt sonst mit `requests` aus.
"""
import os

# .env.api-keys liegt neben dieser Datei, also im Repo-Wurzelverzeichnis.
# NICHT im aktuellen Arbeitsverzeichnis suchen - die Skripte werden von
# ueberall gestartet, und ein zufaellig danebenliegendes .env.api-keys waere
# eine boese Ueberraschung.
API_KEYS_DATEI = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".env.api-keys")

_GESPIEGELT = False


def _in_umgebung_spiegeln() -> None:
    """.env.api-keys einmalig nach os.environ - vorhandene Namen bleiben.

    Format: KEY=WERT je Zeile, '#' leitet einen Kommentar ein. Umschliessende
    Anfuehrungszeichen werden abgestreift - sonst landete das Zitat im
    Schluessel und die API antwortete mit einem raetselhaften 403.
    """
    global _GESPIEGELT
    if _GESPIEGELT:
        return
    _GESPIEGELT = True
    try:
        with open(API_KEYS_DATEI, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                name, _, wert = zeile.partition("=")
                name, wert = name.strip(), wert.strip()
                if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "\"'":
                    wert = wert[1:-1]
                if wert and name not in os.environ:
                    os.environ[name] = wert
    except FileNotFoundError:
        pass  # ohne die Datei laeuft alles ueber echte Umgebungsvariablen


_in_umgebung_spiegeln()


def wert(name: str, vorgabe: str = "") -> str:
    """Zugangsdatum aus der Umgebung, sonst die im Aufruf mitgegebene Vorgabe."""
    return os.environ.get(name) or vorgabe


def fehlt_hinweis(name: str) -> str:
    """Einheitlicher Hinweistext, wenn ein Zugangsdatum fehlt."""
    return (
        f"{name} ist nicht in der Umgebung gesetzt. Entweder exportieren "
        f"(z. B. {name}=... python -m ...) oder in {API_KEYS_DATEI} eintragen "
        f"- die Datei ist gitignoriert und wird beim Start in die Umgebung "
        f"gespiegelt."
    )
