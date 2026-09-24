"""Per-visitor daily limits, so strangers can't burn the free Groq/Gemini quota.

In memory: the Space runs a single process, and losing the counters on a restart only
makes the limit more generous. Sample bills and cached answers never count - only calls
that reach an LLM or the vision model do.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

DEFAULT_LIMITS = {"upload": 5, "ask": 20}


def limits_from_env() -> dict[str, int]:
    """REHNUMA_LIMIT_UPLOAD / REHNUMA_LIMIT_ASK override the defaults."""
    return {kind: int(os.environ.get(f"REHNUMA_LIMIT_{kind.upper()}", n))
            for kind, n in DEFAULT_LIMITS.items()}


def client_key(headers: dict, peer: str | None) -> str:
    """Behind the Spaces proxy the visitor is the FIRST X-Forwarded-For address."""
    fwd = headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or peer or "unknown"


def seconds_to_midnight_utc(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds()) + 1


@dataclass
class DailyLimiter:
    limits: dict[str, int] = field(default_factory=limits_from_env)
    _counts: dict[tuple[str, str, str], int] = field(default_factory=dict)

    def _day(self, now: datetime | None) -> str:
        return (now or datetime.now(UTC)).strftime("%Y-%m-%d")

    def remaining(self, key: str, kind: str, now: datetime | None = None) -> int:
        return self.limits[kind] - self._counts.get((key, kind, self._day(now)), 0)

    def take(self, key: str, kind: str, now: datetime | None = None) -> bool:
        """Consume one unit; False (and nothing consumed) if the visitor is out."""
        if self.remaining(key, kind, now) <= 0:
            return False
        day = self._day(now)
        self._counts = {k: v for k, v in self._counts.items() if k[2] == day}   # drop old days
        self._counts[(key, kind, day)] = self._counts.get((key, kind, day), 0) + 1
        return True
