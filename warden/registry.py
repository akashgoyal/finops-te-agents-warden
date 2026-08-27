"""Agent registry: which agents exist, and what they're declared to be allowed to call.

Backed by Firestore in the cloud. Falls back to an in-memory store when no
GOOGLE_CLOUD_PROJECT is set, so you can develop the whole gateway locally
before ever touching GCP — see Day 1 of the checklist.
"""

from __future__ import annotations

from warden.config import get_settings
from warden.models import AgentScope

_COLLECTION = "agents"


class InMemoryRegistry:
    def __init__(self) -> None:
        self._store: dict[str, AgentScope] = {}

    def register(self, scope: AgentScope) -> None:
        self._store[scope.agent_id] = scope

    def get(self, agent_id: str) -> AgentScope | None:
        return self._store.get(agent_id)


class FirestoreRegistry:
    def __init__(self) -> None:
        from google.cloud import firestore  # imported lazily — optional dependency at runtime

        settings = get_settings()
        self._client = firestore.Client(
            project=settings.google_cloud_project,
            database=settings.firestore_database,
        )

    def register(self, scope: AgentScope) -> None:
        self._client.collection(_COLLECTION).document(scope.agent_id).set(scope.model_dump())

    def get(self, agent_id: str) -> AgentScope | None:
        doc = self._client.collection(_COLLECTION).document(agent_id).get()
        if not doc.exists:
            return None
        return AgentScope(**doc.to_dict())


def get_registry():
    settings = get_settings()
    if settings.google_cloud_project:
        return FirestoreRegistry()
    return InMemoryRegistry()
