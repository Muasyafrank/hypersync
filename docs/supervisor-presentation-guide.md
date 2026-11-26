# HyperSync supervisor presentation and demo guide

**Presentation date:** 25 November 2026
**Recommended duration:** 12–15 minutes plus questions
**Best defensible positioning:** a working, clinically reviewable **decision-support prototype**, not a clinically approved diagnostic or emergency-monitoring system.

## 1. Opening statement

> HyperSync is a manual blood-pressure logging and clinician decision-support prototype. Patients enter readings and daily lifestyle information themselves; the system classifies the readings, tracks trends, produces transparent lifestyle guidance, and gives clinicians a review queue. It does not connect to a monitoring device and it does not send emergency alerts. The main thresholds and habit wording are collected in one review sheet, but that sheet is still unsigned.

This opening prevents the demo from overstating the system.

## 2. What to show (10–12 minute sequence)

### A. Patient dashboard — the complete workflow (2 minutes)

1. Open **Dashboard** as Daniel (`demo.daniel@example.com`).
2. Point out:
   - latest manually entered reading;
   - 30-day average and band;
   - reading distribution;
   - unread-alert count;
   - recommendations grouped into clear patient-facing sections.
3. Open **Recommendations**.
4. Explain the ordering:
   - the patient's own reading trend;
   - personal patterns supported by their log;
   - concrete actions for logged habits;
   - survey context explained in the summary;
   - system/coverage messages.
5. Daniel demonstrates the advice cap: smoking remains visible, while medication information stays out of patient output. The overflow message names the other habits **and retains their actions**.

**Expected Daniel outcome:** high band; smoking present; no medication or treatment advice; no personal pattern because there are no safe comparison days; advice includes an overflow item with concrete actions.

### B. Transparent personal pattern (1–2 minutes)

1. Log in as Peter (`demo.peter@example.com`).
2. Open **Recommendations**.
3. Point to the two separate findings:
   - under-six-hours sleep;
   - high salt.
4. Read the wording aloud: it gives the patient's own millimetres-of-mercury gap and says this is a link in their log, **not proof of cause**.
5. If time permits, open the patient **Trends** chart and expand **View daily values as a table**. This demonstrates the accessible text alternative and exact values.

**Expected Peter outcome:** two own-data findings, each with the difference and concrete next step.

### C. Measurement quality (1 minute)

1. Log in as Mary (`demo.mary@example.com`).
2. Open **Recommendations**.
3. The first actionable finding says that hurried/post-stimulant readings ran higher than properly rested readings.
4. Explain why the system checks technique before blaming lifestyle.

**Expected Mary outcome:** elevated average, but the leading finding is measurement technique, including the approximate gap.

### D. Sparse data and low readings (1 minute)

1. Log in as Amina (`demo.amina@example.com`).
2. Show the high 7-day average and alert.
3. Point to the coverage message saying exactly how many paired days are still needed for personal patterns.
4. Optionally log in as Joseph (`demo.joseph@example.com`) to show the low-band wording and the clinician-only sustained-low review.

**Expected Amina outcome:** high trend, no medication or treatment advice, and an exact logging target.
**Expected Joseph outcome:** low-band safety wording says to contact the clinician if dizzy or unwell. No lifestyle advice is attached.

### E. Clinician workflow and role isolation (3 minutes)

1. Log out and log in as Dr. Wambui (`demo.clinician@example.com`).
2. On the clinician dashboard, show:
   - patient list with treatment-review badges;
   - alert queue;
   - summary of the patient cohort.
3. Open Daniel's detail page. Show:
   - weekly trend;
   - treatment-review reasoning;
   - medication use, measurement quality and lifestyle contributors;
   - the statement that no drug or dose is suggested.
4. Point out the role boundary: the treatment-review endpoint and record are clinician-only; the patient interface does not expose them.
5. Mark Daniel as reviewed only if you want to demonstrate the 28-day follow-up window. Otherwise leave the data unchanged.

**Expected clinician outcome:** Daniel is priority because he is high in the recent weeks and medication is often logged as not taken; Peter/James are routine elevated/high-band reviews; Joseph is flagged in the low direction; Grace is not flagged.

### F. Live recomputation (1 minute, optional but effective)

While logged in as Daniel, add one new manual reading from **Log reading**. The app saves the reading, recomputes recommendations, and opens **Recommendations** with the updated state.

If the recommendation refresh fails, the app must say that the reading was saved but recommendations could not be refreshed; it must not claim success. If the model artefact is unavailable, readings and lifestyle guidance still work and the population estimate is omitted.

Do not try to save a second lifestyle check-in for the same day: the intended result is a clear duplicate-day message. This is a correctness feature, not a failure.

## 3. Demo accounts

Every demo account uses password `DemoPass#2026`.

| Account | Purpose |
| --- | --- |
| `demo.daniel@example.com` | High pressure, many risky habits, advice-cap overflow, priority review, medication often logged as not taken |
| `demo.peter@example.com` | Separate sleep and salt personal patterns; routine elevated/high-band review despite medication logged as taken |
| `demo.mary@example.com` | Hurried/post-stimulant readings and measurement caution |
| `demo.james@example.com` | Noise and cold-weather personal patterns |
| `demo.amina@example.com` | High pressure with very sparse lifestyle logging and unknown medication use |
| `demo.joseph@example.com` | Sustained low readings; low-direction clinician review |
| `demo.grace@example.com` | Controlled readings and healthy habits; the system stays quiet |
| `demo.clinician@example.com` | Clinician dashboard, alert queue and treatment-review flags |

Seed before the presentation from `backend/`:

```bash
python -m scripts.seed_demo_30_days
```

