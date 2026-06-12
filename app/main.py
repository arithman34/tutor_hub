from fastapi import FastAPI

from app.api.v1 import router as v1_router

app = FastAPI(
    title="Tutor Hub API",
    description="API for managing tutors, students, sessions, and payments in the Tutor Hub application.",
    version="1.0.0",
)


app.include_router(v1_router)


@app.get("/health", tags=["Health Check"])
def health():  # pragma: no cover
    return {"status": "ok"}
