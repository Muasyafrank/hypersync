"""Treatment-review flag: decision support for CLINICIANS, never shown to patients.

It answers one question a clinician cannot easily see from a list of readings:
"has this patient's pressure stayed in a concerning band for weeks, and what
should the clinician confirm next?"

What it does
    * Splits the last REVIEW_WEEKS weeks into 7-day bins and classifies each
      week's average with the same bands as everywhere else.
    * Flags a patient when their weekly average was elevated/high in
      MIN_WEEKS_ELEVATED_OR_HIGH of those weeks AND remains elevated/high in
      the most recent week (so a patient who has already improved is not
      flagged).
    * Works in both directions: sustained elevated/high readings and sustained
      low readings. These are application bands, not a configured clinical
      treatment target.
    * Lists what to confirm first: what medication use was actually recorded,
      whether readings were taken properly, and which lifestyle contributors
      are logged.

What it deliberately does not do
    * It never suggests a drug, a dose or a change. It says "consider a review".
    * It never assumes that the patient takes medication when none was logged.
    * It is never returned by any patient endpoint.
    * It is not a diagnosis. Every threshold below is listed in
      docs/advice-for-clinical-review.md for a clinician to confirm or change.

A clinician can record that they have reviewed a patient. A matching flag is
then paused for SNOOZE_DAYS as a follow-up window; the suitability of that
window remains a clinical judgement.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from sqlalchemy.orm import Session

from app.core.bp_classification import (
    ELEVATED,
    HIGH,
    LOW,
    LOW_DIASTOLIC,
    LOW_SYSTOLIC,
    NO_DATA,
    classify_bp,
)
from app.core.factor_insights import LABELS, RISK_PREDICATES, flagged_fields, poorly_measured, summarize_log
from app.core.localtime import local_day

# --- Thresholds (all of these appear on the clinical review sheet) -------------

REVIEW_WEEKS = 4  # how far back to look, in 7-day weeks
MIN_READINGS_PER_WEEK = 3  # a week with fewer readings is not trusted
MIN_WEEKS_WITH_DATA = 3  # weeks that must have enough readings to judge at all
MIN_WEEKS_ELEVATED_OR_HIGH = 3  # elevated/high weeks needed before flagging
MIN_WEEKS_LOW = 3  # low weeks needed before flagging
PRIORITY_HIGH_WEEKS = 3  # weeks in the HIGH band that raise the flag to "priority"
ADHERENCE_MIN_ANSWERS = 5  # logged answers needed before adherence is judged
ADHERENCE_POOR_MISSED_SHARE = 0.20  # missed/answers at or above this = poor adherence
MEASUREMENT_CAUTION_SHARE = 0.30  # share of hurried readings that casts doubt on the numbers
MEASUREMENT_CAUTION_MIN_READINGS = 2
SNOOZE_DAYS = 28  # pause after a clinician records a review

SUSTAINED_ELEVATED_HIGH = "sustained_elevated_high"
SUSTAINED_LOW = "sustained_low"
ROUTINE = "routine"
PRIORITY = "priority"

DISCLAIMER = (
    "Decision support only. This flags a pattern for a clinician to consider. It does not recommend a drug or "
    "dose and does not replace clinical judgement."
)


# --- Result shapes ---------------------------------------------------------------


@dataclass(frozen=True)
class WeekSummary:
    start: date
    end: date
    reading_count: int
    avg_systolic: float | None
    avg_diastolic: float | None
    status: str  # a BP band, or NO_DATA when the week has too few readings


@dataclass(frozen=True)
class Adherence:
    answered: int
    missed: int
    status: str  # "good" | "poor" | "unknown"


@dataclass(frozen=True)
class Measurement:
    total: int
    hurried: int
    caution: bool


@dataclass
class Assessment:
    flagged: bool = False  # the criteria are met
    active: bool = False  # flagged and not paused by a recent review
    kind: str | None = None
    level: str | None = None
    weeks_in_flagged_band: int = 0  # how many judgeable weeks were in the band that triggered the flag
    headline: str | None = None
    weeks: list[WeekSummary] = field(default_factory=list)  # oldest first
    adherence: Adherence = Adherence(0, 0, "unknown")
    measurement: Measurement = Measurement(0, 0, False)
    confirm_first: list[str] = field(default_factory=list)
    contributors: list[str] = field(default_factory=list)
    snoozed_until: datetime | None = None
    last_reviewed_at: datetime | None = None
    # Start of the current uninterrupted flagged run. A review from an older
    # episode must not silence a later relapse.
    episode_started_at: datetime | None = None


# --- Pure rules ------------------------------------------------------------------


def weekly_summaries(readings, end_day: date, tz: tzinfo = UTC) -> list[WeekSummary]:
    """REVIEW_WEEKS consecutive 7-day bins ending on `end_day` (the user's local day), oldest first."""
    buckets: dict[int, list] = defaultdict(list)
    for r in readings:
        age_days = (end_day - local_day(r.recorded_at, tz)).days
        if 0 <= age_days < REVIEW_WEEKS * 7:
            buckets[age_days // 7].append(r)

    weeks = []
    for index in range(REVIEW_WEEKS - 1, -1, -1):  # oldest bin first
        rows = buckets.get(index, [])
        start = end_day - timedelta(days=7 * index + 6)
        end = end_day - timedelta(days=7 * index)
        if len(rows) < MIN_READINGS_PER_WEEK:
            weeks.append(WeekSummary(start, end, len(rows), None, None, NO_DATA))
            continue
        avg_s = round(sum(r.systolic for r in rows) / len(rows), 1)
        avg_d = round(sum(r.diastolic for r in rows) / len(rows), 1)
        weeks.append(WeekSummary(start, end, len(rows), avg_s, avg_d, classify_bp(avg_s, avg_d)))
    return weeks


def latest_entry_per_day(entries) -> list:
    """Keep one lifestyle entry per local calendar day.

    The API now accepts only one check-in per patient per day, but older
    databases may contain duplicates. Keeping the last entry supplied for each
    date makes adherence count *days*, not rows, even while those old rows are
    being cleaned up. Callers pass entries oldest-first.
    """
    latest = {}
    for entry in entries:
        latest[entry.logged_date] = entry
    return list(latest.values())


def judge_adherence(medication_answers: list[bool]) -> Adherence:
    answered = len(medication_answers)
    missed = sum(1 for taken in medication_answers if not taken)
    if answered < ADHERENCE_MIN_ANSWERS:
        return Adherence(answered, missed, "unknown")
    status = "poor" if missed / answered >= ADHERENCE_POOR_MISSED_SHARE else "good"
    return Adherence(answered, missed, status)


def judge_measurement(readings) -> Measurement:
    readings = list(readings)
    hurried = sum(1 for r in readings if poorly_measured(r))
    caution = (
        hurried >= MEASUREMENT_CAUTION_MIN_READINGS
        and len(readings) > 0
        and hurried / len(readings) >= MEASUREMENT_CAUTION_SHARE
    )
    return Measurement(len(readings), hurried, caution)


def _elevated_or_high(week: WeekSummary) -> bool:
    return week.status in (ELEVATED, HIGH)


def _episode_started_at(weeks: list[WeekSummary], kind: str, tz: tzinfo) -> datetime | None:
    """Return when the current uninterrupted flagged run began.

    The review window contains four weekly bins. A relapse after a gap starts
    a new run, so a review from the earlier run cannot pause it.
    """
    if kind == SUSTAINED_LOW:
        qualifies = lambda week: week.status == LOW  # noqa: E731
    else:
        qualifies = _elevated_or_high

    index = len(weeks) - 1
    if index < 0 or not qualifies(weeks[index]):
        return None
    while index > 0 and qualifies(weeks[index - 1]):
        index -= 1
    return datetime.combine(weeks[index].start, time.min, tzinfo=tz)


def assess(
    readings,
    entries,
    now: datetime,
    tz: tzinfo = UTC,
    last_reviewed_at: datetime | None = None,
    last_reviewed_kind: str | None = None,
    last_reviewed_level: str | None = None,
) -> Assessment:
    """Decide whether one patient needs a treatment-review flag.

    readings: objects with recorded_at, systolic, diastolic, rested_before, stimulant_before
    entries:  lifestyle-log objects (logged_date and the logged habit fields)
    """
    end_day = local_day(now, tz)
    window_start = end_day - timedelta(days=REVIEW_WEEKS * 7 - 1)
    # Keep one inclusive local-day window for every statistic. Future-dated
    # legacy readings must not change measurement-quality percentages.
    readings = [r for r in readings if window_start <= local_day(r.recorded_at, tz) <= end_day]
    entries = latest_entry_per_day([e for e in entries if window_start <= e.logged_date <= end_day])

    weeks = weekly_summaries(readings, end_day, tz)
    result = Assessment(weeks=weeks)

    latest = weeks[-1]
    with_data = [w for w in weeks if w.status != NO_DATA]
    if len(with_data) < MIN_WEEKS_WITH_DATA or latest.status == NO_DATA:
        return result  # not enough recent data to say anything

    elevated_or_high = [w for w in with_data if _elevated_or_high(w)]
    low = [w for w in with_data if w.status == LOW]

    if _elevated_or_high(latest) and len(elevated_or_high) >= MIN_WEEKS_ELEVATED_OR_HIGH:
        result.kind = SUSTAINED_ELEVATED_HIGH
        high_weeks = sum(1 for w in with_data if w.status == HIGH)
        result.level = PRIORITY if high_weeks >= PRIORITY_HIGH_WEEKS else ROUTINE
        result.weeks_in_flagged_band = len(elevated_or_high)
    elif latest.status == LOW and len(low) >= MIN_WEEKS_LOW:
        result.kind = SUSTAINED_LOW
        result.level = ROUTINE
        result.weeks_in_flagged_band = len(low)
    else:
        return result

    result.flagged = True
    result.episode_started_at = _episode_started_at(weeks, result.kind, tz)
    result.adherence = judge_adherence(
        [
            e.medication_taken
            for e in entries
            if e.medication_taken is not None and getattr(e, "medication_prescribed", None) is not False
        ]
    )
    result.measurement = judge_measurement(readings)

    history = summarize_log(entries)
    flagged_habits = flagged_fields(history, window_start)
    result.contributors = [LABELS[name] for name in RISK_PREDICATES if name in flagged_habits]

    result.headline = _headline(result, latest)
    result.confirm_first = _confirm_first(result, bool(entries))

    apply_review_snooze(
        result,
        last_reviewed_at,
        now,
        reviewed_kind=last_reviewed_kind,
        reviewed_level=last_reviewed_level,
        strict_match=last_reviewed_kind is not None or last_reviewed_level is not None,
    )
    return result


def apply_review_snooze(
    result: Assessment,
    reviewed_at: datetime | None,
    now: datetime,
    *,
    reviewed_kind: str | None = None,
    reviewed_level: str | None = None,
    strict_match: bool = False,
) -> None:
    """Pause only a review of the current flag, level and episode."""
    result.last_reviewed_at = reviewed_at
    result.snoozed_until = None

    if reviewed_at is not None:
        if reviewed_at.tzinfo is None:
            reviewed_at = reviewed_at.replace(tzinfo=UTC)
        matches = True
        if strict_match:
            matches = reviewed_kind == result.kind and reviewed_level == result.level
        in_current_episode = result.episode_started_at is None or reviewed_at >= result.episode_started_at
        if matches and in_current_episode:
            paused_until = reviewed_at + timedelta(days=SNOOZE_DAYS)
            if now < paused_until:
                result.snoozed_until = paused_until

    result.active = result.flagged and result.snoozed_until is None


def _headline(a: Assessment, latest: WeekSummary) -> str:
    n = a.weeks_in_flagged_band
    adherence = a.adherence
    if a.kind == SUSTAINED_LOW:
        text = (
            f"Average blood pressure was in the low band (below {LOW_SYSTOLIC}/{LOW_DIASTOLIC}) in {n} of the last "
            f"{REVIEW_WEEKS} weeks and remains low in the most recent week "
            f"({latest.avg_systolic:g}/{latest.avg_diastolic:g}). Review possible causes and ask about dizziness or falls."
        )
    else:
        text = (
            f"Average blood pressure was in the elevated/high band in {n} of the last {REVIEW_WEEKS} weeks and remains "
            f"elevated/high in the most recent week ({latest.avg_systolic:g}/{latest.avg_diastolic:g})."
        )

    if adherence.status == "good":
        taken = adherence.answered - adherence.missed
        text += (
            f" Medication is logged as taken on {taken} of {adherence.answered} days; this does not rule out other "
            f"causes, so review the pattern with the patient."
        )
    elif adherence.status == "poor":
        text += (
            f" Medication is logged as not taken on {adherence.missed} of {adherence.answered} days; explore adherence "
            f"support and other causes."
        )
    else:
        text += (
            f" Medication use is not logged often enough to tell (fewer than {ADHERENCE_MIN_ANSWERS} answers); confirm "
            f"what medication, if any, the patient takes, and assess other causes."
        )
    if a.measurement.caution:
        text += (
            f" Note: {a.measurement.hurried} of {a.measurement.total} readings were taken without rest or soon after "
            f"coffee, tea, smoking or exercise, so confirm technique too."
        )
    return text


def _confirm_first(a: Assessment, has_log: bool) -> list[str]:
    items = []
    ad = a.adherence
    if ad.status == "unknown":
        items.append(
            f"Medication use: not enough logged answers ({ad.answered}). Confirm what medication, if any, the patient takes."
        )
    elif ad.status == "poor":
        items.append(f"Medication use: logged as not taken on {ad.missed} of {ad.answered} days. Explore why.")
    else:
        items.append(f"Medication use: logged as taken on {ad.answered - ad.missed} of {ad.answered} days.")

    m = a.measurement
    if m.caution:
        items.append(
            f"Measurement: {m.hurried} of {m.total} readings were hurried or after a stimulant. Check technique."
        )
    elif m.total:
        items.append("Measurement: most readings were not flagged as hurried (conditions are optional to record).")

    if a.contributors:
        items.append(f"Lifestyle: logged as risks this period: {', '.join(a.contributors)}.")
    elif has_log:
        items.append("Lifestyle: no risky habits logged this period.")
    else:
        items.append("Lifestyle: nothing logged this period.")
    return items


# --- Database loading --------------------------------------------------------------


def assess_patients(
    db: Session,
    patient_ids,
    now: datetime | None = None,
    tz: tzinfo = UTC,
    timezones: dict | None = None,
) -> dict:
    """Assess many patients with three queries in total (not three per patient).

    `timezones` maps patient IDs to their own stored calendar timezone. The
    single `tz` remains a backwards-compatible fallback for callers that have
    no patient context.
    """
    # Imported here to keep the pure rules above importable without a database.
    from sqlalchemy import func

    from app.models.environmental_factor import EnvironmentalFactor
    from app.models.reading import BPReading
    from app.models.treatment_review import TreatmentReviewRecord

    patient_ids = list(patient_ids)
    if not patient_ids:
        return {}
    now = now or datetime.now(UTC)
    effective_tz = {patient_id: (timezones or {}).get(patient_id, tz) for patient_id in patient_ids}
    earliest_day = min(local_day(now, zone) for zone in effective_tz.values())
    since = now - timedelta(days=REVIEW_WEEKS * 7 + 1)  # one day of slack for timezone edges

    readings_by: dict = defaultdict(list)
    for r in db.query(BPReading).filter(BPReading.patient_id.in_(patient_ids), BPReading.recorded_at >= since):
        readings_by[r.patient_id].append(r)

    entries_by: dict = defaultdict(list)
    log_since = earliest_day - timedelta(days=REVIEW_WEEKS * 7)
    for e in (
        db.query(EnvironmentalFactor)
        .filter(EnvironmentalFactor.patient_id.in_(patient_ids), EnvironmentalFactor.logged_date >= log_since)
        .order_by(EnvironmentalFactor.logged_date.asc(), EnvironmentalFactor.created_at.asc())
    ):
        entries_by[e.patient_id].append(e)

    review_times = {
        (patient_id, flag_kind, flag_level): reviewed_at
        for patient_id, flag_kind, flag_level, reviewed_at in db.query(
            TreatmentReviewRecord.patient_id,
            TreatmentReviewRecord.flag_kind,
            TreatmentReviewRecord.flag_level,
            func.max(TreatmentReviewRecord.reviewed_at),
        )
        .filter(
            TreatmentReviewRecord.patient_id.in_(patient_ids),
            TreatmentReviewRecord.flag_kind.isnot(None),
            TreatmentReviewRecord.flag_level.isnot(None),
        )
        .group_by(
            TreatmentReviewRecord.patient_id,
            TreatmentReviewRecord.flag_kind,
            TreatmentReviewRecord.flag_level,
        )
        .all()
    }

    out = {}
    for pid in patient_ids:
        result = assess(readings_by.get(pid, []), entries_by.get(pid, []), now, effective_tz[pid])
        reviewed = review_times.get((pid, result.kind, result.level)) if result.kind else None
        if reviewed is not None and reviewed.tzinfo is None:
            reviewed = reviewed.replace(tzinfo=UTC)  # some drivers return naive UTC
        apply_review_snooze(
            result,
            reviewed,
            now,
            reviewed_kind=result.kind,
            reviewed_level=result.level,
            strict_match=True,
        )
        out[pid] = result
    return out
