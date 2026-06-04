import { Skeleton } from "@/components/ui/skeleton";

export default function PropertyDetailLoading() {
  return (
    <main className="min-h-screen bg-muted/40 pb-32">
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 md:px-8">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-64 w-full rounded-lg" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    </main>
  );
}