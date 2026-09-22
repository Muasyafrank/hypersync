"""
Kenya STEPS 2015 -> HyperSync feature pipeline.

DATA SOURCE
-----------
Kenya National Bureau of Statistics, Ministry of Health (Kenya), World
Health Organization. Kenya STEPwise Survey for Non-Communicable Disease
Risk Factors, 2015. n=4500 respondents aged 18-69, nationally
representative, three-stage cluster sample (NASSEP V frame).

WHAT THIS SURVEY DOES AND DOES NOT COVER
-----------------------------------------
Covered directly: blood pressure (3 measured readings), smoking, alcohol
use, salt-related behaviour, physical activity (work/transport/sport),
fruit & vegetable intake, and — for respondents previously diagnosed with
hypertension — antihypertensive medication adherence in the last two
weeks.

NOT covered: sleep duration, caffeine intake, perceived stress. These are
HyperSync app features with no equivalent STEPS question. They are
therefore excluded from the trained model entirely (rather than imputed
with fabricated values) and handled separately in the application as
plainly-labelled threshold rules — see app/core/ml_recommendation_engine.py.

This is a cross-sectional survey: it captures association between
lifestyle and blood pressure at a single point in time, not causation or
within-person change over time. Framed in the recommendation output as
"associated with" rather than "causes".
"""
import numpy as np
import pandas as pd
import pyreadstat

FEATURE_COLUMNS = [
    "age", "sex", "smoked", "alcohol_consumed", "salt_score",
    "activity_minutes", "diet_adherence",
]
# medication_taken is intentionally excluded from FEATURE_COLUMNS — see
# note in build_dataset() below.


def load_raw(path: str):
    df, meta = pyreadstat.read_sav(path)
    return df, meta


def _yes_no(series: pd.Series) -> pd.Series:
    """STEPS convention: 1 = yes, 2 = no. Returns 0/1, NaN preserved."""
    return series.map({1.0: 1, 2.0: 0})


def _salt_score(series: pd.Series) -> pd.Series:
    """
    D5: frequency of adding salt to food.
    1 every meal .. 5 never, 77 don't know.
    Recoded to an ascending 0-3 salt-exposure score (0=never, 3=every meal).
    """
    mapping = {1.0: 3, 2.0: 2, 3.0: 1, 4.0: 1, 5.0: 0}
    return series.map(mapping)


def _activity_minutes_per_day(df: pd.DataFrame) -> pd.Series:
    """
    Combines GPAQ-style work, transport, and sport activity blocks into an
    average minutes-per-day figure, matching the unit HyperSync's
    physical_activity_minutes field already uses.
    """
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
    """
    WHO 5-a-day threshold: combined fruit + vegetable servings/day >= 5,
    approximated as (days/week consuming * servings when consumed) / 7.
    """
    fruit_daily = (df["D1"].fillna(0) * df["D2"].fillna(0)) / 7.0
    veg_daily = (df["D3"].fillna(0) * df["D4"].fillna(0)) / 7.0
    total = fruit_daily + veg_daily
    return (total >= 5).astype(int)


def _avg_bp(df: pd.DataFrame):
    """
    WHO STEPS convention: average the 2nd and 3rd readings (1st is a
    settling reading). Falls back to whatever readings are present.
    """
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

    systolic, diastolic = _avg_bp(df)
    out["systolic"] = systolic
    out["diastolic"] = diastolic
    out["bp_status"] = [classify_bp(s, d) for s, d in zip(systolic, diastolic)]

    before = len(out)
    out = out.dropna(subset=["age", "sex", "bp_status", "systolic", "diastolic"])
    out = out[out["age"].between(18, 100)]
    # drop physiologically implausible BP values (device/entry errors) —
    # same bounds HyperSync's own BPReadingCreate schema enforces at intake
    out = out[out["systolic"].between(60, 260) & out["diastolic"].between(30, 180)]
    after = len(out)
    print(f"Dropped {before - after} rows with missing core fields, out-of-range age, or implausible BP; {after} remain.")

    return out.reset_index(drop=True)


if __name__ == "__main__":
    data = build_dataset("data/2015_STEPS_Data.sav")
    print(data.shape)
    print(data["bp_status"].value_counts())
    data.to_csv("ml/artifacts/steps_clean.csv", index=False)
