"""
Trains HyperSync's risk model on Kenya STEPS 2015 (KNBS/MoH/WHO, n=4,500).

Target: AT-RISK = Elevated or High blood pressure (same thresholds as
app/core/bp_classification.py) vs NOT-AT-RISK.

What changed in v3 and why (numbers in ml/README.md):
  * The deployed model is a logistic regression with a smooth age curve, not a
    random forest. Accuracy is the same within noise (all models sit at the
    ceiling of the available features), but its probabilities are calibrated.
    The old forest, trained with class_weight="balanced", over-stated risk
    (mean prediction 48% vs 42% actual), and that number was shown to patients.
  * Evaluation uses repeated 5-fold cross-validation on all data. A single
    884-row test split has a standard error of about +/-0.018 AUC, which is
    larger than most differences between candidate models.
  * It stores each lifestyle factor's ADJUSTED effect (odds ratio with a 95%
    bootstrap interval). The engine uses these instead of random-forest
    importance, which wrongly ranked physical activity second only to age.

This is a cross-sectional survey: it shows association at one point in time,
not that changing a factor will change a given person's blood pressure.

Run from backend/:
    python -m ml.train_model                  # features the app collects today
    python -m ml.train_model --features bmi   # once height/weight are collected
"""

import argparse
import json
import os

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from ml.steps_pipeline import BMI_FEATURE_COLUMNS, FEATURE_COLUMNS, build_dataset

MODEL_DIR = "ml/models"
ARTIFACT_DIR = "ml/artifacts"
DATA_PATH = "data/2015_STEPS_Data.sav"
LABEL_ORDER = ["not_at_risk", "at_risk"]
CONTINUOUS = {"age", "activity_minutes", "salt_score", "bmi", "pulse"}
EFFECT_FEATURES = ["salt_score", "alcohol_consumed", "activity_minutes", "diet_adherence", "smoked", "bmi"]
# feature -> (label, divisor so odds ratios are per a meaningful unit)
EFFECT_UNITS = {
    "age": ("per 10 years", 10.0),
    "sex": ("male vs female", 1.0),
    "bmi": ("per 5 BMI points", 5.0),
    "salt_score": ("per +1 salt level (0-3)", 1.0),
    "activity_minutes": ("per 30 active min/day", 30.0),
    "alcohol_consumed": ("alcohol in last 30 days", 1.0),
    "smoked": ("currently smokes", 1.0),
    "diet_adherence": ("meets fruit/veg target", 1.0),
}
N_BOOTSTRAP = 300


def build_model(columns):
    """Logistic regression with a smooth (spline) age curve. Expects a
    DataFrame so columns are matched by name."""
    continuous = [c for c in columns if c in CONTINUOUS and c != "age"]
    binary = [c for c in columns if c not in CONTINUOUS]
    pre = ColumnTransformer(
        [
            ("age", SplineTransformer(n_knots=5, degree=3), ["age"]),
            ("continuous", StandardScaler(), continuous),
            ("binary", "passthrough", binary),
        ]
    )
    return make_pipeline(pre, LogisticRegression(C=0.5, max_iter=2000))


def candidate_models(columns):
    return {
        "logistic (deployed)": lambda: build_model(columns),
        "random forest (v2)": lambda: RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=0,
            n_jobs=-1,
        ),
        "gradient boosting": lambda: HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.04,
            max_iter=250,
            min_samples_leaf=30,
            l2_regularization=1.0,
            random_state=0,
        ),
    }


def compare_models(X, y):
    """Repeated stratified CV on identical folds for every candidate."""
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=1)
    results = {}
    for name, make in candidate_models(list(X.columns)).items():
        aucs, briers = [], []
        for train_idx, test_idx in cv.split(X, y):
            model = make().fit(X.iloc[train_idx], y.iloc[train_idx])
            proba = model.predict_proba(X.iloc[test_idx])[:, 1]
            aucs.append(roc_auc_score(y.iloc[test_idx], proba))
            briers.append(brier_score_loss(y.iloc[test_idx], proba))
        results[name] = {
            "auc_mean": float(np.mean(aucs)),
            "auc_se": float(np.std(aucs) / np.sqrt(len(aucs))),
            "brier_mean": float(np.mean(briers)),
        }
        print(f"  {name:22s} AUC {np.mean(aucs):.3f} +/- {results[name]['auc_se']:.3f}   Brier {np.mean(briers):.4f}")
    return results


