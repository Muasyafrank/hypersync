"""What the patient's lifestyle log says about their blood pressure, and what to do about it.

Pure functions (no database, no ML) so the rules are easy to test. The engine
in ml_recommendation_engine.py feeds them the logged entries and daily readings.

Three ideas:

1. **Every logged habit is covered.** Nine things can be logged; each has one
   rule for "this points the unhealthy way" (RISK_PREDICATES) and one concrete
   tip for avoiding it (TIPS). Nothing that is logged is silently ignored.

2. **Patterns over days, not just the latest entry.** A habit is raised when
   it was risky on the most recent entry or on at least two days in the
   period, so one good day cannot hide a week of bad ones.

3. **Surroundings and measurement conditions count too.** Temperature and
   noise are logged like any other habit. How each reading was taken (rested?
   caffeine, smoking or exercise just before?) is checked separately, because a
   hurried reading can look like high blood pressure when it is not.

4. **The patient's own data first.** When readings are clearly higher on the
   days a habit was risky than on the days it wasn't (same person, same
   period), that is stated plainly, with the numbers. It shows a link in
   their own log; the wording says it is not proof of cause.
"""

from dataclasses import dataclass, field
from datetime import date

from app.core.lifestyle_factors import (
    DATA_SUPPORTED_SUFFIX,
    GUIDELINE_MESSAGES,
    rank_factors,
)

# --- 1. Which logged values count as a risk ---------------------------------


def _value(v):
    return v.value if hasattr(v, "value") else v


# One predicate per logged field; only called with non-None answers.
RISK_PREDICATES = {
    "salt_intake": lambda v: _value(v) in ("moderate", "high"),
    "alcohol_consumed": bool,
    "smoked": bool,
    "physical_activity_minutes": lambda v: v < 20,
    "diet_adherence": lambda v: not v,
    "sleep_hours": lambda v: v < 6,
    "stress_level": lambda v: _value(v) == "high",
    "caffeine_intake": lambda v: _value(v) == "high",
    "medication_taken": lambda v: not v,
    "temperature_feel": lambda v: _value(v) == "cold",  # cold narrows blood vessels
    "noise_level": lambda v: _value(v) == "loud",
}

# The same rules in plain words, for the clinical review sheet (app/core/clinical_review.py).
# A test makes sure every rule above has an entry here.
RISK_TEXT = {
    "salt_intake": "Moderate or high",
    "alcohol_consumed": "Any alcohol",
    "smoked": "Smoked",
    "physical_activity_minutes": "Under 20 minutes",
    "diet_adherence": "Did not follow the advised diet",
    "sleep_hours": "Under 6 hours",
    "stress_level": "High",
    "caffeine_intake": "High",
    "medication_taken": "Missed a dose",
    "temperature_feel": "Cold",
    "noise_level": "Loud",
}

# Logged field -> the model feature of the same name (the survey-trained model
# covers only these five; the other four are plain clinical-guidance rules).
MODEL_FEATURE = {
    "salt_intake": "salt_score",
    "alcohol_consumed": "alcohol_consumed",
    "smoked": "smoked",
    "physical_activity_minutes": "activity_minutes",
    "diet_adherence": "diet_adherence",
}
_FIELD_OF = {feature: logged for logged, feature in MODEL_FEATURE.items()}

# rank_factors only needs to know whether each feature is on the risky side, so
# a flagged habit is represented by a clearly risky value and the rest by a
# clearly healthy one.
_RISKY_VALUE = {"salt_score": 3, "alcohol_consumed": 1, "activity_minutes": 0, "diet_adherence": 0, "smoked": 1}
_HEALTHY_VALUE = {"salt_score": 0, "alcohol_consumed": 0, "activity_minutes": 90, "diet_adherence": 1, "smoked": 0}

RULE_PROVENANCE = " (General clinical guidance; this is not part of the trained model.)"
RULE_MESSAGES = {
    "sleep_hours": "You've logged under 6 hours of sleep. Poor sleep is linked to higher blood pressure.",
    "stress_level": "You've logged high stress. Stress can raise blood pressure.",
    "caffeine_intake": (
        "You've logged a lot of coffee or tea. Caffeine can push blood pressure up for a few hours after each cup."
    ),
    "medication_taken": "You've logged a missed medication dose. Missing doses can lead to higher readings.",
    "temperature_feel": "You've logged cold weather. Cold narrows blood vessels and can push blood pressure up.",
    "noise_level": "You've logged a loud day. Ongoing loud noise is a stressor and is linked to higher blood pressure.",
}
RULE_ORDER = [
    "medication_taken",
    "sleep_hours",
    "stress_level",
    "caffeine_intake",
    "temperature_feel",
    "noise_level",
]

