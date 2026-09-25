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
    savings_clause: tuple[str, str] | None = None   # (doc id, clause) deciding when it applies

    def __post_init__(self):
        if isinstance(self.savings_clause, list):   # JSON gives a list
            object.__setattr__(self, "savings_clause", tuple(self.savings_clause))

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


# --- the policy watcher -----------------------------------------------------------------
@dataclass(frozen=True)
class WatchResult:
    doc_id: str
    status: str                  # same | changed | new | unreachable | not_pdf
    detail: str = ""
    old_sha: str | None = None
    new_sha: str | None = None


def watch(docs: list[Document], lock_path: Path = LOCK) -> list[WatchResult]:
    """Download every document and compare it with the committed lock - read only: nothing
    is written, the index is not rebuilt. A changed document is a question for a human
    (what changed, which answers cite it), never an automatic update."""
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
    out = []
    for d in docs:
        old = lock.get(d.id, {}).get("sha256")
        try:
            data = _download(d.url)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            out.append(WatchResult(d.id, "unreachable", str(e)[:200], old))
            continue
        if not data.startswith(b"%PDF"):
            out.append(WatchResult(d.id, "not_pdf", f"got {data[:40]!r}", old))
            continue
        new = hashlib.sha256(data).hexdigest()
        status = "new" if old is None else ("same" if new == old else "changed")
        out.append(WatchResult(d.id, status, f"{len(data) // 1024} KB", old, new))
        time.sleep(1)                                   # be polite to nepra.org.pk
    return out


def watch_report(results: list[WatchResult], docs: list[Document]) -> str:
    """Markdown for the GitHub issue the scheduled workflow opens."""
    by_id = {d.id: d for d in docs}
    changed = [r for r in results if r.status == "changed"]
    lines = ["## NEPRA policy watch", ""]
    if changed:
        lines += ["**A document Rehnuma answers from has changed.** Nothing was updated "
                  "automatically. To review:", "",
                  "1. Open the new PDF and compare it with the old one (what changed?).",
                  "2. `uv run rehnuma-policy fetch --force` then `uv run rehnuma-policy ingest`.",
                  "3. `uv run rehnuma-eval-policy` and `uv run rehnuma-ci-evals`: did answers "
                  "move?",
                  "4. Commit the new `sources.lock.json` with a note on what changed.", ""]
    lines += ["| Document | Status | Detail |", "|---|---|---|"]
    for r in results:
        d = by_id[r.doc_id]
        lines.append(f"| [{d.short}]({d.url}) | **{r.status}** | {r.detail} |")
    return "\n".join(lines) + "\n"
