"""Transaction store — one record per trip run, not per call.

The audit ledger (warden/ledger.py) already tracks every individual call.
This tracks the thing a Finance Ops team actually thinks in: one booking
attempt, when it started, what order agents actually ran in, when — or
whether — it finished. In-memory for now, same as the registry/ledger's
local-dev fallback; the natural next step is a Firestore collection,
keyed the same way.
"""

from __future__ import annotations

from warden.models import Transaction


class InMemoryTransactionStore:
    def __init__(self) -> None:
        self._transactions: dict[str, Transaction] = {}
        self._order: list[str] = []

    def start(self, txn: Transaction) -> None:
        self._transactions[txn.transaction_id] = txn
        self._order.append(txn.transaction_id)

    def get(self, transaction_id: str) -> Transaction | None:
        return self._transactions.get(transaction_id)

    def all(self) -> list[Transaction]:
        return [self._transactions[tid] for tid in self._order]


_store = InMemoryTransactionStore()


def get_store() -> InMemoryTransactionStore:
    return _store
