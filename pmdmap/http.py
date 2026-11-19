"""Einziger Netzzugang von pmdmap.

Drosselung je Gegenstelle und Retry stecken hier statt in den Aufrufern: so
wird genau dann gewartet, wenn wirklich eine Anfrage hinausgeht (Cache-Treffer
bremsen nicht), und keine Stelle kann das Rate-Limit versehentlich umgehen.

Tests ersetzen _send (siehe conftest.py) und bleiben damit offline.
"""
from __future__ import annotations

import sys
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests

from .config import NetConfig


def _send(session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
    """Der eine Aufruf, der wirklich ins Netz geht."""
    return session.request(method, url, **kwargs)


def _retry_after_s(resp: requests.Response) -> float | None:
    """Retry-After lesen (Sekunden oder HTTP-Datum)."""
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


class HttpClient:
    def __init__(self, net: NetConfig, session: requests.Session | None = None):
        self.net = net
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": net.user_agent})
        self._last: dict[str, float] = {}

    def _throttle(self, host: str) -> None:
        pause = self.net.throttle_s.get(host, self.net.throttle_s.get("default", 1.0))
        wait = pause - (time.monotonic() - self._last.get(host, float("-inf")))
        if wait > 0:
            print(f"  warte {wait:.0f}s (Drosselung {host})", file=sys.stderr)
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Anfrage mit Drosselung; Wiederholung bei 429, 5xx und Netzfehlern."""
        host = urlsplit(url).hostname or url
        backoff = 5.0
        for attempt in range(1, self.net.attempts + 1):
            self._throttle(host)
            last = attempt == self.net.attempts
            try:
                resp = _send(self.session, method, url, timeout=self.net.timeout_s, **kwargs)
            except requests.RequestException as exc:
                if last:
                    raise
                wait, reason = backoff, type(exc).__name__
            else:
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    return resp
                if last:
                    resp.raise_for_status()
                reason = f"HTTP {resp.status_code}"
                if resp.status_code == 429:
                    wait = _retry_after_s(resp) or self.net.wait_429_s
                else:
                    wait = _retry_after_s(resp) or backoff
            print(
                f"  {reason} von {host} - Versuch {attempt}/{self.net.attempts}, "
                f"warte {wait:.0f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
            backoff *= 2
        raise RuntimeError(f"unerreichbar: {url}")  # pragma: no cover
