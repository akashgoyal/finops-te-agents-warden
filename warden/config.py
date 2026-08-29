"""Central config, loaded once from the environment (.env in local dev)."""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "ollama" (local, free, default — get this working first) | "gemini"
    # (cloud, Gemini Developer API / AI Studio key, free tier) | "vertex"
    # (cloud, Vertex AI + Model Armor prompt/response screening — needs a
    # billed project, no AI-Studio-style free tier; see .env.example)
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
    # Pinned, not gemini-flash-latest — see .env.example for why (the
    # rolling alias hit 504 DEADLINE_EXCEEDED on 11/11 live reviewer calls;
    # this pinned version hit 0 across repeated local verification).
    gemini_model: str = "gemini-3.5-flash"
    # Verified against the live API (client.models.list()), not assumed —
    # gemma-4-4b-it/12b-it aren't actually exposed on this API version,
    # only gemma-4-26b-a4b-it and gemma-4-31b-it are. This is the smaller
    # of the two: a mixture-of-experts model, ~4B active params despite
    # the 26B total, so it still fits "cheapest that works" for triage.
    gemma_model: str = "gemma-4-26b-a4b-it"  # used only once model_backend == "gemini"

    google_cloud_project: str = ""
    firestore_database: str = "(default)"

    # Only used when model_backend == "vertex". Deliberately separate from
    # gemini_model: verified live via client.models.list() against this
    # project's Vertex AI catalog that gemini-3.5-flash (and every other
    # 3.x model) 404s here — "Publisher model ... was not found or your
    # project does not have access to it" — while gemini-2.5-flash works.
    # AI Studio (the "gemini" backend, gemini_model above) has broader
    # default access and is what's actually deployed; this is a proven,
    # working proof-of-concept for the Vertex AI + Model Armor path, not
    # the primary submission path — see README.
    vertex_gemini_model: str = "gemini-2.5-flash"

    # Only used when model_backend == "vertex". us-central1 is one of Model
    # Armor's four supported Vertex AI integration regions as of this
    # writing (us-central1, us-east4, us-west1, europe-west4) — matches
    # where Firestore/Cloud Run are already provisioned in this project.
    vertex_location: str = "us-central1"
    # Resource names of pre-created Model Armor templates, e.g.
    # "projects/P/locations/us-central1/templates/warden-prompt". Created
    # once via scripts/setup_model_armor.sh, not by application code —
    # Model Armor has no free tier, so this stays opt-in and unset by
    # default even when model_backend == "vertex" (empty means "call
    # Vertex AI's Gemini without Model Armor screening attached").
    model_armor_prompt_template: str = ""
    model_armor_response_template: str = ""

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
        if self.model_backend == "gemini" and not self.google_api_key:
            return True
        # Vertex AI auths via ADC (no API key), but still needs a project —
        # same fail-closed reasoning as the Gemini branch above.
        if self.model_backend == "vertex" and not self.google_cloud_project:
            return True
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
