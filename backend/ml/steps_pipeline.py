import numpy as np
import pandas as pd
import pyreadstat

# Features the app can supply today (age/sex from the profile, the rest from
# the Lifestyle log).
FEATURE_COLUMNS = [
    "age",
    "sex",
    "smoked",
    "alcohol_consumed",
    "salt_score",
    "activity_minutes",
    "diet_adherence",
]

# Adding body-mass index is the single biggest accuracy gain available
# (see ml/README.md). Use it once the app collects height and weight:
#   python -m ml.train_model --features bmi
BMI_FEATURE_COLUMNS = FEATURE_COLUMNS + ["bmi"]

# STEPS stores "not measured / refused" as 0 or 888.8 in the body measurements.
PLAUSIBLE_RANGES = {
    "height_cm": (120, 220),
    "weight_kg": (25, 250),
    "pulse": (35, 200),
}


def load_raw(path: str):
    df, meta = pyreadstat.read_sav(path)
    return df, meta


def _yes_no(series: pd.Series) -> pd.Series:
    """STEPS convention: 1 = yes, 2 = no. Returns 0/1, NaN preserved."""
    return series.map({1.0: 1, 2.0: 0})


def _salt_score(series: pd.Series) -> pd.Series:

    mapping = {1.0: 3, 2.0: 2, 3.0: 1, 4.0: 1, 5.0: 0}
    return series.map(mapping)


def _activity_minutes_per_day(df: pd.DataFrame) -> pd.Series:

    def block_minutes(does_col, days_col, hours_col, mins_col):
        does = df[does_col].map({1.0: 1, 2.0: 0}).fillna(0)
        days = df[days_col].fillna(0)
        hrs = df[hours_col].fillna(0)
        mins = df[mins_col].fillna(0)
        per_day_minutes = hrs * 60 + mins
        weekly = does * days * per_day_minutes
        return weekly

    weekly_total = (
        block_minutes("P1", "P2", "P3a", "P3b")
        + block_minutes("P7", "P8", "P9a", "P9b")
        + block_minutes("P10", "P11", "P12a", "P12b")
    )
    return (weekly_total / 7.0).clip(upper=240)


def _diet_adherence(df: pd.DataFrame) -> pd.Series:

    fruit_daily = (df["D1"].fillna(0) * df["D2"].fillna(0)) / 7.0
    veg_daily = (df["D3"].fillna(0) * df["D4"].fillna(0)) / 7.0
    total = fruit_daily + veg_daily
    return (total >= 5).astype(int)


def _in_range(series: pd.Series, low: float, high: float) -> pd.Series:
    """NaN for anything outside a physiologically plausible range."""
    return series.where(series.between(low, high))


def _avg_pulse(df: pd.DataFrame) -> pd.Series:
    cols = [df[c] for c in ("M16a", "M16b", "M16c")]
    readings = pd.concat([_in_range(c, *PLAUSIBLE_RANGES["pulse"]) for c in cols], axis=1)
    return readings.mean(axis=1, skipna=True)


def _avg_bp(df: pd.DataFrame):

    sys_cols = ["M5a", "M6a"]
    dia_cols = ["M5b", "M6b"]
    systolic = df[sys_cols].mean(axis=1, skipna=True)
    diastolic = df[dia_cols].mean(axis=1, skipna=True)
    systolic = systolic.fillna(df["M4a"])
    diastolic = diastolic.fillna(df["M4b"])
    return systolic, diastolic


def classify_bp(systolic, diastolic):
    """Mirrors HyperSync's app/core/bp_classification.py thresholds exactly."""
    if pd.isna(systolic) or pd.isna(diastolic):
        return np.nan
    if systolic < 90 or diastolic < 60:
        return "low"
    if systolic >= 150 or diastolic >= 95:
        return "high"
    if systolic >= 135 or diastolic >= 85:
        return "elevated"
    return "controlled"


def build_dataset(path: str) -> pd.DataFrame:
    df, meta = load_raw(path)

    out = pd.DataFrame()
    out["age"] = df["age"]
    out["sex"] = df["sex"].map({"Men": 1, "Women": 0})
    out["smoked"] = _yes_no(df["T1"])
    out["alcohol_consumed"] = _yes_no(df["A5"]).fillna(0)  # NaN => didn't reach this question => no recent use
    out["salt_score"] = _salt_score(df["D5"])
    out["activity_minutes"] = _activity_minutes_per_day(df)
    out["diet_adherence"] = _diet_adherence(df)

    diagnosed = _yes_no(df["H2a"]) == 1
    med_taken = _yes_no(df["H3"])
    out["medication_taken"] = np.where(diagnosed, med_taken, np.nan)
    # NOTE: medication_taken is only answered by the ~11% of respondents
    # previously diagnosed with hypertension, so it is NOT used as a
    # trained model feature (see train_model.py) — it would either gut
    # the dataset via dropna or leak diagnosis status into the model.
    # It is retained here for descriptive purposes only and handled as a
    # plain rule in the app, same treatment as sleep/caffeine/stress.

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

    before = len(out)
    out = out.dropna(subset=["age", "sex", "bp_status", "systolic", "diastolic"])
    out = out[out["age"].between(18, 100)]
    # drop physiologically implausible BP values (device/entry errors) —
    # same bounds HyperSync's own BPReadingCreate schema enforces at intake
    out = out[out["systolic"].between(60, 260) & out["diastolic"].between(30, 180)]
    after = len(out)
    print(
        f"Dropped {before - after} rows with missing core fields, out-of-range age, or implausible BP; {after} remain."
    )

    return out.reset_index(drop=True)


if __name__ == "__main__":
    data = build_dataset("data/2015_STEPS_Data.sav")
    print(data.shape)
    print(data["bp_status"].value_counts())
    data.to_csv("ml/artifacts/steps_clean.csv", index=False)
