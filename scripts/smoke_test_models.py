"""One cheap call to each model Warden is configured to use, before you
trust a full demo run. Works for both backends:

    python -m scripts.smoke_test_models
"""

from warden.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"MODEL_BACKEND = {settings.model_backend}\n")

    if settings.model_backend == "ollama":
        _check_ollama(settings.ollama_triage_model, "OLLAMA_TRIAGE_MODEL")
        _check_ollama(settings.ollama_review_model, "OLLAMA_REVIEW_MODEL")
        return

    if not settings.google_api_key:
        raise SystemExit("GOOGLE_API_KEY is empty — set it in .env first.")
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    for label, model in [("GEMINI_MODEL", settings.gemini_model), ("GEMMA_MODEL", settings.gemma_model)]:
        print(f"--- {label} = {model} ---")
        try:
            resp = client.models.generate_content(model=model, contents="Reply with exactly one word: OK")
            print(f"  ok: {resp.text!r}")
        except Exception as exc:
            print(f"  FAILED: {exc}")


def _check_ollama(model: str, label: str) -> None:
    import httpx

    settings = get_settings()
    print(f"--- {label} = {model} (via {settings.ollama_host}) ---")
    try:
        resp = httpx.post(
            f"{settings.ollama_host}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly one word: OK"}],
                "stream": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        print(f"  ok: {resp.json()['message']['content']!r}")
    except httpx.ConnectError:
        print(f"  FAILED: can't reach Ollama at {settings.ollama_host} — is `ollama serve` running?")
    except Exception as exc:
        print(f"  FAILED: {exc}")
        print(f"  If this is a 404, pull the model first: ollama pull {model}")


if __name__ == "__main__":
    main()
