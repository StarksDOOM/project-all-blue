"use client";

import { useCallback } from "react";
import { Download, Printer } from "lucide-react";

import { Button } from "@/components/ui/button";

interface TransactionHeaderActionsProps {
  transactionId: string;
  documentBody?: string;
}

/** Client leaf — print/download handlers only. */
export function TransactionHeaderActions({
  transactionId,
  documentBody,
}: TransactionHeaderActionsProps) {
  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handleDownload = useCallback(() => {
    if (!documentBody) return;
    const blob = new Blob([documentBody], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `promesa-venta-${transactionId}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [documentBody, transactionId]);

  return (
    <div className="flex flex-wrap gap-2 print:hidden">
      <Button type="button" variant="outline" onClick={handlePrint}>
        <Printer className="mr-2 h-4 w-4" />
        Imprimir
      </Button>
      <Button type="button" onClick={handleDownload} disabled={!documentBody}>
        <Download className="mr-2 h-4 w-4" />
        Descargar .md
      </Button>
    </div>
  );
}