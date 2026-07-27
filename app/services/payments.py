"""Payment authorization + settlement.

Flow: authenticated user authorizes a transfer to a merchant. We (1) run
multimodal auth, (2) if accepted, call the mock bank to move funds, and (3)
persist a Transaction row. Steps 2 and 3 commit together so balances and the
audit record stay consistent (atomic).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..extensions import db
from ..models import Merchant, Transaction, User, log_event
from ..mocks import bank_gateway
from . import auth as auth_service


@dataclass
class PaymentResult:
    ok: bool
    status: str          # APPROVED | DECLINED | AUTH_FAILED
    reference: str
    message: str
    transaction: Transaction | None


_AUTH_METHOD = {"face": "face", "fingerprint": "fingerprint", "both": "face+fingerprint"}


def authorize_payment(
    user: User,
    merchant: Merchant,
    amount: float,
    *,
    modality: str = "both",
    face_image: bytes | None = None,
    fingerprint_image: bytes | None = None,
) -> PaymentResult:
    """Authenticate with real captures, then (on success) settle via the mock bank."""
    auth_method = _AUTH_METHOD.get(modality, "face+fingerprint")

    # Step 1: biometric authorization. This commits its own AuthAttempt row.
    outcome = auth_service.authenticate(
        user,
        modality=modality,
        face_image=face_image,
        fingerprint_image=fingerprint_image,
        attempt_type="live",
    )

    if not outcome.accepted:
        txn = Transaction(
            reference=_pending_ref(),
            user_id=user.id,
            merchant_id=merchant.id,
            amount=amount,
            currency=user.account.currency if user.account else "NGN",
            status="AUTH_FAILED",
            status_code="AUTH",
            auth_method=auth_method,
            detail=outcome.detail,
        )
        db.session.add(txn)
        log_event("WARN", "payment",
                  f"Payment AUTH_FAILED [{auth_method}]: {user.username} -> {merchant.name} "
                  f"NGN {amount:,.2f} ({outcome.detail})")
        db.session.commit()
        return PaymentResult(False, "AUTH_FAILED", txn.reference,
                             f"Authentication failed: {outcome.detail}", txn)

    # Step 2: settlement via the MOCK bank (mutates balances, no commit yet).
    result = bank_gateway().transfer(
        from_account=user.account.account_number,
        to_account=merchant.account.account_number,
        amount=amount,
        currency=user.account.currency,
    )

    status = "APPROVED" if result.approved else "DECLINED"
    txn = Transaction(
        reference=result.reference,
        user_id=user.id,
        merchant_id=merchant.id,
        amount=amount,
        currency=user.account.currency,
        status=status,
        status_code=result.status_code,
        auth_method=auth_method,
        detail=result.message,
    )
    db.session.add(txn)

    # Step 3: commit balance changes + transaction record together (atomic).
    log_event("INFO" if result.approved else "WARN", "payment",
              f"Payment {status} ({result.status_code}) [{auth_method}]: {user.username} -> "
              f"{merchant.name} NGN {amount:,.2f} ref={result.reference}")
    db.session.commit()

    return PaymentResult(result.approved, status, result.reference, result.message, txn)


def _pending_ref() -> str:
    import secrets

    return "TXN-" + secrets.token_hex(4).upper()
