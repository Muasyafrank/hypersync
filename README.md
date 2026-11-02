# HyperSync — Hypertension Patient Monitoring System

Final year project — Dedan Kimathi University of Technology.

HyperSync lets patients log blood pressure readings and daily lifestyle
factors, classifies each reading, tracks trends over time, raises alerts
for clinicians when a trend deteriorates, and generates recommendations
from a model trained on the Kenya STEPS 2015 NCD survey.

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
  ml/             STEPS data pipeline, training script, model artefacts
  scripts/        admin/clinician provisioning, test-data seeding
  data/           STEPS survey (.sav) and the seed workbook
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
| Clinician | View all patients, their readings, trends and lifestyle factors; work the alert queue |
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

cp .env.example .env        # then fill in DATABASE_URL and SECRET_KEY
alembic upgrade head
python -m ml.train_model    # needs data/2015_STEPS_Data.sav

uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

Provisioning and sample data (run from `backend/`):

```bash
python -m scripts.create_admin
python -m scripts.create_clinician
python -m scripts.seed_test_data        # reads data/HyperSync_Test_Data.xlsx
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
hours. On the API, every request carries an `X-Timezone` header and trend
endpoints group readings with it (`get_timezone` in `app/core/deps.py`,
falling back to UTC).

**Bootstrap is a custom build.** `src/bootstrap.scss` compiles only the
components and utility groups the app uses (about a third of stock Bootstrap's
size). If something renders unstyled after you add a component or class, add
its partial there; `npm run check:css` fails when the code uses a Bootstrap
class the build leaves out.

**Lists ask for what they show.** The dashboard fetches 5 readings plus a
`/readings/me/summary` count, not the whole history.

**Never commit `.env`.** `.env.example` documents the required variables.
