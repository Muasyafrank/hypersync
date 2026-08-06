from fastapi import FastAPI
from app.routers import auth,readings


app = FastAPI(title = "HyperSync API")
app.include_router(auth.router)
app.include_router(readings.router)
@app.get("/health")
def health_check():
    return {"status": "ok"}
