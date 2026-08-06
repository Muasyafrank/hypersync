from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth,readings


app = FastAPI(title = "HyperSync API")
app.include_router(auth.router)
app.include_router(readings.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}
