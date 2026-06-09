import { dehydrate, HydrationBoundary } from "@tanstack/react-query";
import { Suspense } from "react";
import { fetchPropertiesPage, fetchPropertyDetail } from "@/lib/server-api";
import { getQueryClient } from "@/lib/get-query-client";
import { propertyKeys } from "@/lib/query-keys";
import { LeadMagnetClient } from "./LeadMagnetClient";

interface InvestPageProps {
  params: Promise<{ location: string }>;
}

/**
 * Dynamic route to handle dynamic public lead capture landing pages.
 * Resolves location parameter to lookup comps, pre-fetching the detailed context.
 */
export default async function InvestPage({ params }: InvestPageProps) {
  const { location } = await params;
  const queryClient = getQueryClient();

  // 1. Cross-reference location slug to look up comp search keyword
  let searchKey = "";
  if (location === "punta-cana") {
    searchKey = "Punta Cana";
  } else if (location === "samana") {
    searchKey = "Samana";
  } else if (location === "santo-domingo") {
    searchKey = "Santo Domingo";
  } else {
    // Fallback: title-case slug format
    searchKey = location
      .replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // 2. Fetch properties matching search key
  const { data: properties } = await fetchPropertiesPage({
    keyword: searchKey,
    property_type: "venta",
    limit: 1,
  });

  let selectedProperty = properties[0];
  if (!selectedProperty) {
    // Fallback to first available property in the DB
    const { data: fallbackProps } = await fetchPropertiesPage({
      property_type: "venta",
      limit: 1,
    });
    selectedProperty = fallbackProps[0];
  }

  if (selectedProperty) {
    // Prefetch property detail on the server using blu_id string primary key
    await queryClient.prefetchQuery({
      queryKey: propertyKeys.detail(selectedProperty.blu_id, "portal"),
      queryFn: () =>
        fetchPropertyDetail(selectedProperty.blu_id, {
          refreshFromPortal: false,
        }),
    });
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Suspense
        fallback={
          <div className="flex min-h-[60vh] items-center justify-center text-slate-400">
            Loading ROI calculator...
          </div>
        }
      >
        <LeadMagnetClient
          locationSlug={location}
          propertyId={selectedProperty?.blu_id ?? null}
        />
      </Suspense>
    </HydrationBoundary>
  );
}
