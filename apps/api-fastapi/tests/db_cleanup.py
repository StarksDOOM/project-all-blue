"""FK-safe teardown helpers for integration tests touching ``transaction_sessions``."""

from __future__ import annotations

from sqlmodel import Session, select

from models import LegalContract, PropertyListing, TransactionSession


def delete_transaction_cascade(session: Session, transaction_id: str) -> None:
    """Remove one transaction session and its legal contracts (keep the property)."""
    contracts = session.exec(
        select(LegalContract).where(LegalContract.transaction_session_id == transaction_id)
    ).all()
    for contract in contracts:
        session.delete(contract)

    txn = session.get(TransactionSession, transaction_id)
    if txn is not None:
        session.delete(txn)
    session.commit()


def delete_property_cascade(session: Session, *, property_id: str | None = None, remote_id: str | None = None) -> None:
    """Remove legal contracts, transaction sessions, then the property row."""
    listing: PropertyListing | None = None
    if property_id:
        listing = session.get(PropertyListing, property_id)
    if listing is None and remote_id:
        listing = session.exec(
            select(PropertyListing).where(PropertyListing.remote_id == remote_id)
        ).first()
    if listing is None:
        return

    transactions = session.exec(
        select(TransactionSession).where(TransactionSession.property_id == listing.id)
    ).all()
    for txn in transactions:
        for contract in session.exec(
            select(LegalContract).where(LegalContract.transaction_session_id == txn.id)
        ).all():
            session.delete(contract)
        session.delete(txn)

    session.flush()
    session.delete(listing)
    session.commit()