import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import { HomeDashboardClient } from "@/components/home/HomeDashboardClient";
import { getQueryClient } from "@/lib/get-query-client";
import { propertyKeys } from "@/lib/query-keys";
import { fetchPropertiesPage } from "@/lib/server-api";

/** RSC entry — prefetch page 1 so the client table hydrates without a duplicate fetch. */
export default async function HomePage() {
  const queryClient = getQueryClient();

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: propertyKeys.total(""),
      queryFn: () =>
        fetchPropertiesPage({
          page: 1,
          limit: 20,
          source_portal: "remaxrd",
          include_total: true,
        }),
    }),
    queryClient.prefetchQuery({
      queryKey: propertyKeys.list(1, "", ""),
      queryFn: () =>
        fetchPropertiesPage({
          page: 1,
          limit: 20,
          source_portal: "remaxrd",
          include_total: true,
        }),
    }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <HomeDashboardClient />
    </HydrationBoundary>
  );
}