The seed is deterministic and refreshes only the `@example.com` demo accounts. The personas, readings, and logs are synthetic behavioural fixtures for exercising the workflow. They are not study participants, validation data, or evidence of model performance or clinical benefit.

## 4. Evidence to mention

- The recommendation endpoint recomputes from current data on every request and sends `Cache-Control: no-store`.
- The patient's own readings and the survey-model estimate are displayed separately; they are not blended into an invented risk score.
- Missing profile/lifestyle inputs are disclosed in the patient-facing text, and the model uses recorded training-population defaults with explicit missingness flags.
- The model uses the STEPS measurement weight, locked PSU-grouped splits, regularised logistic regression, and validation-only calibration.
- The model's per-prediction contributions include 95% PSU-bootstrap ranges that resample both training and validation PSUs, and are labelled non-causal.
- One lifestyle check-in per local day is enforced by both API and database; medication adherence and habit patterns count distinct days.
- The accessible trend chart expands to an exact-value table and scales beyond 200 mmHg.
- The clinical wording is generated from code, and a drift test detects divergence between the code and the generated sheet; it does not verify clinical sign-off.
- The committed model has a version, SHA-256 checksum, exact feature contract, model card, data card, locked split and measured subgroup results.
- A real loopback Uvicorn HTTP gate checks that the first recommendation request and p95 remain below 300 ms without an LLM.

Run the verification commands live only if time allows; do not turn the presentation into a test-console reading.

```bash
# backend
cd backend
hyper/bin/python -m pytest
hyper/bin/ruff check .
hyper/bin/ruff format --check .

# frontend
cd ../frontend
npm run check
```

A manual PostgreSQL upgrade → downgrade → upgrade check and a clean-checkout artefact check were run during final verification. They are engineering checks, not clinical validation, and they are not part of the default SQLite-based pytest suite.

## 5. Boundaries to state clearly

1. **Manual entry only.** There is no Bluetooth, device-data ingestion or CSV import. The browser uses the project's own API to store and retrieve the data patients enter.
2. **Safety route, public band unchanged.** `180/110` remains stored as High, but the recommendation engine treats systolic at least 180 or diastolic at least 110 as very high. It gives urgent-care wording only, with no model or lifestyle content. Low readings also use safety wording only.
3. **Unsigned clinical wording.** The review sheet's sign-off table is blank. It must not be called approved guidance.
4. **Population model, not diagnosis.** The patient-facing estimate names the 2015 Kenya STEPS source and year. Locked-test weighted AUROC is 0.634 and PR-AUC is 0.498. These are model metrics, not evidence of clinical benefit.
5. **Subgroup limits are visible.** The age 60–69 test subgroup has AUROC 0.408 and unstable calibration. The overall result must not be generalized to every user.
6. **Treatment-review flag is decision support.** It prompts clinician review and provides a 28-day follow-up window after a recorded review; it does not recommend a drug, dose or titration, and the adequacy of the window is a clinical judgement. Medication information never appears in patient recommendations.
7. **No clinical validation claims.** This repository cannot establish safety, usability with real patients, or clinical effectiveness.

## 6. Likely questions and concise answers

### “Does it work with a blood-pressure monitor?”

No. This version is manual-input only. Device ingestion would be a separate implementation with validation, security, device identity and clinical-safety work.

### “What happens at 180/110?”

The stored public band is still High. The recommendation engine has a separate very-high safety route. It tells the patient to seek urgent medical care and suppresses the model and lifestyle content. Any low reading in the same window also gets safety wording only.

### “Is the advice clinically approved?”

No. It is general lifestyle wording gathered in `docs/advice-for-clinical-review.md` for clinician review. The sign-off table is intentionally blank.

### “How accurate is the model?”

The untouched, survey-weighted locked-test AUROC is 0.634 and PR-AUC is 0.498. Calibration is close overall, but subgroup performance varies and the age 60–69 subgroup is poor. It is a modest population estimate, not an individual diagnosis or a prediction of treatment response.

### “How do you avoid advice driven by incomplete data?”

The app says when profile or lifestyle inputs are missing. It uses recorded training-population defaults and explicit missingness flags. It does not describe an unspecified sex as the patient's own. Model contributions include 95% ranges and say when direction is uncertain. Personal patterns require paired days on both sides of a comparison and are explicitly described as correlation, not cause.

### “How do you know the data is consistent?”

The API rejects empty, future and duplicate same-day check-ins; the database has a unique daily constraint; adherence and habit calculations use distinct days; and the migration chain was manually exercised through upgrade and downgrade against PostgreSQL during final verification.

### “What is the biggest next step?”

Authorised clinical review of thresholds and wording, prospective local subgroup validation, real-user usability and safety validation, and evaluation of whether the recommendations improve outcomes.

## 7. Contingency plan

- **Backend not ready:** show the seeded screenshots/data and use the architecture and model-card walkthrough.
- **Database migration fails:** show `alembic current`, explain that the committed migration chain includes the unnamed-constraint repair and daily uniqueness constraint, and do not improvise schema changes during the talk.
- **Model will not load:** the intended fallback still shows readings, trends, lifestyle actions and clinician review without the population estimate; the error is logged rather than returning a 500.
- **Browser/network failure:** use the patient personas in order (Daniel → Peter → Mary → Amina) and show the clinician review only if the API is reachable.
- **Time is short:** show Daniel's capped advice, Peter's own-data pattern, then the clinician badge/detail view. Those three screens cover the core contribution.

## 8. Closing statement

> HyperSync now demonstrates an auditable path from manual patient entries to transparent recommendations and clinician review, with clear ownership of thresholds, data integrity, accessibility and reproducibility. The next step is not to imply more certainty than the evidence supports; it is to obtain authorised clinical review and validate the workflow with real users.
