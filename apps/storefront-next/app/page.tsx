import { Suspense } from "react";
import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import { HomeDashboardClient } from "@/components/home/HomeDashboardClient";
import HomeLoading from "./loading";
import { getQueryClient } from "@/lib/get-query-client";
import {
  DEFAULT_PROPERTY_FILTERS,
  filtersFingerprint,
} from "@/lib/property-filters";
import { propertyKeys } from "@/lib/query-keys";
import { fetchPropertiesPage } from "@/lib/server-api";

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

/** RSC entry — prefetch default facet page for instant hydration. */
export default async function HomePage({ searchParams }: PageProps) {
  const resolvedParams = await searchParams;
  const hasFilters = Object.keys(resolvedParams).some(
    (key) => key !== "source_portal" && key !== "page"
  );

  const queryClient = getQueryClient();
  const fingerprint = filtersFingerprint(DEFAULT_PROPERTY_FILTERS);
  const baseQuery = {
    page: 1,
    limit: 20,
    source_portal: "remaxrd" as const,
    include_total: true,
  };

  if (!hasFilters) {
    await Promise.all([
      queryClient.prefetchQuery({
        queryKey: propertyKeys.total(fingerprint),
        queryFn: () => fetchPropertiesPage(baseQuery),
      }),
      queryClient.prefetchQuery({
        queryKey: propertyKeys.list(1, fingerprint),
        queryFn: () => fetchPropertiesPage(baseQuery),
      }),
    ]);
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Suspense fallback={<HomeLoading />}>
        <HomeDashboardClient />
      </Suspense>
    </HydrationBoundary>
  );
}