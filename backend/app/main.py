from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.ml_recommendation_engine import preload_model
from app.routers import alerts, auth, environmental_factor, readings, recommendations, treatment_review, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Validate the optional model bundle before serving requests. A missing or
    # invalid artefact is logged by preload_model and does not block startup.
    preload_model()
    yield


app = FastAPI(
    title="HyperSync API",
    description="Manual blood-pressure logging and clinician decision-support prototype.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    readings.router,
    users.router,
    environmental_factor.router,
    recommendations.router,
    alerts.router,
    treatment_review.router,
):
    app.include_router(router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
