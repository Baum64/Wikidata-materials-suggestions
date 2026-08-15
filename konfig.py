"""Zugangsdaten aus .env lesen - ohne zusaetzliche Abhaengigkeit.

Alle Skripte dieses Repos holen ihren API-Schluessel und ihre Kontaktadresse
hierueber, damit beides an genau EINER Stelle steht und diese eine Stelle
gitignoriert ist.

Rangfolge, bewusst so herum:

    1. echte Umgebungsvariable   (MP_API_KEY=... python -m materialswiki ...)
    2. Eintrag in .env
    3. Vorgabewert im Aufruf

Die Umgebung gewinnt, damit sich ein Lauf voruebergehend umstellen laesst -
etwa mit einem Zweitschluessel - ohne die Datei zu aendern.

Bewusst KEIN python-dotenv: das waere eine weitere Abhaengigkeit fuer 20
Zeilen Parser, und dieses Repo kommt sonst mit `requests` aus.
"""
import os

# .env liegt neben dieser Datei, also im Repo-Wurzelverzeichnis. Nicht im
# aktuellen Arbeitsverzeichnis suchen - die Skripte werden von ueberall
# gestartet, und ein zufaellig danebenliegendes .env waere eine boese
# Ueberraschung.
ENV_DATEI = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

_ZWISCHENSPEICHER = None


def _laden() -> dict:
    """Parst .env: KEY=WERT je Zeile, '#' leitet einen Kommentar ein."""
    global _ZWISCHENSPEICHER
    if _ZWISCHENSPEICHER is not None:
        return _ZWISCHENSPEICHER

    werte = {}
    try:
        with open(ENV_DATEI, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile or zeile.startswith("#") or "=" not in zeile:
                    continue
                name, _, wert = zeile.partition("=")
                wert = wert.strip()
                # Anfuehrungszeichen abstreifen, falls jemand welche setzt -
                # sonst landete das Zitat mit im Schluessel und die API
                # antwortete mit einem raetselhaften 403.
                if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "\"'":
                    wert = wert[1:-1]
                werte[name.strip()] = wert
    except FileNotFoundError:
        pass  # ohne .env laeuft alles ueber die Umgebung
    _ZWISCHENSPEICHER = werte
    return werte


def wert(name: str, vorgabe: str = "") -> str:
    """Zugangsdatum lesen: Umgebung, dann .env, dann Vorgabe."""
    aus_umgebung = os.environ.get(name)
    if aus_umgebung:
        return aus_umgebung
    return _laden().get(name, vorgabe)


def fehlt_hinweis(name: str) -> str:
    """Einheitlicher Hinweistext, wenn ein Zugangsdatum fehlt."""
    return (
        f"{name} ist weder als Umgebungsvariable noch in {ENV_DATEI} gesetzt. "
        f"Vorlage: .env.beispiel nach .env kopieren und ausfuellen."
    )
