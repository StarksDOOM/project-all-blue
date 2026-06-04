import { TransactionPageShellSkeleton } from "@/components/transactions/skeletons/TransactionDetailSkeletons";

/** Route-level streaming shell — fast FCP while RSC prefetches contract data. */
export default function TransactionDetailLoading() {
  return <TransactionPageShellSkeleton />;
}