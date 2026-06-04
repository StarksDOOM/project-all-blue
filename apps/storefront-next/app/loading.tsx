import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/** Instant dashboard shell while RSC prefetches inventory. */
export default function HomeLoading() {
  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-4 w-96" />
        </div>
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-10 w-full max-w-md" />
            <Skeleton className="h-72 w-full" />
          </CardContent>
        </Card>
      </div>
    </main>
  );
}