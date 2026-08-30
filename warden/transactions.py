"""Transaction store — one record per trip run, not per call.

The audit ledger (warden/ledger.py) already tracks every individual call,
and is Firestore-backed — it survives a server restart. This used to be
in-memory only on every backend, which produced exactly the mismatch a
live user caught: the "Calls" stat (built from the persistent ledger)
kept climbing across restarts while the Transactions panel (built from
this store) reset to whatever ran since the last one. Firestore-backed
now, same pattern as the registry/ledger, so both views tell the same
story again — restart survives, counts stay aligned.

One real difference from the ledger: a Transaction's `steps` list grows
incrementally while a trip is in flight (warden/orchestrator.py appends
to it live). The in-memory store gets that for free — `start()` stores a
reference to the same object the orchestrator keeps mutating. Firestore
has no such thing as a live-mutating remote document; every append needs
an explicit `save()` call, which orchestrator.py now makes after each
step and once more at the end.
"""

from __future__ import annotations

from warden.config import get_settings
from warden.models import Transaction

_COLLECTION = "transactions"


class InMemoryTransactionStore:
    def __init__(self) -> None:
        self._transactions: dict[str, Transaction] = {}
        self._order: list[str] = []

    def start(self, txn: Transaction) -> None:
        self._transactions[txn.transaction_id] = txn
        self._order.append(txn.transaction_id)

    def save(self, txn: Transaction) -> None:
        # No-op: start() already stored a reference to this exact object,
        # so every mutation the orchestrator makes is already visible.
        # Kept as a real method (not omitted) so orchestrator.py can call
        # store.save(txn) unconditionally regardless of which store this is.
        pass

    def get(self, transaction_id: str) -> Transaction | None:
        return self._transactions.get(transaction_id)

    def all(self) -> list[Transaction]:
        return [self._transactions[tid] for tid in self._order]


class FirestoreTransactionStore:
    def __init__(self) -> None:
        from google.cloud import firestore

        settings = get_settings()
        self._client = firestore.Client(
            project=settings.google_cloud_project,
            database=settings.firestore_database,
        )
        self._col = self._client.collection(_COLLECTION)

    def start(self, txn: Transaction) -> None:
        self._col.document(txn.transaction_id).set(txn.model_dump(mode="json"))

    def save(self, txn: Transaction) -> None:
        self._col.document(txn.transaction_id).set(txn.model_dump(mode="json"))

    def get(self, transaction_id: str) -> Transaction | None:
        doc = self._col.document(transaction_id).get()
        return Transaction(**doc.to_dict()) if doc.exists else None

    def all(self) -> list[Transaction]:
        # Capped, unlike the ledger's own all() — a running demo/live
        # deployment shouldn't pull an unbounded history on every page
        # load. Newest first; the dashboard re-sorts client-side anyway.
        docs = self._col.order_by("start_ts", direction="DESCENDING").limit(500).stream()
        return [Transaction(**d.to_dict()) for d in docs]


_store = None


def get_store():
    global _store
    if _store is not None:
        return _store
    settings = get_settings()
    _store = FirestoreTransactionStore() if settings.google_cloud_project else InMemoryTransactionStore()
    return _store
