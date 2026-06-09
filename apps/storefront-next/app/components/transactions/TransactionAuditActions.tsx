"use client";

import { FileText, ShieldCheck } from "lucide-react";

import { api } from "@/lib/api";
import { LegalContractRecord } from "@/lib/types";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface TransactionAuditActionsProps {
  contract: LegalContractRecord;
  transactionId: string;
}

export function TransactionAuditActions({
  contract,
  transactionId,
}: TransactionAuditActionsProps) {
  const isExecuted = contract.transaction?.status === "EXECUTED";

  if (!isExecuted) {
    return null;
  }

  const auditUrl = api.auditCertificateDownloadUrl(transactionId);

  return (
    <section
      className="flex flex-col gap-3 rounded-lg border border-emerald-500/30 bg-emerald-50/40 p-4 sm:flex-row sm:items-center sm:justify-between print:hidden"
      aria-label="Post-execution audit evidence"
    >
      <div className="space-y-1">
        <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
          <ShieldCheck className="h-4 w-4" />
          Transacción certificada
        </p>
        <p className="text-xs text-emerald-900/80">
          Descargue el Certificado de Ejecución Digital emitido tras el cierre DocuSign.
        </p>
      </div>
      <a
        href={auditUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(buttonVariants({ variant: "default" }), "shrink-0 gap-2")}
      >
        <FileText className="h-4 w-4" />
        Descargar Certificado de Auditoría
      </a>
    </section>
  );
}