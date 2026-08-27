"""One cheap call to each real model, before you trust WARDEN_STUB_MODE=false
for the full demo. Confirms your API key and both model IDs actually work.

    python -m scripts.smoke_test_models
"""

from warden.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.google_api_key:
        raise SystemExit("GOOGLE_API_KEY is empty — set it in .env first.")

    from google import genai

    client = genai.Client(api_key=settings.google_api_key)

    for label, model in [("GEMINI_MODEL", settings.gemini_model), ("GEMMA_MODEL", settings.gemma_model)]:
        print(f"--- {label} = {model} ---")
        try:
            resp = client.models.generate_content(
                model=model, contents="Reply with exactly one word: OK"
            )
            print(f"  ok: {resp.text!r}")
        except Exception as exc:
            print(f"  FAILED: {exc}")
            print(
                "  If this is a 404/NOT_FOUND, the model id is stale — run "
                "client.models.list() or check https://ai.google.dev/gemini-api/docs/models"
            )


if __name__ == "__main__":
    main()
