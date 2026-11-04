"""Wording for the time window behind a recommendation (pure, no DB).

Recommendations normally describe "the last N days". When the patient has
logged nothing in that window the engine falls back to their most recent
readings instead of discarding them, and these helpers make sure the text says
so plainly rather than implying the data is current.
"""

from dataclasses import dataclass
from datetime import date


def format_span(first: date, last: date) -> str:
    """'Sep 23-28', 'Sep 28 - Oct 2' or 'Sep 28' (single day)."""
    if first == last:
        return f"{first:%b} {first.day}"
    if first.year == last.year and first.month == last.month:
        return f"{first:%b} {first.day}\u2013{last.day}"
    return f"{first:%b} {first.day} \u2013 {last:%b} {last.day}"


def days_ago(count: int) -> str:
    if count <= 0:
        return "today"
    return "1 day ago" if count == 1 else f"{count} days ago"


@dataclass(frozen=True)
class ReadingWindow:
    period_days: int
    # None: readings fall inside the requested period. Otherwise the number of
    # days since the latest reading, with the span of the readings used.
    stale_days: int | None = None
    first_day: date | None = None
    last_day: date | None = None

    @property
    def is_stale(self) -> bool:
        return self.stale_days is not None

    @property
    def phrase(self) -> str:
        """Fits 'Your average blood pressure ___ is ...'."""
        if not self.is_stale:
            return f"over the last {self.period_days} days"
        return f"in your most recent readings ({format_span(self.first_day, self.last_day)})"

    @property
    def period_label(self) -> str:
        return "that period" if self.is_stale else "this period"

    @property
    def nudge(self) -> str:
        if not self.is_stale:
            return ""
        return f" Your last reading was {days_ago(self.stale_days)}, so log a new one to bring this up to date."
