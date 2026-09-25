"""rehnuma-ci-evals: run every eval that needs no API key and fail if a metric drops.

  uv run rehnuma-ci-evals            # prints a table; exit code 1 on any regression

Runs in CI on every push (.github/workflows/ci.yml). Floors live in
data/eval/ci_thresholds.json and are set to what the code achieves today, so a change that
makes any of these worse fails the build instead of quietly shipping:

  * auditor      - 2,000 synthetic bills: detection, localisation, false positives
  * summary      - template summaries of the real bills: every number from the engine,
                   every must-mention fact, right language
  * retrieval    - NEPRA clause retrieval, lexical and with the production query rewrites
                   REPLAYED from a frozen file (no Groq call), per split and language
  * router       - which part of the assistant each question reaches
  * forecast     - the outlook prices months with the engine that reproduces real bills

Anything that needs a live model (extraction, LLM answers) is measured by its own eval
and is not gated here: a flaky free-tier API must not turn the build red.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

THRESHOLDS = Path("data/eval/ci_thresholds.json")
REWRITES = Path("data/eval/ci/rewrites_all.json")
TOL = 1e-9
# Limits are stored rounded DOWN to 3 decimals (7/8 -> 0.875, 10/11 -> 0.909). A floor
# rounded UP (15/16 -> 0.938) would fail on the very value it was taken from - found when
# the gate first ran. "Improved" needs a real change, not the rounding remainder.
IMPROVED = 0.005


@dataclass
class Result:
    name: str
    value: float
    floor: float | None = None          # value must be >= floor
    ceiling: float | None = None        # value must be <= ceiling

    @property
    def ok(self) -> bool:
        return ((self.floor is None or self.value >= self.floor - TOL)
                and (self.ceiling is None or self.value <= self.ceiling + TOL))

    @property
    def improved(self) -> bool:
        return (self.floor is not None and self.value > self.floor + IMPROVED) or \
               (self.ceiling is not None and self.value < self.ceiling - IMPROVED)


def auditor_metrics() -> dict[str, float]:
    from rehnuma.evals.auditor_eval import run
    o = run(2000, 42)["overall"]
    return {"auditor.detection_rate": o["detection_rate"],
            "auditor.localisation_rate": o["localisation_rate"],
            "auditor.false_positive_rate": o["false_positive_rate"]}


def summary_metrics() -> dict[str, float]:
    from rehnuma.evals.summary_eval import run
    o = run(["data/labels/real"], "template", ["ur", "en"])["overall"]
    return {"summary.faithfulness": o["mean_faithfulness"],
            "summary.coverage": o["mean_coverage"],
            "summary.language_ok": o["language_ok_rate"]}


def retrieval_metrics() -> dict[str, float]:
    from rehnuma.evals.policy_retrieval_eval import evaluate, load_replay
    from rehnuma.policy.parse import CHUNKS, load_chunks
    from rehnuma.policy.retrieve import PolicyIndex

    questions = json.loads(Path("data/policy/retrieval_questions.json")
                           .read_text(encoding="utf-8"))["questions"]
    index = PolicyIndex(load_chunks(CHUNKS))
    out: dict[str, float] = {}
    for setting, kwargs in (("lexical", {}),
                            ("rewrite", {"rewrite_mode": "all",
                                         "replay": load_replay(REWRITES)})):
        rep = evaluate(index, questions, **kwargs)
        out[f"retrieval.{setting}.not_in_index"] = len(rep["not_in_index"])
        for group, by_method in rep["summary"].items():
            if setting == "lexical" and group.endswith("/ur"):
                continue                 # raw Urdu without a rewrite is 0% by design
            out[f"retrieval.{setting}.{group}.hit@5"] = by_method["hybrid"]["hit@5"]
    return out


def router_metrics() -> dict[str, float]:
    from rehnuma.evals.route_eval import QUESTIONS, evaluate
    rep = evaluate(json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"])
    return {f"router.{g}.accuracy": m["accuracy"] for g, m in rep["groups"].items()}


def forecast_metrics() -> dict[str, float]:
    from rehnuma.evals.forecast_eval import run
    rep = run()
    rows = rep["engine"]
    recon = rep["solar"]["reconstruction"]
    return {"forecast.engine_reproduces_bills": sum(bool(r.get("ok")) for r in rows)
            / (len(rows) or 1),
            "forecast.solar_months_rebuilt": sum(r["ok"] for r in recon) / (len(recon) or 1)}


SUITES: dict[str, Callable[[], dict[str, float]]] = {
    "auditor": auditor_metrics, "summary": summary_metrics,
    "retrieval": retrieval_metrics, "router": router_metrics, "forecast": forecast_metrics,
}


def check(metrics: dict[str, float], thresholds: dict) -> tuple[list[Result], list[str]]:
    """Compare metrics with their limits. A metric with no limit, or a limit with no
    metric, is an error too - otherwise a renamed metric silently stops being gated."""
    results, problems = [], []
    limits = {k: v for k, v in thresholds.items() if not k.startswith("_")}
    for name, value in sorted(metrics.items()):
        lim = limits.get(name)
        if lim is None:
            problems.append(f"{name} = {value:.3f} has no limit in {THRESHOLDS}")
            continue
        results.append(Result(name, value, lim.get("min"), lim.get("max")))
    for name in sorted(set(limits) - set(metrics)):
        problems.append(f"{name} has a limit but was not measured")
    return results, problems


def render(results: list[Result], problems: list[str]) -> str:
    lines = ["## Rehnuma evals (no API calls)", "", "| Metric | Value | Limit | |",
             "|---|---|---|---|"]
    for r in results:
        limit = f">= {r.floor:g}" if r.floor is not None else f"<= {r.ceiling:g}"
        mark = "FAIL" if not r.ok else ("improved - raise the limit" if r.improved else "ok")
        lines.append(f"| {r.name} | {r.value:.3f} | {limit} | {mark} |")
    if problems:
        lines += ["", *[f"- **{p}**" for p in problems]]
    failed = [r for r in results if not r.ok]
    lines += ["", f"**{'FAILED' if failed or problems else 'PASSED'}**: {len(results)} metrics, "
              f"{len(failed)} below their limit, {len(problems)} configuration problem(s)."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    metrics: dict[str, float] = {}
    for suite in SUITES.values():
        metrics.update(suite())
    results, problems = check(metrics, thresholds)
    md = render(results, problems)
    print(md)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")      # shown on the Actions run page
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)
    return 1 if problems or any(not r.ok for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