def calibration_report(X, y):
    """Out-of-fold probabilities and how honest they are. Ideal: slope 1,
    intercept 0, mean prediction equal to the observed rate."""
    cv = StratifiedKFold(5, shuffle=True, random_state=3)
    proba = cross_val_predict(build_model(list(X.columns)), X, y, cv=cv, method="predict_proba")[:, 1]
    clipped = np.clip(proba, 1e-4, 1 - 1e-4)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    fit = LogisticRegression(C=1e6).fit(logit, y)
    return proba, {
        "mean_predicted": float(proba.mean()),
        "observed_rate": float(y.mean()),
        "calibration_slope": float(fit.coef_[0][0]),
        "calibration_intercept": float(fit.intercept_[0]),
        "brier": float(brier_score_loss(y, proba)),
        "oof_auc": float(roc_auc_score(y, proba)),
    }


def adjusted_effects(df, columns):
    """Odds ratios (95% bootstrap CI) from one unpenalised logistic regression
    holding age, sex and the other factors fixed."""
    cols = [c for c in ["age", "sex"] + EFFECT_FEATURES if c in columns]
    Z = df[cols].astype(float).copy()
    for c in cols:
        Z[c] = Z[c] / EFFECT_UNITS[c][1]
    y = df["y"].to_numpy()

    def coefs(idx):
        return LogisticRegression(C=1e6, max_iter=3000).fit(Z.iloc[idx], y[idx]).coef_[0]

    rng = np.random.default_rng(0)
    n = len(Z)
    point = coefs(np.arange(n))
    boots = np.array([coefs(rng.integers(0, n, n)) for _ in range(N_BOOTSTRAP)])
    low, high = np.percentile(boots, [2.5, 97.5], axis=0)
    return {
        c: {
            "odds_ratio": float(np.exp(point[i])),
            "ci_low": float(np.exp(low[i])),
            "ci_high": float(np.exp(high[i])),
            "unit": EFFECT_UNITS[c][0],
        }
        for i, c in enumerate(cols)
    }


