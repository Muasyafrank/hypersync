# HyperSync — Hypertension Patient Monitoring System

Final year project — Dedan Kimathi University of Technology.

HyperSync lets patients **manually enter** blood-pressure readings and daily
lifestyle factors, classifies each reading, tracks trends over time, places
trend alerts in a clinician review queue, and generates recommendations from
the patient's own log and a model trained on the Kenya STEPS 2015 NCD survey.

## Scope and safety boundary

- HyperSync is **manual-input only** in this version. It does not connect to a
  blood-pressure monitor, ingest device data, or send clinical alerts to a
  phone.
- The current bands are checked in this order: **low** below 90 systolic or 60
  diastolic; otherwise **high** at 150 systolic or 90 diastolic or above;
  otherwise **elevated** at 135 systolic or 85 diastolic or above. The public
  band remains `high`, but an internal safety boundary at **180 systolic or 110
  diastolic** routes any such reading to urgent-care wording only. Any low or
  very-high reading in the current recommendation window suppresses model and
  lifestyle content.
- The advice and thresholds are a **clinically reviewable prototype**, not
  approved clinical guidance. The review sheet is deliberately unsigned:
  `docs/advice-for-clinical-review.md`.
- The survey model supplies a population estimate as context. It is not a
  diagnosis, an individual risk forecast, or evidence that the app improves
  clinical outcomes.
- The model and patient templates run locally. No external LLM is used, and no
  patient data is sent to a third-party inference service.
- Patient-facing recommendation output never contains a diagnosis or any
  medication/drug/dose content, medication or treatment timing, treatment
  start/stop instructions, or treatment-change advice. Treatment review remains
  clinician-only.

## Structure

```
backend/          FastAPI + PostgreSQL + SQLAlchemy
  app/
    core/         config, database, security, auth deps, BP classification,
                  trend analysis, alert engine, ML recommendation engine
    models/       SQLAlchemy ORM models
    schemas/      Pydantic request/response models
    routers/      HTTP endpoints, grouped by resource
  alembic/        database migrations
  ml/             STEPS data pipeline, locked survey build, versioned model +
                  checksum, data card and model card
  scripts/        admin/clinician provisioning, test-data seeding
  data/           local raw survey data (not versioned) and the seed workbook
  tests/          pytest suite (unit tests + API tests on throw-away SQLite)

frontend/         React 19 + Vite + React-Bootstrap + Recharts
  src/
    api/          one module per backend resource; axios client with
                  automatic session refresh and the X-Timezone header
    components/   shared components
      ui/         presentational primitives (Panel, StatCard, DataRow,
                  FormField, FormModal, …)
      admin/      admin dashboard modals
      lifestyle/  lifestyle wizard steps
    context/      auth, toast and confirm providers
    hooks/        useAsync (loading/error/retry), useForm, useSubmit
    pages/        one file per route
    utils/        formatting and BP classification helpers (+ *.test.js)
```

## Roles

| Role | Can do |
| --- | --- |
| Patient | Log readings and lifestyle entries, view own trends, alerts and recommendations |
| Clinician | View all patients, their readings, trends and lifestyle factors; work the alert and treatment-review queues |
| Admin | Manage users, provision clinician accounts, reset passwords |

Patients self-register. Clinician and admin accounts are provisioned by an
admin (or the `scripts/` helpers for the first one).

## Running locally

### Backend

```bash
cd backend
python -m venv hyper && source hyper/bin/activate   # Windows: hyper\Scripts\activate
pip install -r requirements.txt          # add -r requirements-dev.txt for tests/lint/seeding
                                         # add -r requirements-ml.txt to retrain the model
                                         # ml/requirements-lock.txt pins the full resolved build

cp .env.example .env        # then fill in DATABASE_URL and SECRET_KEY
alembic upgrade head
# The versioned model artefact is already included; training is optional.

uvicorn app.main:app --reload
```

If the daily check-in migration reports legacy duplicate patient/day rows, it
will stop rather than discard observations automatically. The cleanup helper
prints every saved answer, merges complementary answers into the retained row,
and refuses to delete a group when two rows disagree about the same field.
Review the dry run, choose the retention rule explicitly, and retry the
migration:

```bash
python -m scripts.cleanup_duplicate_factors
python -m scripts.cleanup_duplicate_factors --apply --keep latest
alembic upgrade head
```

If the helper reports a same-field conflict, provide the exact chosen value in
a JSON resolutions file keyed by `patient-uuid/YYYY-MM-DD`, then rerun with
`--resolutions resolutions.json`. The helper is a dry run unless `--apply` is
supplied, and it changes nothing while any conflict is unresolved.

API docs at http://localhost:8000/docs

