"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileCheck, Lock, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/api";
import { LegalContractRecord } from "@/lib/types";
import type { SignatureRole } from "@/lib/transaction-types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface TransactionSigningPanelProps {
  contract: LegalContractRecord;
  transactionId: string;
}

export function TransactionSigningPanel({
  contract,
  transactionId,
}: TransactionSigningPanelProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const txn = contract.transaction;
  const isLocked =
    txn.is_locked ?? (txn.status === "GENERATED" || txn.status === "EXECUTED");
  const hasPdf = contract.has_secure_pdf;
  const buyerSigned = Boolean(txn.buyer_signed_at);
  const sellerSigned = Boolean(txn.seller_signed_at);
  const isExecuted = txn.status === "EXECUTED";

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["transaction-contract", transactionId] });
  };

  const pdfMutation = useMutation({
    mutationFn: () => api.generateTransactionPdf(transactionId),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const signMutation = useMutation({
    mutationFn: (role: SignatureRole) => api.executeTransactionSignature(transactionId, role),
    onSuccess: () => {
      setActionError(null);
      invalidate();
    },
    onError: (error: Error) => setActionError(error.message),
  });

  return (
    <div className="space-y-4 print:hidden">
      {isLocked ? (
        <Alert variant="destructive" className="border-amber-500/50 bg-amber-50 text-amber-950">
          <Lock className="h-4 w-4" />
          <AlertTitle>Documento bloqueado criptográficamente</AlertTitle>
          <AlertDescription>
            No se permiten modificaciones post-firma. Los términos y partes quedan congelados
            en el estado registrado.
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="h-5 w-5" />
            Panel de ejecución digital
          </CardTitle>
          <CardDescription>
            Firma multiparte sin proveedores externos. Requiere PDF sellado con hash SHA-256.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <LockedField label="Comprador" value={txn.buyer_name} locked={isLocked} />
            <LockedField label="Cédula comprador" value={txn.buyer_id_doc} locked={isLocked} />
            <LockedField label="Vendedor" value={txn.seller_name} locked={isLocked} />
            <LockedField label="Cédula vendedor" value={txn.seller_id_doc} locked={isLocked} />
            <LockedField
              label="Precio pactado"
              value={`${txn.agreed_price.toLocaleString("en-US")} ${txn.currency}`}
              locked={isLocked}
            />
            <div className="space-y-2">
              <Label>Estado</Label>
              <Badge variant={isExecuted ? "default" : "secondary"} className="w-fit">
                {txn.status}
              </Badge>
            </div>
          </div>

          {contract.document_hash ? (
            <p className="font-mono text-xs text-muted-foreground break-all">
              Hash PDF (SHA-256): {contract.document_hash}
            </p>
          ) : null}

          {!hasPdf ? (
            <Button
              type="button"
              onClick={() => pdfMutation.mutate()}
              disabled={pdfMutation.isPending || txn.status !== "GENERATED"}
            >
              <FileCheck className="mr-2 h-4 w-4" />
              {pdfMutation.isPending ? "Generando PDF…" : "Generar PDF seguro"}
            </Button>
          ) : (
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="default"
                disabled={buyerSigned || signMutation.isPending || isExecuted}
                onClick={() => signMutation.mutate("BUYER")}
              >
                Firmar como Comprador
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={sellerSigned || signMutation.isPending || isExecuted}
                onClick={() => signMutation.mutate("SELLER")}
              >
                Firmar como Vendedor
              </Button>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/v1/transactions/${transactionId}/contract/pdf`}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(buttonVariants({ variant: "outline" }))}
              >
                Descargar PDF
              </a>
            </div>
          )}

          {actionError ? (
            <p className="text-sm text-destructive">{actionError}</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function LockedField({
  label,
  value,
  locked,
}: {
  label: string;
  value: string;
  locked: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <Input value={value} disabled={locked} readOnly className={locked ? "opacity-70" : ""} />
    </div>
  );
}