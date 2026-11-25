"""Calendar-day helpers that need neither a database nor settings."""

from datetime import UTC, date, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE_NAME = "Africa/Nairobi"


def resolve_timezone(name: str | None) -> tzinfo:
    """Resolve an IANA timezone name, falling back to the project's local zone.

    HyperSync's demo and clinical context are in Kenya. An absent or invalid
    stored name must not make a patient disappear from a weekly review, so it
    uses the documented project default rather than the clinician's timezone.
    """
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            pass
    return ZoneInfo(DEFAULT_TIMEZONE_NAME)


def local_day(moment: datetime, tz: tzinfo = UTC) -> date:
    """The calendar day `moment` falls on for someone in `tz`.

    Database drivers differ on whether they hand back aware datetimes; a naive
    one is stored UTC by convention, so it is treated as such.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(tz).date()
