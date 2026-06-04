"""
Phase 7 — in-memory async SSE broadcaster keyed by transaction_id.

Designed for single-process FastAPI deployments. For horizontal scale, replace
with Redis Pub/Sub while keeping the same publish/subscribe interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Set from FastAPI lifespan so BackgroundTasks can publish from sync workers.
_app_event_loop: asyncio.AbstractEventLoop | None = None


def bind_app_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _app_event_loop
    _app_event_loop = loop


class RealtimeBroadcaster:
    """Thread-safe async registry of per-transaction subscriber queues."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, transaction_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=32)
        async with self._lock:
            self._subscribers[transaction_id].add(queue)
        logger.debug("SSE subscriber added transaction_id=%s total=%s", transaction_id, len(self._subscribers[transaction_id]))
        return queue

    async def unsubscribe(self, transaction_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            subs = self._subscribers.get(transaction_id)
            if not subs:
                return
            subs.discard(queue)
            if not subs:
                del self._subscribers[transaction_id]
        logger.debug("SSE subscriber removed transaction_id=%s", transaction_id)

    async def publish(self, transaction_id: str, payload: dict[str, Any]) -> int:
        async with self._lock:
            queues = list(self._subscribers.get(transaction_id, ()))
        delivered = 0
        for queue in queues:
            try:
                queue.put_nowait(payload)
                delivered += 1
            except asyncio.QueueFull:
                logger.warning("SSE queue full — dropping event transaction_id=%s", transaction_id)
        if delivered:
            logger.info(
                "SSE event published transaction_id=%s event=%s subscribers=%s",
                transaction_id,
                payload.get("event"),
                delivered,
            )
        return delivered

    def publish_sync(self, transaction_id: str, payload: dict[str, Any]) -> None:
        """
        Publish from sync BackgroundTasks by scheduling on the bound app loop.
        """
        loop = _app_event_loop
        if loop is None or not loop.is_running():
            logger.warning("SSE publish skipped — app event loop not bound")
            return
        asyncio.run_coroutine_threadsafe(self.publish(transaction_id, payload), loop)


def format_sse_message(payload: dict[str, Any], *, event: str | None = None) -> str:
    """Serialize one Server-Sent Events frame."""
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
    lines.append("")
    return "\n".join(lines) + "\n"


# Process-wide singleton
broadcaster = RealtimeBroadcaster()