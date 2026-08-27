"""Tamper-evident audit ledger.

Each record's hash covers its own fields plus the previous record's hash —
a simple hash chain. Anyone can walk the chain and confirm nothing in the
history was edited after the fact, without needing Cloud KMS or a paid
signing service. Backed by Firestore; falls back to an in-memory list
locally, same pattern as the registry.
"""

from __future__ import annotations

import hashlib
import json

from warden.config import get_settings
from warden.models import AuditRecord

_COLLECTION = "audit_log"


def _compute_hash(record: AuditRecord) -> str:
    payload = record.model_dump(exclude={"hash"})
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class InMemoryLedger:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> AuditRecord:
        record.prev_hash = self._records[-1].hash if self._records else ""
        record.hash = _compute_hash(record)
        self._records.append(record)
        return record

    def all(self) -> list[AuditRecord]:
        return list(self._records)


class FirestoreLedger:
    def __init__(self) -> None:
        from google.cloud import firestore

        settings = get_settings()
        self._client = firestore.Client(
            project=settings.google_cloud_project,
            database=settings.firestore_database,
        )
        self._col = self._client.collection(_COLLECTION)

    def _last_hash(self) -> str:
        docs = list(self._col.order_by("ts", direction="DESCENDING").limit(1).stream())
        if not docs:
            return ""
        return docs[0].to_dict().get("hash", "")

    def append(self, record: AuditRecord) -> AuditRecord:
        record.prev_hash = self._last_hash()
        record.hash = _compute_hash(record)
        self._col.add(record.model_dump())
        return record

    def all(self) -> list[AuditRecord]:
        docs = self._col.order_by("ts").stream()
        return [AuditRecord(**d.to_dict()) for d in docs]


def get_ledger():
    settings = get_settings()
    if settings.google_cloud_project:
        return FirestoreLedger()
    return InMemoryLedger()
