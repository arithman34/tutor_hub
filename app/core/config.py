from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_prefix: str = "/api/v1"
    openai_api_key: str
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/calendar/callback"


settings = Settings()
