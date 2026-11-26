"""Tests for the STEPS cleaning rules and the locked survey-model build."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from ml.model_contract import (
    RUNTIME_MODEL_BOOTSTRAP_REPLICATES,
    RUNTIME_MODEL_BUILD_PLATFORM,
    RUNTIME_MODEL_BUILD_PYTHON,
    RUNTIME_MODEL_RAW_SHA256,
    RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
    RUNTIME_MODEL_SPLIT_SHA256,
    RUNTIME_MODEL_TRAINING_DATA_SHA256,
)
from ml.steps_pipeline import (
    MISSING_SENTINEL,
    _activity_minutes_per_day,
    _alcohol_consumed,
    _avg_bp,
    _diet_adherence,
    _salt_score,
    _yes_no,
    classify_bp,
)
from ml.train_model import (
    SEED,
    SPLIT_SEED,
    _at_risk_coefficients,
    _calibration_points,
    _validate_build_environment,
    _weighted_median,
    _weighted_mode,
    apply_defaults,
    create_split_assignment,
    training_defaults,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = BACKEND_ROOT / "data" / "2015_STEPS_Data.sav"
SPLIT_LOCK_PATH = BACKEND_ROOT / "ml" / "artifacts" / "split_assignments.csv"
REQUIREMENTS_LOCK_PATH = BACKEND_ROOT / "ml" / "requirements-lock.txt"
METRICS_PATH = BACKEND_ROOT / "ml" / "artifacts" / "metrics.json"


def test_yes_no_keeps_invalid_codes_missing():
    result = _yes_no(pd.Series([1.0, 2.0, 77.0, np.nan]))
    assert result.tolist()[:2] == [1, 0]
    assert result.isna().tolist() == [False, False, True, True]


def test_alcohol_blank_is_zero_only_for_a_structural_skip():
    frame = pd.DataFrame(
        {
            "A1": [1.0, 1.0, 1.0, 2.0],
            "A2": [1.0, 2.0, 1.0, 2.0],
            "A5": [1.0, np.nan, np.nan, np.nan],
        }
    )

    result = _alcohol_consumed(frame)

    assert result.iloc[0] == 1
    assert result.iloc[1] == 0
    assert np.isnan(result.iloc[2])
    assert result.iloc[3] == 0


def test_salt_frequency_is_mapped_to_the_application_scale():
    result = _salt_score(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, MISSING_SENTINEL]))
    assert result.tolist()[:5] == [3.0, 2.0, 1.0, 1.0, 0.0]
    assert np.isnan(result.iloc[5])


def test_inactive_activity_days_are_structural_skips_not_zero_activity():
    frame = pd.DataFrame(
        {
            "P1": [2.0],
            "P2": [0.0],
            "P3a": [np.nan],
            "P3b": [np.nan],
            "P4": [2.0],
            "P5": [0.0],
            "P6a": [np.nan],
            "P6b": [np.nan],
            "P7": [1.0],
            "P8": [3.0],
            "P9a": [1.0],
            "P9b": [0.0],
            "P10": [2.0],
            "P11": [0.0],
            "P12a": [np.nan],
            "P12b": [np.nan],
            "P13": [2.0],
            "P14": [0.0],
            "P15a": [np.nan],
            "P15b": [np.nan],
        }
    )

    value, missing = _activity_minutes_per_day(frame)

    assert not bool(missing.iloc[0])
    assert value.iloc[0] == pytest.approx(180 / 7)


def test_moderate_work_and_sport_are_included_in_daily_activity():
    frame = pd.DataFrame(
        {
            "P1": [2.0],
            "P2": [0.0],
            "P3a": [np.nan],
            "P3b": [np.nan],
            "P4": [1.0],
            "P5": [7.0],
            "P6a": [1.0],
            "P6b": [0.0],
            "P7": [2.0],
            "P8": [0.0],
            "P9a": [np.nan],
            "P9b": [np.nan],
            "P10": [2.0],
            "P11": [0.0],
            "P12a": [np.nan],
            "P12b": [np.nan],
            "P13": [1.0],
            "P14": [7.0],
            "P15a": [1.0],
            "P15b": [0.0],
        }
    )

    value, missing = _activity_minutes_per_day(frame)

    assert not bool(missing.iloc[0])
    assert value.iloc[0] == pytest.approx(120)


def test_an_invalid_activity_participation_code_is_missing_not_zero():
    frame = pd.DataFrame(
        {
            "P1": [0.0],
            "P2": [0.0],
            "P3a": [np.nan],
            "P3b": [np.nan],
            "P4": [2.0],
            "P5": [0.0],
            "P6a": [np.nan],
            "P6b": [np.nan],
            "P7": [2.0],
            "P8": [0.0],
            "P9a": [np.nan],
            "P9b": [np.nan],
            "P10": [2.0],
            "P11": [0.0],
            "P12a": [np.nan],
            "P12b": [np.nan],
            "P13": [2.0],
            "P14": [0.0],
            "P15a": [np.nan],
            "P15b": [np.nan],
        }
    )

    value, missing = _activity_minutes_per_day(frame)

    assert bool(missing.iloc[0])
    assert np.isnan(value.iloc[0])


def test_an_incomplete_active_activity_block_is_missing_not_zero():
    frame = pd.DataFrame(
        {
            "P1": [2.0],
            "P2": [0.0],
            "P3a": [np.nan],
            "P3b": [np.nan],
            "P4": [2.0],
            "P5": [0.0],
            "P6a": [np.nan],
            "P6b": [np.nan],
            "P7": [1.0],
            "P8": [float(MISSING_SENTINEL)],
            "P9a": [np.nan],
            "P9b": [np.nan],
            "P10": [2.0],
            "P11": [0.0],
            "P12a": [np.nan],
            "P12b": [np.nan],
            "P13": [2.0],
            "P14": [0.0],
            "P15a": [np.nan],
            "P15b": [np.nan],
        }
    )

    value, missing = _activity_minutes_per_day(frame)

    assert bool(missing.iloc[0])
    assert np.isnan(value.iloc[0])


def test_diet_structural_skip_is_separate_from_a_missing_amount():
    frame = pd.DataFrame(
        {
            "D1": [0.0],
            "D2": [np.nan],
            "D3": [3.0],
            "D4": [2.0],
        }
    )

    value, missing = _diet_adherence(frame)

    assert not bool(missing.iloc[0])
    assert value.iloc[0] == 0.0


def test_a_sentinel_amount_invalidates_the_diet_feature():
    frame = pd.DataFrame(
        {
            "D1": [3.0],
            "D2": [2.0],
            "D3": [3.0],
            "D4": [float(MISSING_SENTINEL)],
        }
    )

    value, missing = _diet_adherence(frame)

    assert bool(missing.iloc[0])
    assert np.isnan(value.iloc[0])


def test_the_primary_bp_target_requires_both_the_second_and_third_reading():
    frame = pd.DataFrame(
        {
            "M5a": [120.0, 120.0, np.nan],
            "M5b": [80.0, 80.0, 80.0],
            "M6a": [130.0, np.nan, 130.0],
            "M6b": [85.0, 85.0, 85.0],
        }
    )

    systolic, diastolic = _avg_bp(frame)

    assert systolic.iloc[0] == 125.0
    assert diastolic.iloc[0] == 82.5
    assert np.isnan(systolic.iloc[1])
    assert diastolic.iloc[1] == 82.5  # the respondent is still excluded because systolic is missing
    assert np.isnan(systolic.iloc[2])
    assert diastolic.iloc[2] == 82.5  # the respondent is still excluded because systolic is missing


@pytest.mark.parametrize(
    ("systolic", "diastolic", "expected"),
    [
        (89, 80, "low"),
        (100, 59, "low"),
        (150, 70, "high"),
        (120, 90, "high"),
        (185, 50, "high"),
        (160, 55, "low"),
        (135, 70, "elevated"),
        (120, 85, "elevated"),
        (120, 80, "controlled"),
    ],
)
def test_survey_target_boundaries_match_the_application(systolic, diastolic, expected):
    assert classify_bp(systolic, diastolic) == expected


def test_weighted_defaults_use_the_training_population():
    frame = pd.DataFrame(
        {
            "wstep2": [1.0, 1.0, 10.0, 1.0],
            "age": [20.0, 40.0, 60.0, 80.0],
            "smoked": [1.0, 0.0, 0.0, 0.0],
            "activity_minutes": [10.0, 20.0, 30.0, 40.0],
        }
    )

    defaults = training_defaults(frame, ["age", "smoked", "activity_minutes"])

    assert defaults["age"] == 60.0
    assert defaults["smoked"] == 0.0
    assert defaults["activity_minutes"] == 30.0


def test_weighted_mode_and_median_are_deterministic_for_ties():
    values = pd.Series([0.0, 1.0])
    weights = pd.Series([5.0, 5.0])
    assert _weighted_mode(values, weights) == 0.0

    values = pd.Series([10.0, 20.0, 30.0])
    weights = pd.Series([1.0, 1.0, 1.0])
    assert _weighted_median(values, weights) == 20.0


def test_applying_defaults_does_not_erase_explicit_missingness_flags():
    frame = pd.DataFrame({"activity_minutes": [np.nan], "activity_minutes_missing": [1]})
    filled = apply_defaults(frame, {"activity_minutes": 42.0})
    assert filled.loc[0, "activity_minutes"] == 42.0
    assert filled.loc[0, "activity_minutes_missing"] == 1


def test_expected_calibration_error_is_on_the_probability_scale():
    y = np.asarray([0, 1, 1, 0])
    probability = np.asarray([0.1, 0.9, 0.8, 0.2])
    weights = np.ones(4)

    points, ece = _calibration_points(y, probability, weights, edges=[0.0, 0.5, 1.0])

    assert 0 <= ece <= 1
    assert ece == pytest.approx(0.15)
    assert [point["n"] for point in points] == [2, 2]


def test_the_frozen_calibration_series_keeps_every_bin():
    y = np.asarray([0, 1, 1, 0])
    probability = np.asarray([0.1, 0.9, 0.8, 0.2])
    weights = np.ones(4)

    points, ece = _calibration_points(y, probability, weights, edges=[0.0, 0.5, 0.75, 1.0])

    assert len(points) == 3
    assert [point["n"] for point in points] == [2, 0, 2]
    assert points[1]["mean_predicted"] is None
    assert points[1]["observed"] is None
    assert ece == pytest.approx(0.15)


def test_at_risk_coefficients_use_one_orientation_for_string_and_numeric_labels():
    string_model = SimpleNamespace(classes_=["at_risk", "not_at_risk"], coef_=[[1.0, -2.0]])
    numeric_model = SimpleNamespace(classes_=[0, 1], coef_=[[3.0, -4.0]])

    assert _at_risk_coefficients(string_model, "at_risk").tolist() == [-1.0, 2.0]
    assert _at_risk_coefficients(numeric_model, 1).tolist() == [3.0, -4.0]


def test_the_psu_split_is_deterministic_and_balanced_within_each_stratum():
    rows = []
    for stratum in (1, 2):
        for psu in range(stratum * 100, stratum * 100 + 10):
            rows.append({"psu": psu, "stratum": stratum})
    frame = pd.DataFrame(rows)

    first = create_split_assignment(frame)
    second = create_split_assignment(frame)

    assert first.equals(second)
    assert not first["psu"].duplicated().any()
    assert set(first["split"]) == {"train", "validation", "test"}
    for _stratum, part in first.groupby("stratum"):
        assert (part["split"] == "train").sum() == 6
        assert (part["split"] == "validation").sum() == 2
        assert (part["split"] == "test").sum() == 2


def test_the_reproducible_build_requires_the_published_hash_seed(monkeypatch):
    monkeypatch.setenv("PYTHONHASHSEED", "1")

    with pytest.raises(RuntimeError, match="PYTHONHASHSEED=0"):
        _validate_build_environment()


def test_the_committed_split_lock_has_the_published_hash_and_counts():
    digest = hashlib.sha256(SPLIT_LOCK_PATH.read_bytes()).hexdigest()
    assert digest == RUNTIME_MODEL_SPLIT_SHA256

    lock = pd.read_csv(SPLIT_LOCK_PATH)
    assert list(lock.columns) == ["psu", "stratum", "split"]
    assert not lock["psu"].duplicated().any()
    assert lock["split"].value_counts().to_dict() == {"train": 120, "validation": 40, "test": 40}


def test_the_build_seeds_and_published_hashes_are_fixed():
    assert SEED == 20261125
    assert SPLIT_SEED == 20261125
    assert RUNTIME_MODEL_BOOTSTRAP_REPLICATES == 200
    assert RUNTIME_MODEL_BUILD_PYTHON == "3.13.14"
    assert RUNTIME_MODEL_BUILD_PLATFORM == "linux"
    assert len(RUNTIME_MODEL_RAW_SHA256) == 64
    assert len(RUNTIME_MODEL_SPLIT_SHA256) == 64
    assert len(RUNTIME_MODEL_TRAINING_DATA_SHA256) == 64
    assert hashlib.sha256(REQUIREMENTS_LOCK_PATH.read_bytes()).hexdigest() == (RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256)


@pytest.mark.skipif(not RAW_DATA_PATH.exists(), reason="the raw STEPS survey file is not committed")
def test_the_raw_survey_file_has_the_published_hash():
    assert hashlib.sha256(RAW_DATA_PATH.read_bytes()).hexdigest() == RUNTIME_MODEL_RAW_SHA256


def test_the_committed_metrics_include_weighted_calibration_and_uncertainty():
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    test = metrics["test"]["weighted"]
    assert test["auroc"] == pytest.approx(0.6372179442999376)
    assert test["pr_auc"] == pytest.approx(0.498319282641273)
    assert test["brier"] == pytest.approx(0.22343379326464247)
    assert test["calibration_slope"] == pytest.approx(1.0388168871183754)
    assert 0 <= test["expected_calibration_error"] <= 1
    assert metrics["calibration"]["test_expected_calibration_error"] == pytest.approx(
        test["expected_calibration_error"]
    )
    assert len(metrics["calibration"]["frozen_validation_bin_edges"]) == 11
    curve = metrics["calibration"]["test_calibration_curve"]
    assert len(curve) == 10
    assert [point["bin"] for point in curve] == list(range(1, 11))
    assert metrics["exclusion_counts"]["known_pregnant_excluded_after_core_filters"] == 136
    assert metrics["exclusion_counts"]["unknown_pregnancy_excluded_after_core_filters"] == 3
    interval = metrics["test"]["psu_cluster_bootstrap_uncertainty"]
    assert interval["replicates"] == 2000
    assert interval["metrics"]["auroc"]["ci_low"] < interval["metrics"]["auroc"]["ci_high"]
    ece_interval = interval["metrics"]["expected_calibration_error"]
    assert ece_interval["ci_low"] <= ece_interval["estimate"] <= ece_interval["ci_high"]
    assert "not a full three-stage survey-design interval" in interval["scope"]


def test_the_committed_metrics_disclose_sex_age_and_residence_subgroups():
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    subgroups = metrics["subgroups"]
    assert {"female", "male", "age_18_39", "age_40_59", "age_60_69", "rural", "urban"} <= set(subgroups)
    assert all(result["metrics"] is not None for result in subgroups.values())
    # Keep the known weak subgroup visible instead of allowing a future report
    # to hide it behind the stronger overall average.
    assert subgroups["age_60_69"]["metrics"]["auroc"] < 0.5
    assert subgroups["age_60_69"]["metrics"]["calibration_slope"] < 0


def test_the_committed_metrics_include_target_and_missing_data_sensitivities():
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    target = metrics["target_sensitivity"]
    assert target["primary"] == "mean of second and third BP readings; both readings required"
    assert target["all_rows_changed_binary_label"] > 0
    assert metrics["missing_data_sensitivity"]["weighted_test"]["auroc"] == pytest.approx(0.5)
