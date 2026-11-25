"""The committed model artefact must match its published identity and contract."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import joblib
import pandas as pd
import pytest

from app.core.bp_classification import (
    ELEVATED_DIASTOLIC,
    ELEVATED_SYSTOLIC,
    HIGH_DIASTOLIC,
    HIGH_SYSTOLIC,
    LOW_DIASTOLIC,
    LOW_SYSTOLIC,
)
from app.core.ml_recommendation_engine import (
    _build_model_features,
    _predict_at_risk_probability,
    _validate_model_bundle,
    _validate_model_file,
)
from ml.model_contract import (
    CHECKSUM_FILENAMES,
    MODEL_FILENAMES,
    MODEL_VERSIONS,
    RUNTIME_MODEL_FEATURES,
    RUNTIME_MODEL_SHA256,
    RUNTIME_MODEL_VERSION,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = BACKEND_ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "bp_status_model.joblib"
CHECKSUM_PATH = MODEL_DIR / "SHA256SUMS"
CARD_PATH = MODEL_DIR / "MODEL_CARD.md"

EXPECTED_FEATURES = list(RUNTIME_MODEL_FEATURES)


def _checksum() -> str:
    return hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()


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
    assert "not clinically approved" in card
    assert "not evidence of clinical benefit" in card


def test_the_model_feature_and_threshold_contract_matches_the_application():
    bundle = joblib.load(MODEL_PATH)
    assert bundle["version"] == RUNTIME_MODEL_VERSION
    assert bundle["model_type"] == "logistic"
    assert bundle["feature_columns"] == EXPECTED_FEATURES
    assert set(bundle["feature_medians"]) == set(EXPECTED_FEATURES)
    assert bundle["label_order"] == list(bundle["model"].classes_)

    thresholds = bundle["metrics"]["classification_thresholds"]
    assert thresholds == {
        "low_systolic": LOW_SYSTOLIC,
        "low_diastolic": LOW_DIASTOLIC,
        "high_systolic": HIGH_SYSTOLIC,
        "high_diastolic": HIGH_DIASTOLIC,
        "elevated_systolic": ELEVATED_SYSTOLIC,
        "elevated_diastolic": ELEVATED_DIASTOLIC,
    }
    _validate_model_bundle(bundle)


@pytest.mark.parametrize(
    "malformation",
    [
        "feature_columns",
        "median_domain",
        "labels",
        "thresholds",
        "effect_set",
        "effect_values",
        "effect_unit",
        "metrics_version",
    ],
)
def test_the_runtime_rejects_an_incomplete_or_foreign_model_contract(malformation):
    bundle = joblib.load(MODEL_PATH)
    if malformation == "feature_columns":
        bundle["feature_columns"].pop()
    elif malformation == "median_domain":
        bundle["feature_medians"]["age"] = 500
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
    else:
        bundle["metrics"]["model_version"] = "foreign-model"

    with pytest.raises(ValueError):
        _validate_model_bundle(bundle)


def test_experimental_bmi_training_cannot_overwrite_the_runtime_artifact():
    assert MODEL_FILENAMES["current"] == MODEL_PATH.name
    assert MODEL_FILENAMES["bmi"] != MODEL_PATH.name
    assert MODEL_VERSIONS["bmi"] != MODEL_VERSIONS["current"]
    assert CHECKSUM_FILENAMES["bmi"] != CHECKSUM_FILENAMES["current"]


def test_the_artifact_can_score_its_median_profile():
    bundle = joblib.load(MODEL_PATH)
    row = {name: bundle["feature_medians"][name] for name in EXPECTED_FEATURES}
    probability = bundle["model"].predict_proba(pd.DataFrame([row], columns=EXPECTED_FEATURES))[0]
    assert 0 <= float(probability[list(bundle["model"].classes_).index("at_risk")]) <= 1


def test_a_model_prediction_failure_is_reported_as_no_estimate():
    class BrokenModel:
        classes_ = ["at_risk", "not_at_risk"]

        def predict_proba(self, _frame):
            raise RuntimeError("broken model")

    bundle = {
        "model": BrokenModel(),
        "feature_columns": ["age"],
        "feature_medians": {"age": 35},
        "effects": {},
    }

    assert _predict_at_risk_probability(bundle, {"age": 35}) is None


def test_missing_lifestyle_answers_use_the_recorded_training_medians():
    bundle = joblib.load(MODEL_PATH)
    medians = bundle["feature_medians"]
    empty_entry = SimpleNamespace(
        smoked=None,
        alcohol_consumed=None,
        salt_intake=None,
        physical_activity_minutes=None,
        diet_adherence=None,
    )

    features = _build_model_features(empty_entry, age=40, sex=1, medians=medians)

    assert features["activity_minutes"] == medians["activity_minutes"]
    assert features["diet_adherence"] == medians["diet_adherence"]
    assert features["salt_score"] == medians["salt_score"]


def test_activity_above_the_published_cap_uses_the_capped_training_value():
    bundle = joblib.load(MODEL_PATH)
    entry = SimpleNamespace(
        smoked=False,
        alcohol_consumed=False,
        salt_intake="none",
        physical_activity_minutes=600,
        diet_adherence=True,
    )

    features = _build_model_features(entry, age=40, sex=0, medians=bundle["feature_medians"])

    assert features["activity_minutes"] == 240