A clean checkout does not need the raw STEPS survey file for normal operation:
the small versioned runtime model is committed under `backend/ml/models/`, with
its checksum, model card and feature contract. Retraining is an optional
maintenance task that additionally requires the pinned environment in
`backend/ml/requirements-lock.txt` and the separately obtained
`data/2015_STEPS_Data.sav`; see `backend/ml/models/MODEL_CARD.md` and
`backend/ml/DATA_CARD.md`.

Provisioning and sample data (run from `backend/`):

```bash
python -m scripts.create_admin
python -m scripts.create_clinician
python -m scripts.seed_test_data        # reads data/HyperSync_Test_Data.xlsx
python -m scripts.seed_demo_30_days     # 30 days of data for 7 demo patients + a clinician
python -m scripts.seed_demo_30_days --csv demo_out   # ...and CSV copies
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at http://localhost:5173. No `.env` is needed locally: the app calls the API
on port 8000 of whatever hostname it was opened on. If you set
`VITE_API_BASE_URL` (see `.env.example`), keep the hostname the same as the
app's: the login session is a `SameSite` cookie, and `localhost` and
`127.0.0.1` count as *different sites*, so mixing them logs you straight out.

### Deploying behind HTTPS

Set these in `backend/.env`; they control the refresh-token cookie:

| Variable | Value | Why |
| --- | --- | --- |
| `COOKIE_SECURE` | `true` | send the cookie over HTTPS only |
| `COOKIE_SAMESITE` | `lax` (same site) or `none` (frontend and API on different sites) | `none` requires `COOKIE_SECURE=true` |
| `CORS_ORIGINS` | your frontend origin(s) | credentialed requests need explicit origins, not `*` |

and `VITE_API_BASE_URL=https://your-api-host` when building the frontend.

## Sessions

The **access token** (30 min) lives only in JavaScript memory. The **refresh
token** (7 days) is an `httpOnly` cookie scoped to `/auth`, so page scripts
cannot read it, which limits what an XSS bug can steal. On load the app trades
the cookie for a fresh access token (`POST /auth/refresh`); a logged-out visitor
therefore sees one harmless 401 in the network tab. `/auth/refresh` and
`/auth/logout` also accept the token in the request body for non-browser API
clients.

## Checks

```bash
# backend (from backend/, with requirements-dev.txt installed)
pytest                      # no PostgreSQL or .env needed
ruff check . && ruff format --check .

# frontend (from frontend/)
npm run check               # lint + tests + production build + Bootstrap class check
```

The frontend tests also read the backend source to confirm that the BP
thresholds and the lifestyle-factor fields match on both sides.

## Conventions worth keeping

**Blood pressure thresholds live in two places and must agree.**
`backend/app/core/bp_classification.py` is authoritative;
`frontend/src/utils/bpStatus.js` mirrors it so the live preview on the
"Log reading" screen matches the status the API assigns. Change both.

**Role checks belong in the route signature**, not the body — use the
`require_patient` / `require_clinician` / `require_admin` dependencies from
`app/core/deps.py` so the rules appear in the OpenAPI docs.

**Pages fetch through `useAsync`**, which handles loading, errors, retries
and discards results that arrive after the component unmounts.

**Inline `style={{ … }}` is a smell.** Use the primitives in
`components/ui/`, or add a class to the components section of `theme.css`.

**Optional fields must be nullable all the way down.** The schema, the form
and the database column have to agree (pulse was once optional in the first two
and `NOT NULL` in the third). The API tests save a reading without a pulse.

**Dates are the user's local day.** In the browser use `toLocalDateInput()`;
never `toISOString().slice(0, 10)`, which is the UTC day and lags Kenya by 3
hours. Patient requests carry an `X-Timezone` header and trend endpoints group
readings with it (`get_timezone` in `app/core/deps.py`, falling back to UTC).
The patient's IANA timezone is also stored at registration, so clinician trend
and weekly-review views use the patient's calendar rather than the clinician's.

**Bootstrap is a custom build.** `src/bootstrap.scss` compiles only the
components and utility groups the app uses (about a third of stock Bootstrap's
size). If something renders unstyled after you add a component or class, add
its partial there; `npm run check:css` fails when the code uses a Bootstrap
class the build leaves out.

**Recommendations come from the log, not just the latest entry.** Ten
patient-facing habits can be logged: stress, sleep, diet, salt, caffeine,
alcohol, smoking, activity, **temperature** and **noise**. The check-in also
records medication use for the clinician-only treatment-review feature. That
information never appears in patient recommendations. Each reading can record
whether it was taken **rested** and **without coffee/tea, smoking or exercise
beforehand**. `app/core/factor_insights.py` holds the rules:

- every patient-facing habit has a risk rule *and* a concrete tip (a test fails
  if one is missing);
- a habit is raised when risky on the latest entry or on 2+ days in the period;
- when the patient's readings are clearly higher (5+ mmHg, 2+ days each side) on
  their risky days than on their other days, that is stated with the numbers;
  habits that always coincide are reported as one finding;
