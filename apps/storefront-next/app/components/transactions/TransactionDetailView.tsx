"use client";

import { Suspense } from "react";
import { useQuery } from "@tanstack/react-query";

import { useTransactionRealtime } from "@/hooks/useTransactionRealtime";
import { api } from "@/lib/api";
import { transactionKeys } from "@/lib/query-keys";
import { ContractMarkdownPreview } from "@/components/transactions/ContractMarkdownPreview";
import { TransactionAuditActions } from "@/components/transactions/TransactionAuditActions";
import { TransactionExecutionTimeline } from "@/components/transactions/TransactionExecutionTimeline";
import { TransactionHeaderActions } from "@/components/transactions/TransactionHeaderActions";
import {
  AuditActionsSkeleton,
  SigningPanelSkeleton,
  TimelineSkeleton,
} from "@/components/transactions/skeletons/TransactionDetailSkeletons";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import dynamic from "next/dynamic";

const TransactionSigningPanel = dynamic(
  () =>
    import("@/components/transactions/TransactionSigningPanel").then(
      (mod) => mod.TransactionSigningPanel
    ),
  { loading: () => <SigningPanelSkeleton /> }
);

interface TransactionDetailViewProps {
  transactionId: string;
}

/** Client island — hydrated query, SSE, interactive workflow (no RSC imports). */
export function TransactionDetailView({ transactionId }: TransactionDetailViewProps) {
  useTransactionRealtime(transactionId);

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: transactionKeys.contract(transactionId),
    queryFn: () => api.getTransactionContract(transactionId),
    enabled: Boolean(transactionId),
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-end print:hidden">
        <TransactionHeaderActions
          transactionId={transactionId}
          documentBody={data?.document_body}
        />
      </div>

      {isLoading && !data ? (
        <p className="text-sm text-muted-foreground">Sincronizando contrato…</p>
      ) : null}

      {isError ? (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle>Error al cargar el contrato</CardTitle>
            <CardDescription>
              {error instanceof Error ? error.message : "Error desconocido"}
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {data ? (
        <>
          <Suspense fallback={<TimelineSkeleton />}>
            <TransactionExecutionTimeline contract={data} />
          </Suspense>

          <Suspense fallback={<AuditActionsSkeleton />}>
            <TransactionAuditActions contract={data} transactionId={transactionId} />
          </Suspense>

          <Suspense fallback={<SigningPanelSkeleton />}>
            <TransactionSigningPanel contract={data} transactionId={transactionId} />
          </Suspense>

          <ContractMarkdownPreview
            title={data.property.title}
            remoteId={data.property.remote_id}
            buyerName={data.transaction?.buyer_name ?? ""}
            sellerName={data.transaction?.seller_name ?? ""}
            status={data.transaction?.status ?? "DRAFT"}
            documentBody={data.document_body}
          />
        </>
      ) : null}

      {isFetching && data ? (
        <p className="text-xs text-muted-foreground print:hidden" aria-live="polite">
          Actualizando…
        </p>
      ) : null}
    </div>
  );
}