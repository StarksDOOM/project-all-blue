"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const STREAM_TOKEN = process.env.NEXT_PUBLIC_TRANSACTION_STREAM_TOKEN;

export type TransactionRealtimeEvent = {
  event: string;
  transaction_id: string;
  status?: string;
  has_audit_certificate?: boolean;
};

function buildStreamUrl(transactionId: string): string {
  const base = `${BASE_URL}/api/v1/transactions/${encodeURIComponent(transactionId)}/stream`;
  if (!STREAM_TOKEN) {
    return base;
  }
  const params = new URLSearchParams({ token: STREAM_TOKEN });
  return `${base}?${params.toString()}`;
}

/**
 * Subscribes to backend SSE for a transaction detail view.
 * Invalidates React Query cache on TRANSACTION_UPDATED (no full page reload).
 */
export function useTransactionRealtime(transactionId: string | undefined) {
  const queryClient = useQueryClient();
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!transactionId) {
      return;
    }

    const url = buildStreamUrl(transactionId);
    const source = new EventSource(url);
    sourceRef.current = source;

    const handlePayload = (raw: string) => {
      try {
        const payload = JSON.parse(raw) as TransactionRealtimeEvent;
        if (
          payload.event === "TRANSACTION_UPDATED" &&
          payload.transaction_id === transactionId
        ) {
          queryClient.invalidateQueries({
            queryKey: ["transaction-contract", transactionId],
          });
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    source.addEventListener("transaction_updated", (message) => {
      handlePayload(message.data);
    });

    source.onmessage = (message) => {
      handlePayload(message.data);
    };

    source.onerror = () => {
      /* EventSource auto-reconnects; avoid tight error loops in UI */
    };

    return () => {
      source.close();
      sourceRef.current = null;
    };
  }, [transactionId, queryClient]);
}