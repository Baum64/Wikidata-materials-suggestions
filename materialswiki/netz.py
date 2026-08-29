"""HTTP-Schicht: EIN Einstiegspunkt fuer alle Gegenstellen.

Hier steht die Drosselung, der Retry und die Kennung, mit der sich das
Werkzeug ausweist. Warum es ZWEI Kennungen braucht und warum je Gegenstelle
gedrosselt wird, steht bei den jeweiligen Namen; die Messungen dazu im
README ("Laufzeit", "Zwei User-Agents").

Alles, was ins Netz geht, geht durch request_with_retry - so kann keine
Stelle das Rate-Limit versehentlich umgehen, und die Tests sperren mit einer
einzigen Attrappe den gesamten Netzzugriff.
"""

import sys
import time

import requests

from . import konfiguration as konf

REQUEST_DELAY_SEC = konf.REQUEST_DELAY_SEC
HEADERS = konf.HEADERS


# Letzte Anfrage JE GEGENSTELLE. Eine gemeinsame Uhr fuer alle waere
# unnoetig teuer: ein Lauf spricht sieben verschiedene Server an (Wikidata,
# COD, MP, zwei Wikipedias, WebBook), und die Ruecksicht gilt jedem einzeln.
# Gemessen an 5 Oxiden: 44 Anfragen auf sieben Gegenstellen, mit gemeinsamer
# Uhr 44 Wartesekunden, mit getrennten hoechstens so viele, wie die
# meistbefragte Gegenstelle bekommt.
_LAST_REQUEST: dict = {}


def _gegenstelle(url: str) -> str:
    """Hostname als Schluessel der Drosselung."""
    return url.split("/")[2] if "//" in url else url


def request_with_retry(method: str, url: str, attempts: int = 4, **kwargs):
    """Einziger HTTP-Einstiegspunkt: drosselt und wiederholt bei 429/5xx.

    Die Drosselung steckt hier statt in den Aufrufern - so wird genau dann
    gewartet, wenn wirklich eine Anfrage rausgeht (Cache-Treffer bremsen
    nichts mehr), und keine Stelle kann das Rate-Limit versehentlich umgehen.
    Gewartet wird JE GEGENSTELLE, siehe _LAST_REQUEST.

    Ohne Retry reisst ein einzelner 502 den kompletten Lauf ab; der
    Wikidata-Query-Service liefert die unter Last sporadisch.
    """
    host = _gegenstelle(url)
    delay = 2.0
    # timeout ueberschreibbar - der Query-Service braucht fuer groessere
    # SPARQL-Abfragen mehr als 60s, alle anderen Aufrufer bleiben dabei.
    timeout = kwargs.pop("timeout", 60)
    for attempt in range(1, attempts + 1):
        wait = REQUEST_DELAY_SEC - (time.monotonic() - _LAST_REQUEST.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST[host] = time.monotonic()
        try:
            # headers ueberschreibbar - die MP-API braucht zusaetzlich
            # X-API-KEY, alle anderen Aufrufer bleiben bei HEADERS.
            resp = requests.request(
                method, url, timeout=timeout,
                **{"headers": HEADERS, **kwargs}
            )
        except requests.RequestException:
            if attempt == attempts:
                raise
        else:
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
            if attempt == attempts:
                resp.raise_for_status()
            print(
                f"  HTTP {resp.status_code} von {url} - Versuch "
                f"{attempt}/{attempts}, warte {delay:.0f}s",
                file=sys.stderr,
            )
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"Unerreichbar: {url}")


def get_with_retry(url: str, params: dict, attempts: int = 4):
    resp = request_with_retry("GET", url, attempts, params=params)
    resp.raise_for_status()
    return resp
