"""FastAPI application for MachineMind."""
from fastapi import FastAPI

app = FastAPI(
    title="MachineMind API",
    description="Backend for machine-sound anomaly detection.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """Report that the backend is running."""
    return {"status": "ok"}
