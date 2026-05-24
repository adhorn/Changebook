from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Changebook"
    debug: bool = False

    database_url: str = "postgresql://changebook:changebook@localhost:5432/changebook"

    # Organisation is the invisible tenant boundary.
    # Single-tenant by default. Users never see or interact with this.
    org_name: str = "Default"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_prefix": "CHANGEBOOK_", "env_file": ".env"}


settings = Settings()
