"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Printer } from "lucide-react";

import { TransactionAuditActions } from "@/components/transactions/TransactionAuditActions";
import { TransactionExecutionTimeline } from "@/components/transactions/TransactionExecutionTimeline";
import { TransactionSigningPanel } from "@/components/transactions/TransactionSigningPanel";
import { api } from "@/lib/api";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export default function TransactionContractPreviewPage() {
  const params = useParams<{ id: string }>();
  const transactionId = params.id;
  const printRef = useRef<HTMLElement>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["transaction-contract", transactionId],
    queryFn: () => api.getTransactionContract(transactionId),
    enabled: Boolean(transactionId),
  });

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handleDownload = useCallback(() => {
    if (!data?.document_body) return;
    const blob = new Blob([data.document_body], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `promesa-venta-${transactionId}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [data?.document_body, transactionId]);

  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8 print:bg-white print:p-0">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between print:hidden">
          <div>
            <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
              ← Inventario
            </Link>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              Vista previa del contrato
            </h1>
            <p className="text-sm text-muted-foreground">
              Transacción {transactionId}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={handlePrint}>
              <Printer className="mr-2 h-4 w-4" />
              Imprimir
            </Button>
            <Button type="button" onClick={handleDownload} disabled={!data}>
              <Download className="mr-2 h-4 w-4" />
              Descargar .md
            </Button>
          </div>
        </div>

        {isLoading ? (
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-72" />
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </CardContent>
          </Card>
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
            <TransactionExecutionTimeline contract={data} />
            <TransactionAuditActions contract={data} transactionId={transactionId} />
            <TransactionSigningPanel contract={data} transactionId={transactionId} />
          </>
        ) : null}

        {data ? (
          <Card className="print:border-0 print:shadow-none">
            <CardHeader className="print:hidden">
              <CardTitle>{data.property.title}</CardTitle>
              <CardDescription>
                #{data.property.remote_id} · {data.transaction.buyer_name} →{" "}
                {data.transaction.seller_name} · Estado {data.transaction.status}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <article
                ref={printRef}
                className="prose prose-slate dark:prose-invert max-w-none rounded-lg border bg-white p-6 text-sm leading-relaxed shadow-sm print:border-0 print:shadow-none"
              >
                <ContractMarkdownBody body={data.document_body} />
              </article>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </main>
  );
}

function ContractMarkdownBody({ body }: { body: string }) {
  const lines = body.split("\n");
  return (
    <div className="space-y-2 font-sans text-slate-900">
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (trimmed.startsWith("# ")) {
          return (
            <h1 key={index} className="text-2xl font-bold tracking-tight">
              {trimmed.replace(/^#\s+/, "")}
            </h1>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h2 key={index} className="mt-6 text-lg font-semibold">
              {trimmed.replace(/^##\s+/, "")}
            </h2>
          );
        }
        if (trimmed.startsWith("---")) {
          return <hr key={index} className="my-4 border-slate-200" />;
        }
        if (trimmed.startsWith("|")) {
          return (
            <p key={index} className="font-mono text-xs text-slate-700">
              {line}
            </p>
          );
        }
        if (!trimmed) {
          return <div key={index} className="h-2" />;
        }
        const boldRendered = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        return (
          <p
            key={index}
            className="text-sm text-slate-800"
            dangerouslySetInnerHTML={{ __html: boldRendered }}
          />
        );
      })}
    </div>
  );
}