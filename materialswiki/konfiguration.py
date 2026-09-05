"""Kennungen, Endpunkte und Drosselung - alles, was aus der Umgebung kommt.

Eigene Datei, weil es JEDES andere Modul braucht und nichts davon Logik ist.
"""

import os
import sys

# konfig.py liegt im Repo-Wurzelverzeichnis, eine Ebene ueber diesem Paket.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import konfig  # noqa: E402

# Kontaktadresse und Schluessel kommen aus der Umgebung; konfig.py spiegelt
# dafuer beim Import .env.api-keys im Repo-Wurzelverzeichnis hinein. Diese
# Datei ist gitignoriert - so steht kein Zugangsdatum im Quelltext und damit
# auch keines auf GitHub.
CONTACT_EMAIL = konfig.wert("CONTACT_EMAIL", "DEINE-ADRESSE@example.org")
CONTACT = f"mailto:{CONTACT_EMAIL}"

# Zwei Kennungen, weil die beiden Gegenstellen Gegensaetzliches verlangen:
#
#   Wikimedia  verlangt laut User-Agent-Richtlinie eine sprechende Kennung
#              mit Kontakt; "Bot" im Namen ist dort ueblich und erwuenscht.
#   Materials  blockt genau das. Am Bestand geprueft (2026-08-15): mit
#   Project    "MaterialsWikidataSuggestBot/0.1" antwortet die API HTTP 403
#              "Forbidden", obwohl der Schluessel gueltig ist - und zwar
#              BEVOR sie den Schluessel prueft. Ausschlaggebend ist allein
#              das Wort "Bot": "SomethingBot/1.0" -> 403, dieselbe Kennung
#              ohne "Bot" -> 200. Kontaktangaben stoeren nicht,
#              "materialswiki/0.1 (mailto:...)" geht durch.
#
# Ein gemeinsamer User-Agent kann beide Anforderungen nicht erfuellen.
USER_AGENT = f"MaterialsWikidataSuggestBot/0.1 ({CONTACT})"
MP_USER_AGENT = f"materialswiki/0.1 ({CONTACT})"

HEADERS = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}

MP_API = "https://api.materialsproject.org"
# Die API verlangt einen Schluessel; ohne ihn antwortet jeder Endpunkt mit
# HTTP 401. Aus der Umgebung statt aus dem Quelltext - ein Schluessel im Repo
# waere ein Leck, sobald das Repo geteilt wird.
MP_API_KEY = konfig.wert("MP_API_KEY")

# Einzelne MP-Materialien haben keine eigene DOI. Belegt wird deshalb mit der
# Referenzpublikation der Datenbank; welches Material gemeint ist, steht als
# mp-ID in der Notiz und in der Belegspalte der CSV.
MP_DOI = "10.1063/1.4812323"  # Jain et al. 2013, APL Materials 1, 011002

# Die Nutzungsbedingungen verlangen fuer einzelne Datensaetze eine EIGENE
# Zitierung zusaetzlich zur Hauptpublikation
# (https://legacy.materialsproject.org/citing, geprueft am 2026-08-16).
# Betroffen ist hier der Elastizitaets-Datensatz: Kompressionsmodul,
# Schubmodul und Poissonzahl stammen samt und sonders daraus. Ohne diesen
# Eintrag wuerde nur Jain et al. zitiert - die Zitierpflicht waere verletzt.
MP_DATASET_DOI = {
    "bulk_modulus": "10.1038/sdata.2015.9",
    "shear_modulus": "10.1038/sdata.2015.9",
    "poisson_ratio": "10.1038/sdata.2015.9",
}
MP_DATASET_WERK = {
    "10.1038/sdata.2015.9": (
        "de Jong et al., Charting the complete elastic properties of "
        "inorganic crystalline compounds, Sci Data 2:150009 (2015)"
    ),
}

# Groesste Seite, die die API ausliefert (Feld meta.max_limit in jeder
# Antwort, geprueft am 2026-08-15). Groessere Mengen kommen ueber _skip.
MP_MAX_LIMIT = 1000

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

REQUEST_DELAY_SEC = 1.0  # höflich sein, Rate Limits respektieren
