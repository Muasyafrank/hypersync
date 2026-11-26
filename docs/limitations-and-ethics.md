# Plain-language limitations and ethics statement

## What the population estimate means

HyperSync uses a small model trained with Kenya STEPS 2015 survey data. The model gives a population estimate for blood-pressure status at the same time as the survey. It uses age, sex, and five logged lifestyle factors.

The estimate is background context. It is not a diagnosis. It is not a forecast of a future event. It does not explain the patient's latest blood-pressure reading.

The patient's own readings are shown separately. HyperSync does not mix the model score into the reading average.

## How well the model works

The locked test set had 871 survey respondents. Its weighted AUROC was 0.634. This means the model had modest ability to separate the survey groups. Its weighted Brier score was 0.224. Overall calibration was close to the observed survey rate.

These figures do not show that HyperSync improves health. They do not show safety for patients. They do not replace testing with local patients and a clinical team.

The seeded demo patients are synthetic behavioural fixtures for testing the workflow. They are not study participants or validation evidence, and they are not included in the model metrics above.

Some groups did worse. The age 60–69 test group had AUROC 0.408 and an unstable calibration slope. Other age groups also had weak results. One overall result cannot be assumed for every age or sex.

## What the model cannot show

The survey was taken at one time. It cannot show that a habit caused a blood-pressure reading. It cannot show what will happen if one person changes a habit. It cannot show that treatment caused or prevented an outcome.

The survey's binary comparison group included 106 low readings alongside controlled readings. This is an event definition for the survey, not a judgement that a low reading is harmless. The app routes low readings to safety wording and never attaches this estimate to them.

Medication information is not used by the model. It is kept only for the clinician review feature. The survey also used broad questions that do not exactly match daily app logs. Some answers may be missing or inaccurate.

The model was not tested on future HyperSync patients. New populations may have different results. More local validation is needed before clinical use.

## Safety comes first

A low reading or a very-high reading in the current period uses safety wording only. No model estimate or lifestyle advice is attached. Very high means systolic pressure of at least 180 mmHg or diastolic pressure of at least 110 mmHg.

Patient messages never give a diagnosis. They never name a medicine or drug. They never give a dose, medication or treatment timing, treatment start/stop instructions, or treatment-change advice. Patients may still record medication status in the lifestyle check-in for clinician review; that data is not included in patient recommendation output. Treatment-review information stays in the clinician-only review area.

## Uncertainty is shown

Each model explanation gives the two largest feature contributions. If a displayed contribution is based on a missing input, it is labelled as missing information, not as the patient's behaviour. The overall estimate separately names every defaulted field. The app also gives a 95% range. If the range crosses zero, it says that the direction is uncertain.

The range comes from repeated survey-cluster model fits. Each repeat resamples training PSUs for the model and validation PSUs for calibration. It is not a causal range. It is not a full prediction range. It describes training-coefficient and validation-calibration sampling uncertainty only; the fitted age curve and scaling transform stay fixed during those resamples.

## Privacy and data use

The model runs locally. HyperSync does not send patient data to an external AI service. No external language model is used for patient recommendations.

The survey file is not committed to the project repository. The build records its SHA-256 hash so the source can be checked. The committed model artefact is checked against its own published hash before use.

Patient names, email addresses, dates of birth, IDs, and free text are not model inputs. They are not sent to third-party inference services. The API response shape remains unchanged.

## Deferred language layer

No language layer is part of this release. Patient text comes from fixed templates and deterministic code pending clinician review. This keeps a deterministic server-side fallback available and makes every message auditable. The browser workflow still requires the API and database; this is not a browser-offline application.

A future language layer must stay off by default. It must use a provider-neutral adapter. It must accept only structured, de-identified data. It must be validated locally. It must fail over to the deterministic templates. It must never receive names, emails, dates of birth, IDs, or free text. It must not change the API response shape. It must not bypass the low and very-high safety routes. Any such design still needs privacy and clinical review before use.

## Current status

This is a research prototype for decision support. The clinical wording and thresholds are still unsigned. The model is not clinically approved. It is not evidence of clinical benefit. It must not replace clinical judgement.

Future work should include prospective local validation, clinician review, subgroup monitoring, calibration checks, and privacy review before any clinical deployment.