def save_charts(effects, proba, y, cm):
    names = list(effects)
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(names) + 1.6))
    for i, name in enumerate(names):
        e = effects[name]
        clear = e["ci_low"] > 1 or e["ci_high"] < 1
        colour = "#0D9488" if clear else "#94A3B8"
        ax.plot([e["ci_low"], e["ci_high"]], [i, i], color=colour, lw=2)
        ax.plot(e["odds_ratio"], i, "o", color=colour)
    ax.axvline(1, color="#334155", ls="--", lw=1)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([f"{n}  ({effects[n]['unit']})" for n in names], fontsize=8)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlabel("Adjusted odds ratio of elevated/high BP (95% CI). Grey = no clear effect")
    ax.set_title("Adjusted effects, Kenya STEPS 2015")
    fig.tight_layout()
    fig.savefig(f"{ARTIFACT_DIR}/effects.png", dpi=160)
    plt.close(fig)

    bins = np.quantile(proba, np.linspace(0, 1, 11))
    idx = np.clip(np.digitize(proba, bins[1:-1]), 0, 9)
    pred = [proba[idx == b].mean() for b in range(10)]
    obs = [y[idx == b].mean() for b in range(10)]
    fig, ax = plt.subplots(figsize=(5.2, 5))
    ax.plot([0, 1], [0, 1], "--", color="#94A3B8")
    ax.plot(pred, obs, "o-", color="#0D9488")
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed share at risk")
    ax.set_title("Calibration (out-of-fold, deciles)")
    fig.tight_layout()
    fig.savefig(f"{ARTIFACT_DIR}/calibration.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.imshow(cm, cmap="Greens")
    ax.set_xticks(range(2), LABEL_ORDER, rotation=45)
    ax.set_yticks(range(2), LABEL_ORDER)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Hold-out confusion matrix")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i][j], ha="center", va="center", color="white" if cm[i][j] > np.max(cm) / 2 else "black")
    fig.tight_layout()
    fig.savefig(f"{ARTIFACT_DIR}/confusion_matrix.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", choices=["current", "bmi"], default="current")
    args = parser.parse_args()
    columns = FEATURE_COLUMNS if args.features == "current" else BMI_FEATURE_COLUMNS

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    print("Loading and cleaning Kenya STEPS 2015 data...")
    df = build_dataset(DATA_PATH)
    df = df[df["pregnant"] != 1]  # pregnancy changes BP and weight
    df = df.dropna(subset=columns).reset_index(drop=True)
    df["y"] = df["bp_status"].isin(["elevated", "high"]).astype(int)
    print(f"Training set: {len(df)} respondents, {100 * df['y'].mean():.1f}% at risk; features = {columns}")

    X, y = df[columns], df["y"]

    print("\nRepeated 5-fold CV (3 repeats), identical folds for every model:")
    cv_results = compare_models(X, y)

    print("\nCalibration of out-of-fold probabilities:")
    oof_proba, calib = calibration_report(X, y)
    print(
        f"  mean predicted {calib['mean_predicted']:.3f} vs observed {calib['observed_rate']:.3f}; "
        f"slope {calib['calibration_slope']:.2f}, intercept {calib['calibration_intercept']:+.2f}"
    )

    print("\nAdjusted effects (95% bootstrap CI):")
    effects = adjusted_effects(df, columns)
    for name, e in effects.items():
        clear = "  <- clear effect" if (e["ci_low"] > 1 or e["ci_high"] < 1) else ""
        print(f"  {name:18s} OR {e['odds_ratio']:.2f} ({e['ci_low']:.2f}-{e['ci_high']:.2f})  {e['unit']}{clear}")

    # Hold-out split kept for a familiar confusion matrix; the CV above is the
    # number to trust.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    holdout = build_model(columns).fit(X_train, y_train)
    threshold = float(y_train.mean())  # flag anyone riskier than the average respondent
    hold_proba = holdout.predict_proba(X_test)[:, 1]
    hold_pred = (hold_proba >= threshold).astype(int)
    cm = confusion_matrix(y_test, hold_pred, labels=[0, 1]).tolist()
    (tn, fp), (fn, tp) = cm
    hold = {
        "threshold": threshold,
        "auc": float(roc_auc_score(y_test, hold_proba)),
        "sensitivity": tp / (tp + fn),
        "specificity": tn / (tn + fp),
        "confusion_matrix": cm,
    }
    print(
        f"\nHold-out (n={len(y_test)}): AUC {hold['auc']:.3f}, sensitivity {hold['sensitivity']:.2f}, "
        f"specificity {hold['specificity']:.2f} at threshold {threshold:.2f}"
    )

    # Final model: all data, string labels so the engine can look up "at_risk".
    final = build_model(columns).fit(X, y.map({0: "not_at_risk", 1: "at_risk"}))
    medians = {c: float(X[c].median()) for c in columns}

    metrics = {
        "data_source": "Kenya STEPS NCD Risk Factor Survey 2015 (KNBS/MoH/WHO)",
        "feature_set": args.features,
        "features": columns,
        "n_total": int(len(df)),
        "at_risk_share": float(y.mean()),
        "cv_comparison": cv_results,
        "calibration": calib,
        "holdout": hold,
        "effects": effects,
    }
    with open(f"{ARTIFACT_DIR}/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    with open(f"{ARTIFACT_DIR}/classification_report.txt", "w") as f:
        f.write(f"Kenya STEPS 2015, n={len(df)}, features={columns}\n\n")
        for name, r in cv_results.items():
            f.write(f"{name:22s} CV AUC {r['auc_mean']:.3f} +/- {r['auc_se']:.3f}  Brier {r['brier_mean']:.4f}\n")
        f.write(
            f"\nHold-out at threshold {threshold:.2f}: sensitivity {hold['sensitivity']:.2f}, "
            f"specificity {hold['specificity']:.2f}, AUC {hold['auc']:.3f}\n"
        )

    save_charts(effects, oof_proba, y.to_numpy(), cm)

    joblib.dump(
        {
            "model": final,
            "model_type": "logistic",
            "feature_columns": columns,
            "feature_medians": medians,
            "effects": effects,
            "label_order": LABEL_ORDER,
            "metrics": metrics,
            "data_source": "Kenya STEPS NCD Risk Factor Survey 2015",
            "version": "3.0.0-steps-logit",
        },
        f"{MODEL_DIR}/bp_status_model.joblib",
    )
    print(f"\nSaved model   -> {MODEL_DIR}/bp_status_model.joblib")
    print(f"Saved reports -> {ARTIFACT_DIR}/ (metrics.json, effects.png, calibration.png, confusion_matrix.png)")


if __name__ == "__main__":
    main()
