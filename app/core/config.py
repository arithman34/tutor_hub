from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_prefix: str = "/api/v1"


settings = Settings()