# --- What to do about it ------------------------------------------------------

TIPS = {
    "salt_intake": (
        "Try seasoning with herbs, lemon or spices instead of salt, and go easy on stock cubes, sauces, "
        "processed meat and salted snacks."
    ),
    "alcohol_consumed": "Keep some days completely alcohol-free, and keep to a small amount on the days you do drink.",
    "smoked": "Ask your clinic about help to quit. Cutting down is a good start, and every smoke-free day counts.",
    "physical_activity_minutes": (
        "Start with a 10-minute brisk walk after a meal and build towards about 30 minutes on most days."
    ),
    "diet_adherence": (
        "Add a fruit or vegetables to every meal, and swap fried or fatty food for boiled, grilled or steamed."
    ),
    "sleep_hours": (
        "Aim for 7 to 9 hours: keep a regular bedtime, put screens away 30 minutes before bed, and avoid "
        "coffee or tea late in the day."
    ),
    "stress_level": (
        "Try five minutes of slow breathing (in for 4, out for 6), a short walk, or talking things through "
        "with someone you trust."
    ),
    "caffeine_intake": (
        "Keep to one or two cups a day, have none after mid-afternoon, and wait 30 minutes after a cup "
        "before measuring your blood pressure."
    ),
    "medication_taken": (
        "Take it at the same time each day, set a phone reminder, never double up after a missed dose, and "
        "tell your clinician if you keep missing doses."
    ),
    "temperature_feel": (
        "Dress in warm layers (head, hands and feet especially), warm up indoors before measuring, and avoid "
        "stepping straight from a warm bed into the cold."
    ),
    "noise_level": (
        "Use ear protection or noise-cancelling earphones where you can, take quiet breaks away from the noise, "
        "and measure your blood pressure in a quiet room."
    ),
}

# "...on the N days you <RISKY>" versus "...on the M days you <SAFE>".
DESCRIPTIONS = {
    "salt_intake": ("ate a moderate or high amount of salt", "ate little salt"),
    "alcohol_consumed": ("drank alcohol", "didn't drink alcohol"),
    "smoked": ("smoked", "didn't smoke"),
    "physical_activity_minutes": ("were active for under 20 minutes", "were more active"),
    "diet_adherence": ("didn't eat as advised", "ate as advised"),
    "sleep_hours": ("slept under 6 hours", "slept 6 hours or more"),
    "stress_level": ("logged high stress", "logged lower stress"),
    "caffeine_intake": ("had a lot of coffee or tea", "had less coffee or tea"),
    "medication_taken": ("missed your medicine", "took your medicine"),
    "temperature_feel": ("logged cold weather", "logged mild or hot weather"),
    "noise_level": ("had a loud day", "had a quiet or moderate day"),
}

LABELS = {
    "salt_intake": "salt",
    "alcohol_consumed": "alcohol",
    "smoked": "smoking",
    "physical_activity_minutes": "physical activity",
    "diet_adherence": "diet",
    "sleep_hours": "sleep",
    "stress_level": "stress",
    "caffeine_intake": "coffee or tea",
    "medication_taken": "missed medicine",
    "temperature_feel": "cold weather",
    "noise_level": "noise",
}

# --- 2. Reading the log -------------------------------------------------------

REPEAT_DAYS = 2  # risky on this many days in the period => a habit, not a slip


@dataclass
class FieldHistory:
    """Days on which one question was answered, and the days that answer was risky."""

    logged: set[date] = field(default_factory=set)
    risky: set[date] = field(default_factory=set)
    latest_day: date | None = None
    latest_risky: bool = False


def summarize_log(entries) -> dict[str, FieldHistory]:
    """Per logged field, which days were answered and which were risky.

    A day counts as risky if ANY entry that day was. `entries` need only have
    `logged_date` and the nine field attributes (None = not answered).
    """
    history = {name: FieldHistory() for name in RISK_PREDICATES}
    for entry in entries:
        for name, is_risk in RISK_PREDICATES.items():
            answer = getattr(entry, name, None)
            if answer is None:
                continue
            h = history[name]
            risky = bool(is_risk(answer))
            h.logged.add(entry.logged_date)
            if risky:
                h.risky.add(entry.logged_date)
            if h.latest_day is None or entry.logged_date > h.latest_day:
                h.latest_day, h.latest_risky = entry.logged_date, risky
            elif entry.logged_date == h.latest_day:
                h.latest_risky = h.latest_risky or risky
    return history


