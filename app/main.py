from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.v1 import router as v1_router


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if "security" in operation:
                operation["security"].append({"BearerAuth": []})
    return schema


app = FastAPI(
    title="Tutor Hub API",
    description="API for managing tutors, students, sessions, and payments in the Tutor Hub application.",
    version="1.0.0",
)

app.openapi = custom_openapi

app.include_router(v1_router)


@app.get("/health", tags=["Health Check"])
def health():
    return {"status": "ok"}
