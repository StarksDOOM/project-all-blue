import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface TransactionDetailHeaderProps {
  transactionId: string;
}

/** RSC shell — title block without client interactivity. */
export function TransactionDetailHeader({ transactionId }: TransactionDetailHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between print:hidden">
      <div>
        <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
          ← Inventario
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          Vista previa del contrato
        </h1>
        <p className="text-sm text-muted-foreground">Transacción {transactionId}</p>
      </div>
    </div>
  );
}