def flagged_fields(history: dict[str, FieldHistory], window_start: date) -> set[str]:
    """Habits to raise now: risky on the latest answer, or on REPEAT_DAYS+ days since `window_start`."""
    flagged = set()
    for name, h in history.items():
        recent_risky = {d for d in h.risky if d >= window_start}
        latest_in_window = h.latest_day is not None and h.latest_day >= window_start
        if (latest_in_window and h.latest_risky) or len(recent_risky) >= REPEAT_DAYS:
            flagged.add(name)
    return flagged


# --- 3. The patient's own pattern --------------------------------------------

PATTERN_MIN_DAYS = 2  # days on EACH side before comparing anything
PATTERN_MIN_DIFF_MMHG = 5  # smaller gaps are within day-to-day noise
MAX_PATTERNS = 2


@dataclass(frozen=True)
class Pattern:
    field: str
    risky_days: int
    safe_days: int
    avg_risky: float
    avg_safe: float
    risky_dates: frozenset = frozenset()
    safe_dates: frozenset = frozenset()

    @property
    def difference(self) -> float:
        return self.avg_risky - self.avg_safe


def personal_patterns(history: dict[str, FieldHistory], daily_systolic: dict[date, float]) -> list[Pattern]:
    """Habits whose risky days had clearly higher readings than the same person's other days."""
    found = []
    for name, h in history.items():
        risky_dates = frozenset(d for d in h.risky if d in daily_systolic)
        safe_dates = frozenset(d for d in (h.logged - h.risky) if d in daily_systolic)
        if len(risky_dates) < PATTERN_MIN_DAYS or len(safe_dates) < PATTERN_MIN_DAYS:
            continue
        risky = [daily_systolic[d] for d in risky_dates]
        safe = [daily_systolic[d] for d in safe_dates]
        pattern = Pattern(
            name, len(risky), len(safe), sum(risky) / len(risky), sum(safe) / len(safe), risky_dates, safe_dates
        )
        if pattern.difference >= PATTERN_MIN_DIFF_MMHG:
            found.append(pattern)
    return sorted(found, key=lambda p: p.difference, reverse=True)


def group_patterns(patterns: list[Pattern]) -> list[list[Pattern]]:
    """Merge patterns that rest on exactly the same days.

    Habits that always happen together (poor sleep AND high salt on the same
    four days) cannot be told apart by this comparison, so they are reported
    as one finding instead of two that each imply sole responsibility.
    """
    groups: dict[tuple, list[Pattern]] = {}
    for p in patterns:
        groups.setdefault((p.risky_dates, p.safe_dates), []).append(p)
    return list(groups.values())[:MAX_PATTERNS]


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def pattern_message(group: list[Pattern]) -> str:
    first = group[0]
    risky_text = _join([DESCRIPTIONS[p.field][0] for p in group])
    safe_text = _join([DESCRIPTIONS[p.field][1] for p in group])
    caveat = (
        "That shows a link in your own readings, not proof of cause."
        if len(group) == 1
        else "These happened on the same days, so your log can't show which one matters most; it is not proof of cause."
    )
    return (
        f"In your own log, on the {first.risky_days} days you {risky_text}, your systolic pressure averaged "
        f"{round(first.avg_risky)} mmHg: {round(first.difference)} mmHg higher than on the {first.safe_days} days "
        f"you {safe_text} ({round(first.avg_safe)} mmHg). {caveat} " + " ".join(TIPS[p.field] for p in group)
    )


# --- How each reading was taken -----------------------------------------------

MEASUREMENT_MIN_READINGS = 2
MEASUREMENT_TIP = (
    "Sit quietly with your back supported and feet flat for 5 minutes, and wait 30 minutes after coffee, tea, "
    "smoking or exercise before you measure. If your readings are only high when taken in a hurry, tell your clinician."
)


def poorly_measured(reading) -> bool:
    """Not rested first, or taken soon after coffee/tea, smoking or exercise."""
    return getattr(reading, "rested_before", None) is False or getattr(reading, "stimulant_before", None) is True


def properly_measured(reading) -> bool:
    return getattr(reading, "rested_before", None) is True and getattr(reading, "stimulant_before", None) is False


