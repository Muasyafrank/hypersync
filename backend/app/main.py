from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import alerts, auth, environmental_factor, readings, recommendations, users

app = FastAPI(
    title="HyperSync API",
    description="Blood pressure monitoring and hypertension management platform.",
    version="1.0.0",
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
):
    app.include_router(router)


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
