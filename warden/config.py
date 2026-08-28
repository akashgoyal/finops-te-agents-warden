"""Central config, loaded once from the environment (.env in local dev)."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "ollama" (local, free, default — get this working first) | "gemini" (cloud)
    model_backend: str = "ollama"

    ollama_host: str = "http://localhost:11434"
    # Small on purpose, and both already common in a local Ollama library —
    # no multi-GB pull needed before you can see this run. Swap freely.
    ollama_triage_model: str = "gemma2:2b"
    # Tested, not assumed: gemma2:2b as reviewer aborted 3 real orchestrated
    # trips in a row on hallucinated blocks of legitimately in-scope calls
    # (flights.hold, hotel.hold). llama3.1:8b — same machine, no download,
    # still small relative to any cloud model — ran the full 9-step trip,
    # including the orchestrator's retry-after-block, with zero flakiness.
    # Keep review a size class above triage; that gap is the point of triage.
    ollama_review_model: str = "llama3.1:8b"

    google_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    # Verified against the live API (client.models.list()), not assumed —
    # gemma-4-4b-it/12b-it aren't actually exposed on this API version,
    # only gemma-4-26b-a4b-it and gemma-4-31b-it are. This is the smaller
    # of the two: a mixture-of-experts model, ~4B active params despite
    # the 26B total, so it still fits "cheapest that works" for triage.
    gemma_model: str = "gemma-4-26b-a4b-it"  # used only once model_backend == "gemini"

    google_cloud_project: str = ""
    firestore_database: str = "(default)"

    warden_secret_key: str = "change-me-to-a-random-string"
    # Deterministic, zero-model fallback — for tests/CI, not for seeing it work.
    warden_stub_mode: bool = False

    port: int = 8080

    @property
    def stub_mode(self) -> bool:
        if self.warden_stub_mode:
            return True
        # Never call the Gemini backend without a key — fail closed to stub,
        # not to a crash. Ollama needs no key, so this doesn't touch it.
        return self.model_backend == "gemini" and not self.google_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
