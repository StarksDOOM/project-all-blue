"use client";

import { useMutation } from "@tanstack/react-query";
import { ExternalLink, FileSignature } from "lucide-react";
import { useCallback, useState } from "react";

import { api } from "@/lib/api";
import type { SignatureRole } from "@/lib/transaction-types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface DocuSignEmbeddedSigningProps {
  transactionId: string;
  hasEnvelope: boolean;
  buyerSigned: boolean;
  sellerSigned: boolean;
  isExecuted: boolean;
  onEnvelopeCreated: () => void;
}

export function DocuSignEmbeddedSigning({
  transactionId,
  hasEnvelope,
  buyerSigned,
  sellerSigned,
  isExecuted,
  onEnvelopeCreated,
}: DocuSignEmbeddedSigningProps) {
  const [signingUrl, setSigningUrl] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const returnUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/dashboard/transactions/${transactionId}`
      : `http://localhost:3000/dashboard/transactions/${transactionId}`;

  const envelopeMutation = useMutation({
    mutationFn: () => api.createDocusignEnvelope(transactionId),
    onSuccess: () => {
      setActionError(null);
      onEnvelopeCreated();
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const signingUrlMutation = useMutation({
    mutationFn: (role: SignatureRole) =>
      api.getDocusignSigningUrl(transactionId, role, returnUrl),
    onSuccess: (data) => {
      setActionError(null);
      setSigningUrl(data.signing_url);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const openSigning = useCallback(
    (role: SignatureRole) => {
      signingUrlMutation.mutate(role);
    },
    [signingUrlMutation]
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <FileSignature className="h-5 w-5" />
          Firma embebida DocuSign
        </CardTitle>
        <CardDescription>
          Ejecución legal vía DocuSign Embedded Signing (JWT). El PDF sellado se envía como sobre.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasEnvelope ? (
          <Button
            type="button"
            onClick={() => envelopeMutation.mutate()}
            disabled={envelopeMutation.isPending || isExecuted}
          >
            {envelopeMutation.isPending ? "Creando sobre…" : "Enviar a DocuSign"}
          </Button>
        ) : (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              disabled={buyerSigned || signingUrlMutation.isPending || isExecuted}
              onClick={() => openSigning("BUYER")}
            >
              Firmar como Comprador (DocuSign)
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={sellerSigned || signingUrlMutation.isPending || isExecuted}
              onClick={() => openSigning("SELLER")}
            >
              Firmar como Vendedor (DocuSign)
            </Button>
          </div>
        )}

        {signingUrl ? (
          <div className="space-y-2">
            <Alert>
              <AlertTitle>Ceremonia de firma</AlertTitle>
              <AlertDescription>
                Complete la firma en el marco inferior. Al terminar, DocuSign redirige de vuelta al
                panel.
              </AlertDescription>
            </Alert>
            <iframe
              title="DocuSign Embedded Signing"
              src={signingUrl}
              className="h-[640px] w-full rounded-md border bg-white"
              allow="clipboard-read; clipboard-write"
            />
            <a
              href={signingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground underline"
            >
              Abrir en nueva pestaña <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        ) : null}

        {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
      </CardContent>
    </Card>
  );
}