import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import { PropertyDetailClient } from "@/components/properties/PropertyDetailClient";
import { getQueryClient } from "@/lib/get-query-client";
import { propertyKeys } from "@/lib/query-keys";
import { fetchPropertyDetail } from "@/lib/server-api";

interface PropertyDetailPageProps {
  params: Promise<{ id: string }>;
}

/** RSC prefetch — detail hydrates instantly; portal sync stays on-demand in the client. */
export default async function PropertyDetailPage({ params }: PropertyDetailPageProps) {
  const { id: propertyId } = await params;
  const queryClient = getQueryClient();

  if (propertyId) {
    await queryClient.prefetchQuery({
      queryKey: propertyKeys.detail(propertyId, "cached"),
      queryFn: () => fetchPropertyDetail(propertyId, { refreshFromPortal: false }),
    });
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <PropertyDetailClient propertyId={propertyId} />
    </HydrationBoundary>
  );
}