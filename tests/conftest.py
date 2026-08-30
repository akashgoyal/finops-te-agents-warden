"""Forces every test onto in-memory storage, regardless of .env.

WARDEN_STUB_MODE only stubs model calls (triage/review) — it says
nothing about storage. warden/registry.py, ledger.py, and
transactions.py each independently check GOOGLE_CLOUD_PROJECT and
connect to real Firestore whenever it's set, which .env has been for
every cloud-deployment task this project has done since. Without this,
running the "no GCP, no network calls" test suite quietly writes to
the same live Firestore project the deployed service reads from —
found live: cleared audit_log/transactions data kept reappearing after
every clear, and it traced back to this test suite's own runs (a
ghost_agent/$5,000/$310 test fixture trio showed up in production,
none of which came from a real demo trip), not anything from the
deployed dashboard.

This has to run before warden.config.get_settings() is called
anywhere. conftest.py is imported by pytest before test modules are
collected, which is what actually guarantees the ordering here —
get_settings() is @lru_cache'd process-wide, so whichever value it
resolves on first call wins for the entire test run, no matter what
any individual test file does afterward.
"""

import os

os.environ["GOOGLE_CLOUD_PROJECT"] = ""
os.environ.setdefault("WARDEN_STUB_MODE", "true")