- if 2+ readings were hurried, that comes first (it can inflate every other
  number), with the size of the gap when there are good readings to compare;
- a patient who logs too sparsely is told exactly how many more days of both
  readings and logs unlock their own patterns;
- anything cut for space is named and retains its concrete action rather than
  being reduced to a label;
- low and very-high readings get safety wording only. No model estimate or
  lifestyle advice is attached.

**Recommendations are live.** `GET /recommendations/me` works the advice out from
the patient's data on every request (nothing is served from a cache, and the
response is `Cache-Control: no-store`), so a reading or lifestyle entry saved a
moment ago is already reflected. A history batch is stored only when the advice
actually changes, with an explicit `position` so the order never shuffles; the
newest 30 batches are kept. In the app, `RecommendationsContext` refetches after
every save or delete (the save screens wait for it, then open the
**Recommendations** tab with the fresh advice), when the browser tab regains
focus, and when the patient's other open tab saves something. The tab groups the
advice (where you stand / what your own data shows / what to work on / keep in
mind). Each item still carries source metadata in the API for auditability, but
the patient-facing cards do not show provenance tags. Needs `alembic upgrade head`.

**A lifestyle check-in is one day, not a stream of clicks.** The API rejects an
empty check-in, a future local date, and a second check-in for the same patient
on the same day (HTTP 409). The database enforces the same daily rule, and
legacy calculations count distinct days so duplicate rows cannot inflate
adherence or habit patterns.

**The survey estimate is qualified honestly.** Version 4 uses the STEPS
measurement weight, locked PSU-grouped splits, regularised logistic regression,
and validation-only Platt calibration. When age, sex or lifestyle inputs are
missing, the model uses its recorded training-population defaults and explicit
missingness flags. The patient-facing text names the defaulted fields and says
the estimate is not fully personalised. An unspecified sex is never presented
as the patient's own sex. Activity above the model's 240-minute training cap is
capped and the adjustment is disclosed. The estimate is omitted outside the
supported 18–69 range. Its two largest feature contributions include 95%
bootstrap ranges that resample both training and validation PSUs, and the text
says when a range crosses zero. Any displayed contribution based on a missing
input is labelled as missing information rather than as patient behaviour; the
overall estimate also names every defaulted field. If the
model artefact is missing, corrupt or incompatible, the endpoint still works from
readings and lifestyle rules and silently omits the population estimate rather
than failing. The optional bundle is loaded and validated during application
startup. A real loopback Uvicorn HTTP regression gate asserts that both the
first request and p95 stay below 300 ms without an LLM.

**Treatment-review flag (clinicians only).** `app/core/treatment_review.py`
splits the last 4 weeks into 7-day weeks and flags a patient whose weekly
average remains elevated/high in 3+ judgeable weeks (or sustained *low*). These
are application bands, not a configured clinical treatment target. It lists
what to confirm first (what medication use was actually recorded, were
readings taken properly, which lifestyle contributors are logged), and a
clinician can record a review, which pauses a matching flag for a 28-day
follow-up window. The adequacy of that window depends on the clinical context.
The flag never suggests a drug or dose and no patient endpoint returns it (a
test checks). The thresholds presented for review are listed on the clinical review sheet.
It needs the `treatment_reviews` table: run `alembic upgrade head`.

**Clinical wording is reviewable in one place.**
`docs/advice-for-clinical-review.md` collects the blood-pressure bands, habit
rules and concrete actions, measurement and personal-pattern thresholds, the
model context, and the clinician-only treatment-review rules. It is generated
(`cd backend && python -m scripts.export_advice`) and a test detects drift
between the generated sections and the code. That test does **not** verify
clinical review or sign-off. The current sheet is intentionally **unsigned**
and must not be described as clinically approved.

**The model has an explicit identity.** `backend/ml/models/MODEL_CARD.md` records
the feature contract, data provenance, thresholds, locked-test metrics, subgroup
results, calibration, contribution uncertainty, intended use, limitations,
version and SHA-256 checksum. `backend/ml/DATA_CARD.md` records data lineage,
cleaning, exclusions, weights, splits, and hashes. The runtime verifies the
published checksum before unpickling the artefact, then validates its version,
exact feature/input contract, defaults, labels, thresholds, calibration,
contribution arrays, effects, and provenance hashes before using it.
`SHA256SUMS` and the model tests keep the committed files consistent with that
identity. The model card does not claim clinical benefit. The plain-language
limits and ethics statement is in `docs/limitations-and-ethics.md`.

**Lists ask for what they show.** The dashboard fetches 5 readings plus a
`/readings/me/summary` count, not the whole history.

**Never commit `.env`.** `.env.example` documents the required variables.

## Presentation and demo

`docs/supervisor-presentation-guide.md` contains the supervisor demo sequence,
expected outcomes, evidence to show, limitations to state, and likely questions.
It is deliberately explicit that the application is manual-input only and that
the clinical wording remains unsigned.
