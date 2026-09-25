"""The CI eval gate: it must pass on today's code and fail on a regression."""

import json
from pathlib import Path

from rehnuma.evals.ci_gate import REWRITES, THRESHOLDS, Result, check, main


def test_gate_passes_on_current_code(capsys):
    assert main() == 0, capsys.readouterr().out


def test_a_drop_below_the_floor_fails():
    results, problems = check({"retrieval.x.hit@5": 0.80}, {"retrieval.x.hit@5": {"min": 0.9}})
    assert not problems and not results[0].ok


def test_a_rise_above_a_ceiling_fails():
    results, _ = check({"auditor.false_positive_rate": 0.01},
                       {"auditor.false_positive_rate": {"max": 0.0}})
    assert not results[0].ok


def test_unlimited_or_unmeasured_metrics_are_problems():
    """A renamed metric must not silently stop being gated."""
    _, problems = check({"new.metric": 1.0}, {"_note": "x", "old.metric": {"min": 1.0}})
    assert any("new.metric" in p for p in problems)
    assert any("old.metric" in p for p in problems)


def test_floor_taken_from_a_value_passes_on_that_value():
    """Regression: 15/16 = 0.9375 stored as 0.938 (rounded up) failed on itself."""
    assert Result("m", 15 / 16, floor=0.937).ok and not Result("m", 15 / 16, floor=0.937).improved


def test_thresholds_are_rounded_down_not_up():
    t = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    for name, lim in t.items():
        if isinstance(lim, dict) and "min" in lim:
            assert round(lim["min"], 3) == lim["min"], name


def test_frozen_rewrites_cover_every_urdu_question():
    """Without a rewrite an Urdu question scores 0% - a missing row would look like a
    retrieval regression."""
    qs = json.loads(Path("data/policy/retrieval_questions.json")
                    .read_text(encoding="utf-8"))["questions"]
    have = {r["id"] for r in json.loads(REWRITES.read_text(encoding="utf-8"))["rows"]}
    assert {q["id"] for q in qs if q["lang"] == "ur"} <= have
