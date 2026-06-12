from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from app.api.v1 import router as v1_router
from app.web import router as web_router
from app.web.deps import NotAuthenticatedException

app = FastAPI(
    title="Tutor Hub API",
    description="API for managing tutors, students, sessions, and payments in the Tutor Hub application.",
    version="1.0.0",
)


@app.exception_handler(NotAuthenticatedException)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/login")


app.include_router(v1_router)
app.include_router(web_router)


@app.get("/health", tags=["Health Check"])
def health():  # pragma: no cover
    return {"status": "ok"}
