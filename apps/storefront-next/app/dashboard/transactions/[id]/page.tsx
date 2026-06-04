import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import { TransactionDetailHeader } from "@/components/transactions/TransactionDetailHeader";
import { TransactionDetailView } from "@/components/transactions/TransactionDetailView";
import { getQueryClient } from "@/lib/get-query-client";
import { signingKeys, transactionKeys } from "@/lib/query-keys";
import { fetchSigningConfig, fetchTransactionContract } from "@/lib/server-api";

interface TransactionDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function TransactionDetailPage({ params }: TransactionDetailPageProps) {
  const { id: transactionId } = await params;
  const queryClient = getQueryClient();

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: transactionKeys.contract(transactionId),
      queryFn: () => fetchTransactionContract(transactionId),
    }),
    queryClient.prefetchQuery({
      queryKey: signingKeys.config(),
      queryFn: () => fetchSigningConfig(),
    }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <main className="min-h-screen bg-muted/40 p-6 md:p-8 print:bg-white print:p-0">
        <div className="mx-auto max-w-4xl space-y-6">
          <TransactionDetailHeader transactionId={transactionId} />
          <TransactionDetailView transactionId={transactionId} />
        </div>
      </main>
    </HydrationBoundary>
  );
}