"""Central config, loaded once from the environment (.env in local dev)."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemma_model: str = "gemma-4-4b-it"

    google_cloud_project: str = ""
    firestore_database: str = "(default)"

    warden_secret_key: str = "change-me-to-a-random-string"
    warden_stub_mode: bool = True

    port: int = 8080

    @property
    def stub_mode(self) -> bool:
        # Never call a paid/rate-limited model without a key — fall back to stubs.
        return self.warden_stub_mode or not self.google_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
