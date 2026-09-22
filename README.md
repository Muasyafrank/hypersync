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
  scripts/        one-off admin/clinician provisioning

frontend/         React 19 + Vite + React-Bootstrap + Recharts
  src/
    api/          one module per backend resource; axios client with
                  automatic token refresh
    components/   shared components
      ui/         presentational primitives (Panel, StatCard, DataRow, …)
      admin/      admin dashboard modals
      lifestyle/  lifestyle wizard steps
    context/      auth, toast and confirm providers
    hooks/        useAsync, useForm
    pages/        one file per route
    utils/        formatting and BP classification helpers
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
pip install -r requirements.txt

cp .env.example .env        # then fill in DATABASE_URL and SECRET_KEY
alembic upgrade head
python -m ml.train_model    # needs data/2015_STEPS_Data.sav

uvicorn app.main:app --reload
```

API docs at http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_BASE_URL
npm run dev
```

App at http://localhost:5173

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

**Never commit `.env`.** `.env.example` documents the required variables.
