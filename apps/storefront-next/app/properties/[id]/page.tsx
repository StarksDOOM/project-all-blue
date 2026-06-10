import { dehydrate, HydrationBoundary } from "@tanstack/react-query";

import { PropertyDetailClient } from "@/components/properties/PropertyDetailClient";
import { getQueryClient } from "@/lib/get-query-client";
import { propertyKeys } from "@/lib/query-keys";
import { fetchPropertyDetail } from "@/lib/server-api";

interface PropertyDetailPageProps {
  params: Promise<{ id: string }>;
}

/** RSC prefetch with portal sync for fresh data + images; client also starts with live sync for gallery. */
export default async function PropertyDetailPage({ params }: PropertyDetailPageProps) {
  const { id: propertyId } = await params;
  const queryClient = getQueryClient();

  if (propertyId) {
    await queryClient.prefetchQuery({
      queryKey: propertyKeys.detail(propertyId, "portal"),
      queryFn: () => fetchPropertyDetail(propertyId, { refreshFromPortal: false }),
    });
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <PropertyDetailClient propertyId={propertyId} />
    </HydrationBoundary>
  );
}