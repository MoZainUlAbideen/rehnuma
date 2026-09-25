"""Policy watcher: re-downloads NEPRA's files, compares with the committed lock, writes
nothing, and signals a change with exit code 3 (the workflow opens an issue on it)."""

import hashlib
import json
import urllib.error

import pytest

from rehnuma.policy import cli
from rehnuma.policy import sources as src

DOCS = src.load_sources()


@pytest.fixture()
def lock(tmp_path):
    p = tmp_path / "lock.json"
    p.write_text(json.dumps({d.id: {"sha256": hashlib.sha256(f"%PDF {d.id}".encode())
                                    .hexdigest()} for d in DOCS}), encoding="utf-8")
    return p


def serve(monkeypatch, changed=(), down=(), html=()):
    def fake(url, timeout=60.0):
        d = next(x for x in DOCS if x.url == url)
        if d.id in down:
            raise urllib.error.URLError("timed out")
        if d.id in html:
            return b"<html>maintenance</html>"
        return f"%PDF {d.id}{' v2' if d.id in changed else ''}".encode()
    monkeypatch.setattr(src, "_download", fake)
    monkeypatch.setattr(src.time, "sleep", lambda s: None)


def test_unchanged_documents(monkeypatch, lock):
    serve(monkeypatch)
    assert {r.status for r in src.watch(DOCS, lock)} == {"same"}


def test_a_replaced_pdf_is_reported_and_nothing_is_written(monkeypatch, lock):
    before = lock.read_text(encoding="utf-8")
    serve(monkeypatch, changed={"prosumer-2026"})
    res = {r.doc_id: r for r in src.watch(DOCS, lock)}
    assert res["prosumer-2026"].status == "changed"
    assert res["prosumer-2026"].old_sha != res["prosumer-2026"].new_sha
    assert lock.read_text(encoding="utf-8") == before            # read only


def test_an_outage_is_not_a_change(monkeypatch, lock):
    serve(monkeypatch, down={"csm-2025"}, html={"nm-2015"})
    res = {r.doc_id: r.status for r in src.watch(DOCS, lock)}
    assert res["csm-2025"] == "unreachable" and res["nm-2015"] == "not_pdf"
    assert "changed" not in res.values()


def test_cli_exit_code_and_report(monkeypatch, tmp_path, lock):
    monkeypatch.setattr(src, "LOCK", lock)
    monkeypatch.setattr(cli, "watch", lambda docs: src.watch(docs, lock))
    serve(monkeypatch, changed={"csm-2025"})
    out = tmp_path / "w.md"
    assert cli.main(["watch", "--report", str(out)]) == 3
    report = out.read_text(encoding="utf-8")
    assert "has changed" in report and "Consumer Service Manual" in report
    serve(monkeypatch)
    assert cli.main(["watch"]) == 0


def test_a_blind_run_fails_loudly(monkeypatch, lock):
    """Every document unreachable (NEPRA down, or blocking the runner): not 'no change'."""
    monkeypatch.setattr(cli, "watch", lambda docs: src.watch(docs, lock))
    serve(monkeypatch, down={d.id for d in DOCS})
    assert cli.main(["watch"]) == 4
