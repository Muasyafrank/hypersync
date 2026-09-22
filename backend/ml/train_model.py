"""
Trains HyperSync's blood-pressure-status classifier on real Kenya STEPS
2015 NCD risk factor survey data (KNBS/MoH/WHO, n=4,500 respondents,
nationally representative, 2015).

The model predicts a binary AT-RISK / NOT-AT-RISK target (at_risk =
Elevated or High blood pressure, using the same thresholds as
app/core/bp_classification.py) from demographic and lifestyle features
STEPS actually measures: age, sex, smoking, alcohol use, salt behaviour,
physical activity, and diet.

Binary framing rationale: HyperSync's recommendation engine only ever
fires when a patient's trend is Elevated or High, so this is the target
that is actually operationally useful — and it matches the standard
binary (normotensive vs hypertensive/elevated) framing used in the
hypertension ML literature this approach is modelled on.

This is a cross-sectional survey: the model demonstrates ASSOCIATION
between lifestyle factors and blood pressure category in the surveyed
population at a single point in time — not a causal, within-patient,
longitudinal prediction.

Run from the backend/ directory:
    python -m ml.train_model
"""
import os
import json
import joblib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, accuracy_score, f1_score, confusion_matrix, roc_auc_score
from sklearn.utils.class_weight import compute_class_weight

from ml.steps_pipeline import build_dataset, FEATURE_COLUMNS

MODEL_DIR = "ml/models"
ARTIFACT_DIR = "ml/artifacts"
DATA_PATH = "data/2015_STEPS_Data.sav"

LABEL_ORDER = ["not_at_risk", "at_risk"]


def to_binary_target(bp_status: str) -> str:
    """
    Reframes the 4-class BP status as a binary target aligned with what
    HyperSync's recommendation engine actually needs. 'low' is grouped
    with 'controlled' as not_at_risk, since it is not the lifestyle-risk
    category this model is meant to explain.
    """
    return "at_risk" if bp_status in ("elevated", "high") else "not_at_risk"


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    print("Loading and cleaning Kenya STEPS 2015 data...")
    df = build_dataset(DATA_PATH)
    df = df.dropna(subset=FEATURE_COLUMNS)
    print(f"Final training dataset: {len(df)} respondents")
    print(df["bp_status"].value_counts())

    X = df[FEATURE_COLUMNS]
    y = df["bp_status"].map(to_binary_target)
    print("\nBinary target distribution:")
    print(y.value_counts())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)}   Test: {len(X_test)}")

    classes = np.array(LABEL_ORDER)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes, weights))
    print("Class weights:", class_weight)

    model = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=8,
        class_weight=class_weight, random_state=42, n_jobs=-1,
    )

    print("\nRunning 5-fold stratified cross-validation on training set...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1_macro")
    print(f"CV macro-F1: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")

    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    report_text = classification_report(y_test, preds, labels=LABEL_ORDER, zero_division=0)
    print("\n" + report_text)

    acc = accuracy_score(y_test, preds)
    macro_f1 = f1_score(y_test, preds, average="macro", zero_division=0)
    weighted_f1 = f1_score(y_test, preds, average="weighted", zero_division=0)
    cm = confusion_matrix(y_test, preds, labels=LABEL_ORDER)

    proba = model.predict_proba(X_test)
    at_risk_idx = list(model.classes_).index("at_risk")
    auc = roc_auc_score((y_test == "at_risk").astype(int), proba[:, at_risk_idx])

    print(f"Accuracy: {acc:.3f}   Macro F1: {macro_f1:.3f}   Weighted F1: {weighted_f1:.3f}   ROC-AUC: {auc:.3f}")

    metrics = {
        "data_source": "Kenya STEPS NCD Risk Factor Survey 2015 (KNBS/MoH/WHO)",
        "n_total": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "class_distribution": y.value_counts().to_dict(),
        "cv_macro_f1_mean": float(cv_scores.mean()),
        "cv_macro_f1_std": float(cv_scores.std()),
        "test_accuracy": float(acc),
        "test_macro_f1": float(macro_f1),
        "test_weighted_f1": float(weighted_f1),
        "test_roc_auc": float(auc),
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": LABEL_ORDER,
    }
    with open(f"{ARTIFACT_DIR}/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    with open(f"{ARTIFACT_DIR}/classification_report.txt", "w") as f:
        f.write(f"Data source: Kenya STEPS 2015 (n={len(df)})\n\n")
        f.write(report_text)

    importances = model.feature_importances_
    order = np.argsort(importances)
    plt.figure(figsize=(8, 5))
    plt.barh(np.array(FEATURE_COLUMNS)[order], importances[order], color="#0D9488")
    plt.xlabel("Feature importance")
    plt.title(f"HyperSync BP-Status Model — Feature Importance\n(trained on Kenya STEPS 2015, n={len(df)})")
    plt.tight_layout()
    plt.savefig(f"{ARTIFACT_DIR}/feature_importance.png", dpi=160)
    plt.close()

    plt.figure(figsize=(5.5, 5))
    plt.imshow(cm, cmap="Greens")
    plt.xticks(range(len(LABEL_ORDER)), LABEL_ORDER, rotation=45)
    plt.yticks(range(len(LABEL_ORDER)), LABEL_ORDER)
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("Confusion Matrix")
    for i in range(len(LABEL_ORDER)):
        for j in range(len(LABEL_ORDER)):
            plt.text(j, i, cm[i, j], ha="center", va="center",
                      color="white" if cm[i, j] > cm.max() / 2 else "black")
    plt.tight_layout()
    plt.savefig(f"{ARTIFACT_DIR}/confusion_matrix.png", dpi=160)
    plt.close()

    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "label_order": LABEL_ORDER,
            "metrics": metrics,
            "data_source": "Kenya STEPS NCD Risk Factor Survey 2015",
            "version": "2.0.0-steps",
        },
        f"{MODEL_DIR}/bp_status_model.joblib",
    )

    print(f"\nSaved model   -> {MODEL_DIR}/bp_status_model.joblib")
    print(f"Saved metrics -> {ARTIFACT_DIR}/metrics.json")
    print(f"Saved charts  -> {ARTIFACT_DIR}/feature_importance.png, confusion_matrix.png")


if __name__ == "__main__":
    main()
