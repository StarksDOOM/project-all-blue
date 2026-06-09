"use client";

import type { ReactNode } from "react";
import { Check, FileText, Lock, Send } from "lucide-react";

import { LegalContractRecord } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface TransactionExecutionTimelineProps {
  contract: LegalContractRecord;
}

type StepState = "pending" | "active" | "complete";

interface PipelineStep {
  id: string;
  label: string;
  description: string;
  state: StepState;
  icon: ReactNode;
}

export function TransactionExecutionTimeline({
  contract,
}: TransactionExecutionTimelineProps) {
  const txn = contract.transaction;
  const isExecuted = txn?.status === "EXECUTED";
  const hasPdf = Boolean(contract.has_secure_pdf);
  const hasEnvelope = Boolean(contract.docusign_envelope_id);

  const steps: PipelineStep[] = [
    {
      id: "draft",
      label: "Draft Created",
      description: "Sesión de transacción iniciada",
      state: "complete",
      icon: <FileText className="h-4 w-4" />,
    },
    {
      id: "pdf",
      label: "PDF Sealed",
      description: hasPdf ? "Hash SHA-256 registrado" : "Pendiente de generación",
      state: hasPdf ? "complete" : txn?.status === "GENERATED" ? "active" : "pending",
      icon: <Lock className="h-4 w-4" />,
    },
    {
      id: "envelope",
      label: "DocuSign Envelope Generated",
      description: hasEnvelope
        ? `Sobre ${contract.docusign_envelope_id?.slice(0, 8)}…`
        : "Pendiente de envío a DocuSign",
      state: hasEnvelope ? "complete" : hasPdf ? "active" : "pending",
      icon: <Send className="h-4 w-4" />,
    },
    {
      id: "executed",
      label: "Fully Executed & Certified",
      description: isExecuted
        ? "Bloqueo seguro activo — certificado disponible"
        : "En espera de firmas",
      state: isExecuted ? "complete" : hasEnvelope ? "active" : "pending",
      icon: <Check className="h-4 w-4" />,
    },
  ];

  return (
    <nav
      aria-label="Transaction execution pipeline"
      className="rounded-lg border bg-card p-4 shadow-sm print:hidden"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Pipeline de ejecución</h2>
        {isExecuted ? (
          <Badge className="gap-1 bg-emerald-600 hover:bg-emerald-600">
            <Lock className="h-3 w-3" />
            Certificado
          </Badge>
        ) : (
          <Badge variant="secondary">{txn?.status ?? "DRAFT"}</Badge>
        )}
      </div>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={cn(
              "relative flex flex-col gap-2 rounded-md border p-3 transition-colors",
              step.state === "complete" && "border-emerald-500/40 bg-emerald-50/50",
              step.state === "active" && "border-primary/40 bg-primary/5",
              step.state === "pending" && "border-muted bg-muted/30 opacity-80"
            )}
          >
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border",
                  step.state === "complete" && "border-emerald-600 bg-emerald-600 text-white",
                  step.state === "active" && "border-primary bg-primary text-primary-foreground",
                  step.state === "pending" && "border-muted-foreground/30 text-muted-foreground"
                )}
              >
                {step.icon}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                {index + 1}/{steps.length}
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold leading-tight">{step.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </nav>
  );
}