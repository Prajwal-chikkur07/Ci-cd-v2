from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    github_token: str = ""
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cicd_orchestrator"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def async_database_url(self) -> str:
        """Ensure the database URL uses asyncpg driver (Render provides plain postgresql://)."""
        url = self.database_url
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