def measurement_advice(readings) -> dict | None:
    """Advice when several readings were taken under conditions that inflate them.

    Says so even without comparison data; when there are also properly taken
    readings to compare with, it shows how much higher the hurried ones were.
    """
    readings = list(readings)
    poor = [r for r in readings if poorly_measured(r)]
    if len(poor) < MEASUREMENT_MIN_READINGS:
        return None

    message = (
        f"{len(poor)} of your {len(readings)} readings this period were taken without resting first, or soon "
        f"after coffee, tea, smoking or exercise. Readings taken like that can come out higher than your true pressure."
    )
    source = "rule"
    good = [r for r in readings if properly_measured(r)]
    if len(good) >= PATTERN_MIN_DAYS:
        poor_avg = sum(r.systolic for r in poor) / len(poor)
        good_avg = sum(r.systolic for r in good) / len(good)
        if poor_avg - good_avg >= PATTERN_MIN_DIFF_MMHG:
            message += (
                f" In your own log they averaged {round(poor_avg)} mmHg systolic, {round(poor_avg - good_avg)} mmHg "
                f"higher than the {len(good)} you took properly rested ({round(good_avg)} mmHg)."
            )
            source = "pattern"
    return {"message": f"{message} {MEASUREMENT_TIP}", "source": source, "kind": "measurement"}


def coverage_message(entries, daily_systolic: dict[date, float]) -> str | None:
    """How many more days of logging unlock the patient's own patterns, or None once there are enough."""
    history = summarize_log(entries)
    logged_days = set().union(*(h.logged for h in history.values()))
    paired = len(logged_days & set(daily_systolic))
    needed = 2 * PATTERN_MIN_DAYS
    if paired >= needed:
        return None
    return (
        f"Your habits can be matched against your readings once you have {needed} days with both a reading and a "
        f"lifestyle log, ideally including some easier days and some harder ones. You have {paired} so far: log "
        f"your lifestyle on the days you measure."
    )


# --- Putting it together ------------------------------------------------------


def build_advice(
    entries,
    daily_systolic: dict[date, float],
    window_start: date,
    effects: dict | None,
    limit: int,
    readings=(),
) -> list[dict]:
    """Ordered advice for the habits the patient's log flags, most useful first.

    Each item is {"message", "source"} with source "pattern" (from the
    patient's own readings), "model" (the survey data supports it) or "rule"
    (general clinical guidance). Order: how the readings were taken, own patterns, missed medication, the
    survey-ranked habits (smoking first among them), then the remaining guidance
    rules. Anything beyond `limit` is summarised in one closing line rather than dropped.
    """
    history = summarize_log(entries)
    flagged = flagged_fields(history, window_start)

    advice: list[dict] = []
    covered: set[str] = set()

    # First: if the readings themselves may be inflated, nothing else can be trusted.
    measurement = measurement_advice(readings)
    if measurement:
        advice.append(measurement)

    if not flagged:
        return advice[:limit]

    current = [p for p in personal_patterns(history, daily_systolic) if p.field in flagged]
    for group in group_patterns(current):
        advice.append({"message": pattern_message(group), "source": "pattern"})
        covered.update(p.field for p in group)

    def rule_item(name):
        return {"message": RULE_MESSAGES[name] + " " + TIPS[name] + RULE_PROVENANCE, "source": "rule"}

    if "medication_taken" in flagged and "medication_taken" not in covered:
        advice.append({**rule_item("medication_taken"), "field": "medication_taken"})
        covered.add("medication_taken")

    model_values = {
        feature: (_RISKY_VALUE if _FIELD_OF[feature] in flagged else _HEALTHY_VALUE)[feature] for feature in _FIELD_OF
    }
    ranked_items = [(_FIELD_OF[r["feature"]], r) for r in rank_factors(model_values, effects, limit=len(_FIELD_OF))]
    # Smoking is one of the largest avoidable risks, so it is never the habit that gets cut
    # for space (the survey ranking alone would put it last). Stable sort keeps the rest in order.
    ranked_items.sort(key=lambda item: item[0] != "smoked")
    for name, ranked in ranked_items:
        if name in covered:
            continue
        advice.append(
            {
                "message": GUIDELINE_MESSAGES[ranked["feature"]]
                + " "
                + TIPS[name]
                + (DATA_SUPPORTED_SUFFIX if ranked["data_supported"] else ""),
                "source": "model" if ranked["data_supported"] else "rule",
                "field": name,
            }
        )
        covered.add(name)

    for name in RULE_ORDER:
        if name in flagged and name not in covered:
            advice.append({**rule_item(name), "field": name})
            covered.add(name)

    shown, cut = advice[:limit], advice[limit:]
    if cut:
        # Never drop a logged habit without saying so.
        labels = _join([LABELS[item["field"]] for item in cut if "field" in item])
        shown.append(
            {
                "message": f"Also worth attention from your log: {labels}. Your Lifestyle page lists everything you've logged.",
                "source": "rule",
            }
        )
    for item in shown:
        item.pop("field", None)
    return shown
