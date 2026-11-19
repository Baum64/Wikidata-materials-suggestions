"""Datei-Cache unter cache/ fuer API-Antworten und Ontologie-Dateien.

Schluessel ist ein Hash ueber die Anfrage (URL + Parameter), damit jede
Anfrage genau eine Datei bekommt. Wiederholte Laeufe sind so offline und
schonen den gedrosselten Query-Service.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class Cache:
    def __init__(self, root: Path, max_age_days: float, refresh: bool = False):
        self.root = Path(root)
        self.max_age_s = max_age_days * 86400
        self.refresh = refresh

    @staticmethod
    def key(*parts: object) -> str:
        blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def path(self, namespace: str, name: str) -> Path:
        p = self.root / namespace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def is_fresh(self, p: Path) -> bool:
        return (
            not self.refresh
            and p.exists()
            and (time.time() - p.stat().st_mtime) < self.max_age_s
        )

    def get_json(self, namespace: str, key: str):
        p = self.path(namespace, f"{key}.json")
        if not self.is_fresh(p):
            return None
        return json.loads(p.read_text(encoding="utf-8"))["data"]

    def put_json(self, namespace: str, key: str, data, request: object = None) -> None:
        p = self.path(namespace, f"{key}.json")
        payload = {"request": request, "stored": time.strftime("%Y-%m-%dT%H:%M:%S"), "data": data}
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
