"""Write the demo fleet's scopes into Firestore, once, before your first
cloud deploy. Requires GOOGLE_CLOUD_PROJECT to be set (.env or environment)
and `gcloud auth application-default login` to have been run.

    python -m scripts.seed_registry
"""

from demo.scopes import DEMO_SCOPES
from warden.registry import FirestoreRegistry

if __name__ == "__main__":
    registry = FirestoreRegistry()
    for scope in DEMO_SCOPES:
        registry.register(scope)
        print(f"registered {scope.agent_id}: {scope.allowed_tools}")
