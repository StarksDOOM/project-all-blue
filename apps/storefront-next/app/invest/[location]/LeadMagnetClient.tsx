"use client";

import { useQuery } from "@tanstack/react-query";
import { api, getPropertyDetail } from "@/lib/api";
import { propertyKeys, analyticsKeys } from "@/lib/query-keys";
import { CashBuyerPitchDashboard } from "@/components/properties/CashBuyerPitchDashboard";
import { LeadMagnetWrapper } from "./LeadMagnetWrapper";
import type { WholesaleDealMetrics } from "@/lib/types";

interface LeadMagnetClientProps {
  locationSlug: string;
  propertyId: string | null;
}

/**
 * LeadMagnetClient client component:
 * Fetches base property details and wholesale metrics to supply the calculator dashboard.
 */
export function LeadMagnetClient({ locationSlug, propertyId }: LeadMagnetClientProps) {
  // Query property detail to show nice info (title, location, etc.)
  const { data: detailData } = useQuery({
    queryKey: propertyKeys.detail(propertyId || "", "portal"),
    queryFn: () => getPropertyDetail(propertyId || "", { refreshFromPortal: false }),
    enabled: !!propertyId,
  });

  // Query base wholesale metrics
  const { data: wholesaleData } = useQuery<WholesaleDealMetrics>({
    queryKey: analyticsKeys.wholesale(propertyId || ""),
    queryFn: () => api.getWholesaleAnalytics(propertyId || ""),
    enabled: !!propertyId,
  });

  if (!propertyId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8 bg-slate-950 text-white">
        <h2 className="text-xl font-bold mb-2 text-red-400">No Listings Available</h2>
        <p className="text-slate-400 max-w-md text-sm">
          There are no listings seeded in the database. Please run the portal scraper or import a property listing to initialize comp calculations.
        </p>
      </div>
    );
  }

  const property = detailData?.property;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 bg-slate-950 text-white min-h-screen">
      <div className="mb-6 space-y-2 text-center sm:text-left">
        <h1 className="text-3xl font-black tracking-tight text-white uppercase sm:text-4xl">
          Real Estate ROI Calculator
        </h1>
        {property ? (
          <p className="text-sm text-slate-400">
            Analyzing property: <span className="font-semibold text-blue-400">{property.title}</span> ({property.sector}, {property.province})
          </p>
        ) : (
          <p className="text-sm text-slate-400">Loading property comp dimensions...</p>
        )}
      </div>

      <LeadMagnetWrapper>
        {(trafficSource) => (
          <CashBuyerPitchDashboard
            propertyBluId={propertyId}
            wholesaleData={wholesaleData}
            locationSlug={locationSlug}
            trafficSource={trafficSource}
          />
        )}
      </LeadMagnetWrapper>
    </div>
  );
}
