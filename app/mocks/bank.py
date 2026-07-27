"""MOCK bank / payment gateway.

Stands in for: a real core-banking system or payment processor (e.g. a card
network / ACH rail). Balances live in the local SQLite DB. This mock validates
funds, moves money between accounts, and returns realistic ISO-8583-style
status codes and a transaction reference.

Atomicity note: this method mutates balances on the shared db.session but does
NOT commit. The caller (payment service) commits the balance changes and the
Transaction audit row together, so either both persist or neither does.
"""
from __future__ import annotations

import secrets

from ..extensions import db
from ..models import BankAccount
from .interfaces import BankGateway, BankResult

# ISO-8583-flavoured response codes for realism.
CODE_APPROVED = "00"
CODE_INSUFFICIENT_FUNDS = "51"
CODE_INVALID_ACCOUNT = "14"
CODE_INVALID_AMOUNT = "13"


class MockBankGateway(BankGateway):
    def transfer(self, from_account: str, to_account: str, amount: float,
                 currency: str = "NGN") -> BankResult:
        ref = _reference()

        if amount <= 0:
            return BankResult(False, CODE_INVALID_AMOUNT, ref, "Invalid amount")

        src = BankAccount.query.filter_by(account_number=from_account).first()
        dst = BankAccount.query.filter_by(account_number=to_account).first()
        if src is None or dst is None:
            return BankResult(False, CODE_INVALID_ACCOUNT, ref, "Unknown account")

        if src.balance < amount:
            return BankResult(False, CODE_INSUFFICIENT_FUNDS, ref, "Insufficient funds")

        # MOCK settlement: debit source, credit destination (caller commits).
        src.balance = round(src.balance - amount, 2)
        dst.balance = round(dst.balance + amount, 2)
        return BankResult(True, CODE_APPROVED, ref, "Approved")


def _reference() -> str:
    """Realistic-looking, unique transaction reference (e.g. TXN-9F3A2B1C)."""
    return "TXN-" + secrets.token_hex(4).upper()
