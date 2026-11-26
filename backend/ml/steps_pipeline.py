"""Reproducible feature construction for the Kenya STEPS 2015 survey.

The cleaning rules in this module are deliberately explicit about STEPS skip
codes and missing values. In particular, ``77`` means "not recorded" in the
physical-activity and diet questions; treating it as zero would turn missing
answers into apparently low-risk observations.

The survey design columns (``wstep2``, ``psu`` and ``stratum``) are retained
so that model fitting, the locked split and the PSU bootstrap all use the
same design information.
"""

import numpy as np
import pandas as pd
import pyreadstat

from app.core.bp_classification import (
    ELEVATED_DIASTOLIC,
    ELEVATED_SYSTOLIC,
    HIGH_DIASTOLIC,
    HIGH_SYSTOLIC,
    LOW_DIASTOLIC,
    LOW_SYSTOLIC,
    VERY_HIGH_DIASTOLIC,
    VERY_HIGH_SYSTOLIC,
)
from ml.model_contract import (
    MODEL_ACTIVITY_MAX_MINUTES,
    MODEL_AGE_RANGE,
    RUNTIME_MODEL_FEATURES,
    RUNTIME_MODEL_MISSING_FEATURES,
)

# Features the app can supply today (age/sex from the profile, the rest from
# the Lifestyle log). Missingness indicators are model inputs, but they are not
# treated as independent clinical factors.
FEATURE_COLUMNS = list(RUNTIME_MODEL_FEATURES)
MISSING_FEATURE_COLUMNS = list(RUNTIME_MODEL_MISSING_FEATURES)
MODEL_INPUT_COLUMNS = FEATURE_COLUMNS + MISSING_FEATURE_COLUMNS

# An experimental BMI feature set is available for maintenance work once the
# app collects height and weight. It is not part of the published runtime
# contract:
#   python -m ml.train_model --features bmi
BMI_FEATURE_COLUMNS = FEATURE_COLUMNS + ["bmi"]

# STEPS stores "not measured / refused" as 0 or 888.8 in the body measurements.
PLAUSIBLE_RANGES = {
    "height_cm": (120, 220),
    "weight_kg": (25, 250),
    "pulse": (35, 200),
}

# In the STEPS diet and physical-activity questions, 77 is a missing-value
# code. It must never be interpreted as a real quantity.
MISSING_SENTINEL = 77


def load_raw(path: str):
    df, meta = pyreadstat.read_sav(path)
    return df, meta


def _yes_no(series: pd.Series) -> pd.Series:
    """STEPS convention: 1 = yes, 2 = no. Invalid codes become NaN."""
    return series.map({1.0: 1, 2.0: 0})


def _alcohol_consumed(df: pd.DataFrame) -> pd.Series:
    """Past-month alcohol use with explicit structural-skip handling."""
    alcohol = _yes_no(df["A5"])
    structural_no_recent_alcohol = df["A2"].eq(2.0) | df["A1"].eq(2.0)
    return alcohol.mask(alcohol.isna() & structural_no_recent_alcohol, 0)


def _salt_score(series: pd.Series) -> pd.Series:
    """Map the STEPS salt-frequency codes to the app's 0-3 score."""
    mapping = {1.0: 3, 2.0: 2, 3.0: 1, 4.0: 1, 5.0: 0}
    return series.map(mapping)


def _without_missing_sentinel(series: pd.Series) -> pd.Series:
    return series.mask(series.eq(MISSING_SENTINEL))


