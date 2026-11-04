"""Pure helpers (no database, no ML imports) that decide WHICH lifestyle
factors to talk about and HOW to word them.

Why this exists
---------------
The first version ranked factors by the random forest's built-in feature
importance. That measure is inflated for continuous variables: it put
physical activity second only to age, yet on held-out data shuffling activity
barely changed accuracy (see ml/README.md). Ranking by it showed patients an
ordering the data does not support.

Now a factor is only credited to the survey data when its adjusted effect has
a confidence interval that excludes "no effect". Everything else is still
mentioned when the patient's own log points that way, but it is worded as
general clinical guidance and ordered by guideline priority.
"""

# Lifestyle features the app can generate advice for. age/sex are never
# surfaced: a patient cannot act on them.
MODIFIABLE_FEATURES = ["salt_score", "alcohol_consumed", "activity_minutes", "diet_adherence", "smoked"]

# Order used when the data cannot separate factors (hypertension guidelines
# put sodium and alcohol reduction ahead of the rest).
GUIDELINE_PRIORITY = MODIFIABLE_FEATURES

# +1: a higher value raises BP odds, -1: a higher value lowers them.
HARMFUL_DIRECTION = {
    "salt_score": +1,
    "alcohol_consumed": +1,
    "smoked": +1,
    "activity_minutes": -1,
    "diet_adherence": -1,
}

GUIDELINE_MESSAGES = {
    "salt_score": "Your logged salt intake has been high. Cutting back on added salt and salty processed foods is one of the most effective lifestyle changes for lowering blood pressure.",
    "alcohol_consumed": "You've logged alcohol consumption recently. Drinking less alcohol helps lower blood pressure.",
    "activity_minutes": "Your logged physical activity has been low. Regular moderate activity, such as brisk walking on most days, helps lower blood pressure.",
    "diet_adherence": "You've logged not meeting the recommended fruit and vegetable intake. Eating more fruit and vegetables helps lower blood pressure.",
    "smoked": "You've logged smoking recently. Smoking raises cardiovascular risk and temporarily raises blood pressure after each cigarette. Consider support resources for quitting.",
}

DATA_SUPPORTED_SUFFIX = " This also showed up clearly in the national survey data this system is built on."


def is_risk_direction(feature: str, value) -> bool:
    """True when the patient's own logged value points the unhealthy way."""
    if feature == "activity_minutes":
        return value < 20
    if feature == "salt_score":
        return value >= 2
    if feature == "alcohol_consumed":
        return bool(value)
    if feature == "smoked":
        return bool(value)
    if feature == "diet_adherence":
        return not bool(value)
    return False


def is_data_supported(feature: str, effect: dict | None) -> bool:
    """True when the survey-derived effect's 95% CI excludes 'no effect' in
    the harmful direction. `effect` holds odds_ratio / ci_low / ci_high."""
    if not effect:
        return False
    direction = HARMFUL_DIRECTION[feature]
    if direction > 0:
        return effect["ci_low"] > 1.0
    return effect["ci_high"] < 1.0


def rank_factors(values: dict, effects: dict | None, limit: int = 3) -> list[dict]:
    """Pick up to `limit` factors to mention.

    Only factors where the patient's own value points the unhealthy way are
    considered. Data-supported factors come first; ties and the rest follow
    guideline priority. Each item: {"feature", "message", "data_supported"}.
    """
    effects = effects or {}
    candidates = [f for f in GUIDELINE_PRIORITY if f in values and is_risk_direction(f, values[f])]
    flagged = [(f, is_data_supported(f, effects.get(f))) for f in candidates]
    flagged.sort(key=lambda item: not item[1])  # stable: keeps guideline order within each group
    return [
        {
            "feature": f,
            "data_supported": supported,
            "message": GUIDELINE_MESSAGES[f] + (DATA_SUPPORTED_SUFFIX if supported else ""),
        }
        for f, supported in flagged[:limit]
    ]
