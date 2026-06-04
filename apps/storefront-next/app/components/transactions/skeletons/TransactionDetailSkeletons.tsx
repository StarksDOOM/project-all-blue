import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function TransactionPageShellSkeleton() {
  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-28" />
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-10 w-28" />
            <Skeleton className="h-10 w-36" />
          </div>
        </div>
        <TimelineSkeleton />
        <SigningPanelSkeleton />
        <ContractCardSkeleton />
      </div>
    </main>
  );
}

export function TimelineSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <Skeleton className="mb-3 h-5 w-40" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-24 w-full rounded-md" />
        ))}
      </div>
    </div>
  );
}

export function AuditActionsSkeleton() {
  return <Skeleton className="h-20 w-full rounded-lg" />;
}

export function SigningPanelSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-4 w-80" />
      </CardHeader>
      <CardContent className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-2/3" />
      </CardContent>
    </Card>
  );
}

export function ContractCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-72" />
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-32 w-full" />
      </CardContent>
    </Card>
  );
}