def _activity_minutes_per_day(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return daily activity minutes and an explicit missingness indicator.

    The feature includes all five STEPS activity domains: vigorous and
    moderate work, walking/cycling for transport, and vigorous and moderate
    sport. A STEPS activity block is complete when the respondent says they do
    the activity and supplies valid days, hours and minutes. A missing block
    makes the total activity value missing rather than silently lower than
    observed. The final value is capped to the published application/training
    contract.
    """
    weekly_total = pd.Series(0.0, index=df.index)
    missing = pd.Series(False, index=df.index)

    for does_col, days_col, hours_col, mins_col in (
        ("P1", "P2", "P3a", "P3b"),  # vigorous-intensity work
        ("P4", "P5", "P6a", "P6b"),  # moderate-intensity work
        ("P7", "P8", "P9a", "P9b"),  # walking or cycling for transport
        ("P10", "P11", "P12a", "P12b"),  # vigorous-intensity sport
        ("P13", "P14", "P15a", "P15b"),  # moderate-intensity sport
    ):
        does_raw = df[does_col]
        does = does_raw.map({1.0: 1, 2.0: 0})
        days = _without_missing_sentinel(df[days_col])
        hours = _without_missing_sentinel(df[hours_col])
        minutes = _without_missing_sentinel(df[mins_col])

        # Code 0 and blank are invalid "do you do this?" responses.
        invalid_block = does.isna()
        incomplete_active_block = does.eq(1) & (days.isna() | hours.isna() | minutes.isna())
        missing |= invalid_block | incomplete_active_block

        weekly_total += does.fillna(0) * days.fillna(0) * (hours.fillna(0) * 60 + minutes.fillna(0))

    value = (weekly_total / 7.0).clip(lower=0, upper=MODEL_ACTIVITY_MAX_MINUTES)
    value[missing] = np.nan
    return value, missing


def _diet_adherence(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return whether the respondent met 5 daily fruit/vegetable servings.

    A blank amount after ``days = 0`` is a structural skip, not missing data.
    A blank amount after one or more days is missing and invalidates the diet
    feature. Code 77 is always invalid.
    """
    d1_raw, d2_raw = df["D1"], df["D2"]
    d3_raw, d4_raw = df["D3"], df["D4"]
    d1 = _without_missing_sentinel(d1_raw)
    d2 = _without_missing_sentinel(d2_raw)
    d3 = _without_missing_sentinel(d3_raw)
    d4 = _without_missing_sentinel(d4_raw)

    fruit_missing = d1.isna() | d2.isna() & (d1.gt(0) | d2_raw.eq(MISSING_SENTINEL))
    vegetable_missing = d3.isna() | d4.isna() & (d3.gt(0) | d4_raw.eq(MISSING_SENTINEL))
    missing = fruit_missing | vegetable_missing

    fruit_daily = (d1.fillna(0) * d2.fillna(0)) / 7.0
    vegetable_daily = (d3.fillna(0) * d4.fillna(0)) / 7.0
    value = ((fruit_daily + vegetable_daily) >= 5).astype(float)
    value[missing] = np.nan
    return value, missing


def _in_range(series: pd.Series, low: float, high: float) -> pd.Series:
    """NaN for anything outside a physiologically plausible range."""
    return series.where(series.between(low, high))


def _avg_pulse(df: pd.DataFrame) -> pd.Series:
    cols = [df[c] for c in ("M16a", "M16b", "M16c")]
    readings = pd.concat([_in_range(c, *PLAUSIBLE_RANGES["pulse"]) for c in cols], axis=1)
    return readings.mean(axis=1, skipna=True)


def _avg_bp(df: pd.DataFrame):
    """Mean of the second and third BP readings, with both required.

    The primary target deliberately does not fall back to the first reading.
    Mixing measurement protocols would change the outcome definition for a
    small number of respondents and make the target harder to audit.
    """
    sys_cols = ["M5a", "M6a"]
    dia_cols = ["M5b", "M6b"]
    systolic = df[sys_cols].mean(axis=1).where(df[sys_cols].notna().all(axis=1))
    diastolic = df[dia_cols].mean(axis=1).where(df[dia_cols].notna().all(axis=1))
    return systolic, diastolic


def classify_bp(systolic, diastolic):
    """Mirror HyperSync's app/core/bp_classification.py thresholds exactly."""
    if pd.isna(systolic) or pd.isna(diastolic):
        return np.nan
    if systolic >= VERY_HIGH_SYSTOLIC or diastolic >= VERY_HIGH_DIASTOLIC:
        return "high"
    if systolic < LOW_SYSTOLIC or diastolic < LOW_DIASTOLIC:
        return "low"
    if systolic >= HIGH_SYSTOLIC or diastolic >= HIGH_DIASTOLIC:
        return "high"
    if systolic >= ELEVATED_SYSTOLIC or diastolic >= ELEVATED_DIASTOLIC:
        return "elevated"
    return "controlled"


def build_dataset(path: str) -> pd.DataFrame:
    """Load and clean the STEPS file without silently imputing answers."""
    df, _meta = load_raw(path)

    out = pd.DataFrame(index=df.index)
    out["respondent_id"] = df["PID"]
    out["valid"] = df["valid"]
    out["age"] = df["age"]
    out["sex"] = df["sex"].map({"Men": 1, "Women": 0})
    out["smoked"] = _yes_no(df["T1"])

    # A5 asks about alcohol in the past month. It is structurally skipped when
    # A2 says there was no alcohol in the past year (and when A1 says the
    # respondent has never consumed alcohol). Those respondents cannot have
    # consumed alcohol in the past month, so the value is zero. Other blanks
    # and explicit invalid codes remain missing.
    out["alcohol_consumed"] = _alcohol_consumed(df)

    out["salt_score"] = _salt_score(df["D5"])
    out["activity_minutes"], activity_missing = _activity_minutes_per_day(df)
    out["diet_adherence"], diet_missing = _diet_adherence(df)

    out["age_missing"] = out["age"].isna().astype(int)
    out["sex_missing"] = out["sex"].isna().astype(int)
    out["smoked_missing"] = out["smoked"].isna().astype(int)
    out["alcohol_consumed_missing"] = out["alcohol_consumed"].isna().astype(int)
    out["salt_score_missing"] = out["salt_score"].isna().astype(int)
    out["activity_minutes_missing"] = activity_missing.astype(int)
    out["diet_adherence_missing"] = diet_missing.astype(int)

    diagnosed = _yes_no(df["H2a"]) == 1
    med_taken = _yes_no(df["H3"])
    out["medication_taken"] = np.where(diagnosed, med_taken, np.nan)
    # NOTE: medication_taken is only answered by the ~11% of respondents
    # previously diagnosed with hypertension, so it is NOT used as a trained
    # model feature. It is retained here for descriptive purposes only.

    # Body measurements, kept out of FEATURE_COLUMNS until the app collects them.
    height = _in_range(df["M11"], *PLAUSIBLE_RANGES["height_cm"])
    weight = _in_range(df["M12"], *PLAUSIBLE_RANGES["weight_kg"])
    out["bmi"] = _in_range(weight / (height / 100) ** 2, 12, 60)
    out["pulse"] = _avg_pulse(df)
    # Pregnancy changes both BP and weight; the training script excludes it.
    out["pregnant"] = df["M8"].map({1.0: 1, 2.0: 0})

    systolic, diastolic = _avg_bp(df)
    out["systolic"] = systolic
    out["diastolic"] = diastolic
    out["bp_status"] = [classify_bp(s, d) for s, d in zip(systolic, diastolic, strict=True)]
    # Locked target sensitivity: the official report also describes the third
    # reading alone. It is not used to train the primary model.
    out["systolic_third"] = df["M6a"]
    out["diastolic_third"] = df["M6b"]
    out["bp_status_third"] = [classify_bp(s, d) for s, d in zip(df["M6a"], df["M6b"], strict=True)]

    # Retain the survey design used for weighting, grouped splitting and the
    # PSU bootstrap. wstep2 is the measurement weight for this target.
    out["wstep2"] = df["wstep2"]
    out["psu"] = df["psu"]
    out["stratum"] = df["stratum"]

    before = len(out)
    raw_rows = len(out)
    raw_zero_weight_rows = int(out["wstep2"].eq(0).sum())
    out = out.dropna(subset=["age", "sex", "bp_status", "systolic", "diastolic"])
    out = out[out["valid"].eq(1)]
    out = out[out["age"].between(*MODEL_AGE_RANGE)]
    # Drop physiologically implausible BP values (device/entry errors) — the
    # same bounds HyperSync's BPReadingCreate schema enforces at intake.
    out = out[out["systolic"].between(60, 260) & out["diastolic"].between(30, 180)]
    after = len(out)
    out.attrs["exclusion_counts"] = {
        "raw_rows": raw_rows,
        "raw_zero_weight_rows": raw_zero_weight_rows,
        "rows_after_core_age_bp_filters": after,
    }
    print(
        f"Dropped {before - after} rows with missing core fields, out-of-range age, or implausible BP; {after} remain."
    )

    return out.reset_index(drop=True)


if __name__ == "__main__":
    data = build_dataset("data/2015_STEPS_Data.sav")
    print(data.shape)
    print(data["bp_status"].value_counts())
    data.to_csv("ml/artifacts/steps_clean.csv", index=False)
