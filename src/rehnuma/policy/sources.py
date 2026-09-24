"""The official documents Rehnuma answers from, and a fetcher that notices when they change.

`data/policy/sources.json` lists each document (URL, date, in force / repealed, which one it
amends). `fetch()` downloads them into data/policy/raw/ (git-ignored: public, but large) and
writes a SHA-256 per file into sources.lock.json (committed). A different hash on a later
fetch means NEPRA replaced the file - the seed of the policy watcher: Rehnuma flags the
change for a human to review; it never rewrites its own rules.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

POLICY_DIR = Path("data/policy")
SOURCES = POLICY_DIR / "sources.json"
LOCK = POLICY_DIR / "sources.lock.json"
RAW = POLICY_DIR / "raw"


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    short: str
    date: str
    status: str                 # in_force | repealed
    style: str                  # regulations | amendment | manual
    url: str
    repealed_by: str | None = None
    amends: str | None = None
    note: str | None = None

    @property
    def path(self) -> Path:
        return RAW / f"{self.id}.pdf"


def load_sources(path: Path = SOURCES) -> list[Document]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Document(**d) for d in data["documents"]]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _download(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (rehnuma policy fetch)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch(docs: list[Document], force: bool = False, lock_path: Path = LOCK) -> list[str]:
    """Download missing (or all, with force) documents; return human-readable status lines."""
    RAW.mkdir(parents=True, exist_ok=True)
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
    report = []
    for d in docs:
        if d.path.exists() and not force:
            status = "present"
        else:
            try:
                data = _download(d.url)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                report.append(f"FAILED   {d.id}: {e}. Download it in a browser from {d.url} "
                              f"and save it as {d.path}")
                continue
            if not data.startswith(b"%PDF"):
                report.append(f"FAILED   {d.id}: the server did not return a PDF "
                              f"(got {data[:40]!r}). Save it manually as {d.path}")
                continue
            d.path.write_bytes(data)
            status = "downloaded"
            time.sleep(1)                               # be polite to nepra.org.pk
        digest = sha256(d.path)
        old = lock.get(d.id, {}).get("sha256")
        if old and old != digest:
            status = "CHANGED - NEPRA replaced this file; review answers that cite it"
        lock[d.id] = {"sha256": digest, "bytes": d.path.stat().st_size, "url": d.url}
        report.append(f"{status:<10} {d.id} ({d.path.stat().st_size // 1024} KB)")
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return report
