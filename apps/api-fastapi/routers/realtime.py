"""
Phase 7 — Server-Sent Events stream for transaction state updates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from database import get_db_session
from models import TransactionSession
from services.realtime_broadcaster import broadcaster, format_sse_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/transactions", tags=["realtime"])

KEEPALIVE_SECONDS = 25


def _verify_stream_access(
    session: Session,
    transaction_id: str,
    stream_token: str | None,
) -> TransactionSession:
    """
    Authorize SSE subscription.

    - Transaction must exist.
    - Optional ``stream_token`` query must match ``TRANSACTION_STREAM_TOKEN`` env when set.
    """
    import os

    transaction = session.get(TransactionSession, transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    required_token = os.getenv("TRANSACTION_STREAM_TOKEN", "").strip()
    if required_token:
        if not stream_token or stream_token != required_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid stream token")
    return transaction


async def _transaction_event_stream(transaction_id: str) -> AsyncIterator[str]:
    queue = await broadcaster.subscribe(transaction_id)
    try:
        yield format_sse_message(
            {"event": "CONNECTED", "transaction_id": transaction_id},
            event="connected",
        )
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                yield format_sse_message(payload, event=payload.get("event", "message").lower())
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        logger.debug("SSE stream cancelled transaction_id=%s", transaction_id)
        raise
    finally:
        await broadcaster.unsubscribe(transaction_id, queue)


@router.get("/{transaction_id}/stream")
async def stream_transaction_updates(
    transaction_id: str,
    stream_token: str | None = Query(default=None, alias="token"),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """
    Persistent SSE stream for a single transaction.

    Emits ``TRANSACTION_UPDATED`` when post-execution pipeline completes.
    """
    transaction = _verify_stream_access(session, transaction_id, stream_token)

    async def guarded_stream() -> AsyncIterator[str]:
        async for chunk in _transaction_event_stream(transaction.id):
            yield chunk

    return StreamingResponse(
        guarded_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )