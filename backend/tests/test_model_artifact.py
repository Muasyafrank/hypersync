"""The committed model artefact must match its published identity and contract."""

import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

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
from app.core.ml_recommendation_engine import (
    _build_model_features,
    _contribution_explanation,
    _latest_lifestyle_values,
    _predict_at_risk_probability,
    _predict_with_explanation,
    _validate_model_bundle,
    _validate_model_file,
)
from ml.model_contract import (
    CHECKSUM_FILENAMES,
    MODEL_ESTIMATE_AGE_RANGE,
    MODEL_FILENAMES,
    MODEL_VERSIONS,
    RUNTIME_MODEL_BOOTSTRAP_REPLICATES,
    RUNTIME_MODEL_BUILD_PLATFORM,
    RUNTIME_MODEL_BUILD_PYTHON,
    RUNTIME_MODEL_EFFECT_UNITS,
    RUNTIME_MODEL_FEATURES,
    RUNTIME_MODEL_INPUT_FEATURES,
    RUNTIME_MODEL_RAW_SHA256,
    RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
    RUNTIME_MODEL_SHA256,
    RUNTIME_MODEL_SPLIT_SHA256,
    RUNTIME_MODEL_TRAINING_DATA_SHA256,
    RUNTIME_MODEL_VERSION,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = BACKEND_ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "bp_status_model.joblib"
CHECKSUM_PATH = MODEL_DIR / "SHA256SUMS"
CARD_PATH = MODEL_DIR / "MODEL_CARD.md"
METRICS_PATH = BACKEND_ROOT / "ml" / "artifacts" / "metrics.json"
ML_README_PATH = BACKEND_ROOT / "ml" / "README.md"

EXPECTED_FEATURES = list(RUNTIME_MODEL_FEATURES)
EXPECTED_INPUTS = list(RUNTIME_MODEL_INPUT_FEATURES)


def _checksum() -> str:
    return hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()


def _bundle() -> dict:
    return joblib.load(MODEL_PATH)


def test_the_clean_checkout_contains_the_runtime_artifact():
    assert MODEL_PATH.is_file()
    assert MODEL_PATH.stat().st_size < 100_000  # the runtime bundle, not the raw survey


def test_the_artifact_matches_its_recorded_sha256():
    recorded = CHECKSUM_PATH.read_text(encoding="utf-8").strip().split()
    assert len(recorded) == 2
    assert recorded[1] == MODEL_PATH.name
    assert recorded[0] == _checksum()
    assert recorded[0] == RUNTIME_MODEL_SHA256


def test_a_digest_mismatch_is_rejected_before_anything_is_unpickled(tmp_path, monkeypatch):
    artifact = tmp_path / "foreign.joblib"
    artifact.write_bytes(b"foreign bytes")
    monkeypatch.setattr(joblib, "load", lambda _path: pytest.fail("unpickled an unverified artefact"))

    with pytest.raises(ValueError, match="SHA-256"):
        _validate_model_file(artifact)


def test_the_model_card_records_the_same_identity_and_keeps_its_limits_visible():
    card = CARD_PATH.read_text(encoding="utf-8")
    assert _checksum() in card
    assert RUNTIME_MODEL_VERSION in card
    assert f"{MODEL_PATH.stat().st_size:,} bytes" in card
    assert "not clinically approved" in card
    assert "not evidence of clinical benefit" in card


def test_the_published_effect_intervals_match_the_committed_metrics():
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    card = CARD_PATH.read_text(encoding="utf-8")
    readme = ML_README_PATH.read_text(encoding="utf-8")
    labels = {
        "age": "+10 years of age (mean spline contrast)",
        "sex": "Male vs female",
        "salt_score": "+1 salt level",
        "alcohol_consumed": "Alcohol in the last 30 days",
        "activity_minutes": "+30 active minutes/day",
        "diet_adherence": "Meets fruit/vegetable target",
        "smoked": "Currently smokes",
    }

    for feature, label in labels.items():
        effect = metrics["effects"][feature]
        rendered = f"{effect['odds_ratio']:.3f} ({effect['ci_low']:.3f}–{effect['ci_high']:.3f})"
        row = f"| {label} | {rendered} |"
        assert row in card
        assert row in readme


def test_the_model_feature_threshold_and_uncertainty_contract_matches_the_application():
    bundle = _bundle()
    assert bundle["version"] == RUNTIME_MODEL_VERSION
    assert bundle["model_type"] == "logistic"
    assert bundle["feature_columns"] == EXPECTED_FEATURES
    assert bundle["model_input_columns"] == EXPECTED_INPUTS
    assert set(bundle["feature_defaults"]) == set(EXPECTED_FEATURES)
    assert bundle["label_order"] == list(bundle["model"].classes_) == ["at_risk", "not_at_risk"]

    thresholds = bundle["metrics"]["classification_thresholds"]
    assert thresholds == {
        "low_systolic": LOW_SYSTOLIC,
        "low_diastolic": LOW_DIASTOLIC,
        "high_systolic": HIGH_SYSTOLIC,
        "high_diastolic": HIGH_DIASTOLIC,
        "very_high_systolic": VERY_HIGH_SYSTOLIC,
        "very_high_diastolic": VERY_HIGH_DIASTOLIC,
        "elevated_systolic": ELEVATED_SYSTOLIC,
        "elevated_diastolic": ELEVATED_DIASTOLIC,
    }

    calibration = bundle["calibration"]
    assert calibration["method"] == "platt_logit"
    assert math.isfinite(calibration["slope"]) and calibration["slope"] > 0
    assert math.isfinite(calibration["intercept"])

    expected_build_environment = {
        "python": RUNTIME_MODEL_BUILD_PYTHON,
        "platform": RUNTIME_MODEL_BUILD_PLATFORM,
        "requirements_lock_sha256": RUNTIME_MODEL_REQUIREMENTS_LOCK_SHA256,
    }
    assert bundle["build_environment"] == expected_build_environment
    assert bundle["metrics"]["build_environment"] == expected_build_environment
    assert bundle["metrics"]["runtime_estimate_age_range"] == list(MODEL_ESTIMATE_AGE_RANGE)
    assert "platform" not in bundle["metrics"]["numerical_environment"]

    metrics_calibration = bundle["metrics"]["calibration"]
    assert len(metrics_calibration["frozen_validation_bin_edges"]) == 11
    assert metrics_calibration["test_expected_calibration_error"] == pytest.approx(
        bundle["metrics"]["test"]["weighted"]["expected_calibration_error"]
    )

    contribution = bundle["contribution"]
    assert contribution["method"] == "stratified_psu_bootstrap"
    assert contribution["replicates"] == RUNTIME_MODEL_BOOTSTRAP_REPLICATES == 200
    assert set(contribution["groups"]) == set(EXPECTED_FEATURES)
    assert np.asarray(contribution["bootstrap_coefficients"]).shape == (
        RUNTIME_MODEL_BOOTSTRAP_REPLICATES,
        len(contribution["feature_names"]),
    )
    _validate_model_bundle(bundle)


def test_the_bundle_records_every_reproducibility_hash():
    bundle = _bundle()
    assert bundle["raw_data_sha256"] == RUNTIME_MODEL_RAW_SHA256
    assert bundle["split_lock_sha256"] == RUNTIME_MODEL_SPLIT_SHA256
    assert bundle["training_data_sha256"] == RUNTIME_MODEL_TRAINING_DATA_SHA256
    assert bundle["metrics"]["raw_data_sha256"] == RUNTIME_MODEL_RAW_SHA256
    assert bundle["metrics"]["split_lock_sha256"] == RUNTIME_MODEL_SPLIT_SHA256
    assert bundle["metrics"]["training_data_sha256"] == RUNTIME_MODEL_TRAINING_DATA_SHA256
    assert bundle["training_command"] == "PYTHONHASHSEED=0 python -m ml.train_model --features current"


@pytest.mark.parametrize(
    "malformation",
    [
        "feature_columns",
        "model_inputs",
        "default_domain",
        "labels",
        "thresholds",
        "effect_set",
        "effect_values",
        "effect_unit",
        "metrics_version",
        "build_environment",
        "calibration",
        "calibration_ece",
        "calibration_metrics",
        "calibration_edges",
        "contribution_replicates",
        "contribution_groups",
        "contribution_feature_names",
        "contribution_point_coefficients",
        "contribution_zero_bootstrap",
        "contribution_arrays",
        "raw_hash",
        "training_hash",
    ],
)
def test_the_runtime_rejects_an_incomplete_or_foreign_model_contract(malformation):
    bundle = _bundle()
    if malformation == "feature_columns":
        bundle["feature_columns"].pop()
    elif malformation == "model_inputs":
        bundle["model_input_columns"].pop()
    elif malformation == "default_domain":
        bundle["feature_defaults"]["age"] = 500
    elif malformation == "labels":
        bundle["label_order"] = ["not_at_risk", "at_risk"]
    elif malformation == "thresholds":
        bundle["metrics"]["classification_thresholds"]["high_systolic"] = 160
    elif malformation == "effect_set":
        bundle["effects"].pop("sex")
    elif malformation == "effect_values":
        bundle["effects"]["smoked"]["ci_high"] = float("nan")
        bundle["metrics"]["effects"]["smoked"]["ci_high"] = float("nan")
    elif malformation == "effect_unit":
        bundle["effects"]["smoked"]["unit"] = "per cigarette"
    elif malformation == "metrics_version":
        bundle["metrics"]["model_version"] = "foreign-model"
    elif malformation == "build_environment":
        bundle["build_environment"]["python"] = "3.14.0"
    elif malformation == "calibration":
        bundle["calibration"]["slope"] = -1
    elif malformation == "calibration_ece":
        bundle["metrics"]["calibration"]["test_expected_calibration_error"] += 0.1
    elif malformation == "calibration_metrics":
        bundle["metrics"]["calibration"]["slope"] += 0.1
    elif malformation == "calibration_edges":
        bundle["metrics"]["calibration"]["frozen_validation_bin_edges"] = [0.5] * 11
    elif malformation == "contribution_replicates":
        bundle["contribution"]["replicates"] = 2
        bundle["metrics"]["contribution_uncertainty"]["replicates"] = 2
    elif malformation == "contribution_groups":
        bundle["contribution"]["groups"]["smoked"] = []
    elif malformation == "contribution_feature_names":
        bundle["contribution"]["feature_names"] = ["renamed"] * len(bundle["contribution"]["feature_names"])
    elif malformation == "contribution_point_coefficients":
        bundle["contribution"]["point_coefficients"] = np.zeros_like(bundle["contribution"]["point_coefficients"])
    elif malformation == "contribution_zero_bootstrap":
        bundle["contribution"]["bootstrap_coefficients"] = np.zeros_like(
            bundle["contribution"]["bootstrap_coefficients"]
        )
    elif malformation == "contribution_arrays":
        bundle["contribution"]["bootstrap_coefficients"] = np.asarray(bundle["contribution"]["bootstrap_coefficients"])[
            :-1
        ]
    elif malformation == "raw_hash":
        bundle["raw_data_sha256"] = "0" * 64
    else:
        bundle["training_data_sha256"] = "0" * 64

    with pytest.raises(ValueError):
        _validate_model_bundle(bundle)


def test_experimental_bmi_training_cannot_overwrite_the_runtime_artifact():
    assert MODEL_FILENAMES["current"] == MODEL_PATH.name
    assert MODEL_FILENAMES["bmi"] != MODEL_PATH.name
    assert MODEL_VERSIONS["bmi"] != MODEL_VERSIONS["current"]
    assert CHECKSUM_FILENAMES["bmi"] != CHECKSUM_FILENAMES["current"]


def test_the_artifact_can_score_its_weighted_reference_profile():
    bundle = _bundle()
    row = {name: bundle["feature_defaults"][name] for name in EXPECTED_FEATURES}
    row.update({name: 0 for name in EXPECTED_INPUTS if name.endswith("_missing")})
    probability = bundle["model"].predict_proba(__import__("pandas").DataFrame([row], columns=EXPECTED_INPUTS))[0]
    assert 0 <= float(probability[list(bundle["model"].classes_).index("at_risk")]) <= 1


def test_a_model_prediction_failure_is_reported_as_no_estimate():
    class BrokenModel:
        classes_ = ["at_risk", "not_at_risk"]

        def predict_proba(self, _frame):
            raise RuntimeError("broken model")

    bundle = {
        "model": BrokenModel(),
        "feature_columns": ["age"],
        "model_input_columns": ["age"],
        "feature_defaults": {"age": 35},
        "effects": {},
    }

    assert _predict_at_risk_probability(bundle, {"age": 35}) is None


def test_each_lifestyle_field_keeps_its_own_latest_available_answer():
    latest = SimpleNamespace(
        smoked=None,
        alcohol_consumed=None,
        salt_intake=None,
        physical_activity_minutes=None,
        diet_adherence=None,
    )
    earlier = SimpleNamespace(
        smoked=False,
        alcohol_consumed=False,
        salt_intake="low",
        physical_activity_minutes=30,
        diet_adherence=True,
    )

    values = _latest_lifestyle_values([latest, earlier])

    assert values == {
        "smoked": False,
        "alcohol_consumed": False,
        "salt_intake": "low",
        "physical_activity_minutes": 30,
        "diet_adherence": True,
    }


def test_missing_lifestyle_answers_use_the_recorded_training_defaults_and_stay_flagged():
    bundle = _bundle()
    defaults = bundle["feature_defaults"]
    empty_entry = SimpleNamespace(
        smoked=None,
        alcohol_consumed=None,
        salt_intake=None,
        physical_activity_minutes=None,
        diet_adherence=None,
    )

    features = _build_model_features(empty_entry, age=40, sex=1, defaults=defaults)

    assert features["activity_minutes"] == defaults["activity_minutes"]
    assert features["diet_adherence"] == defaults["diet_adherence"]
    assert features["salt_score"] == defaults["salt_score"]
    assert features["smoked"] == defaults["smoked"]
    assert features["alcohol_consumed"] == defaults["alcohol_consumed"]
    for feature in ("smoked", "alcohol_consumed", "salt_score", "activity_minutes", "diet_adherence"):
        assert features[f"{feature}_missing"] == 1


def test_activity_above_the_published_cap_uses_the_capped_training_value():
    bundle = _bundle()
    entry = SimpleNamespace(
        smoked=False,
        alcohol_consumed=False,
        salt_intake="none",
        physical_activity_minutes=600,
        diet_adherence=True,
    )

    features = _build_model_features(entry, age=40, sex=0, defaults=bundle["feature_defaults"])

    assert features["activity_minutes"] == 240
    assert features["activity_minutes_missing"] == 0


def test_predictions_include_ordered_uncertainty_intervals_for_every_explained_factor():
    bundle = _bundle()
    row = {name: bundle["feature_defaults"][name] for name in EXPECTED_FEATURES}
    row.update({name: 0 for name in EXPECTED_INPUTS if name.endswith("_missing")})
    row.update(
        {
            "salt_score": 3,
            "smoked": 1,
            "alcohol_consumed": 1,
            "activity_minutes": 0,
            "diet_adherence": 0,
        }
    )

    prediction = _predict_with_explanation(bundle, row)

    assert prediction is not None
    assert 0 <= prediction["probability"] <= 1
    assert set(prediction["contributions"]) == {
        "salt_score",
        "alcohol_consumed",
        "activity_minutes",
        "diet_adherence",
        "smoked",
    }
    for values in prediction["contributions"].values():
        assert math.isfinite(values["point"])
        assert math.isfinite(values["ci_low"])
        assert math.isfinite(values["ci_high"])
        assert values["ci_low"] <= values["ci_high"]
        assert values["missing"] is False


def test_missing_feature_contributions_are_labelled_as_missing_information():
    bundle = _bundle()
    row = {name: bundle["feature_defaults"][name] for name in EXPECTED_FEATURES}
    row.update({name: 0 for name in EXPECTED_INPUTS if name.endswith("_missing")})
    row["salt_score_missing"] = 1

    prediction = _predict_with_explanation(bundle, row)

    assert prediction is not None
    assert prediction["contributions"]["salt_score"]["missing"] is True
    explanation = _contribution_explanation(
        {
            "salt_score": {
                "point": 0.12,
                "ci_low": -0.03,
                "ci_high": 0.27,
                "missing": True,
            }
        }
    )
    assert "Missing salt intake information moved the model score" in explanation
    assert "not percentage points" in explanation
    assert "do not prove that changing a habit" in explanation


def test_a_zero_contribution_does_not_claim_that_a_factor_moved_the_score():
    explanation = _contribution_explanation(
        {
            feature: {"point": 0.0, "ci_low": 0.0, "ci_high": 0.0, "missing": False}
            for feature in ("salt_score", "alcohol_consumed", "activity_minutes", "diet_adherence", "smoked")
        }
    )

    assert "No single lifestyle factor moved the model score much" in explanation
    assert "95% range" not in explanation


def test_the_published_effect_metadata_is_complete_and_ordered():
    bundle = _bundle()
    assert set(bundle["effects"]) == set(EXPECTED_FEATURES)
    assert bundle["metrics"]["effects"] == bundle["effects"]
    for feature, effect in bundle["effects"].items():
        assert effect["unit"] == RUNTIME_MODEL_EFFECT_UNITS[feature]
        assert effect["ci_low"] <= effect["odds_ratio"] <= effect["ci_high"]
