"use client";

import { useSearchParams } from "next/navigation";
import { ReactNode, useMemo } from "react";

interface LeadMagnetWrapperProps {
  children: (trafficSource: string) => ReactNode;
}

/**
 * Extracts "?src=..." search parameter for traffic source attribution,
 * defaulting to "organic" if missing.
 */
export function LeadMagnetWrapper({ children }: LeadMagnetWrapperProps) {
  const searchParams = useSearchParams();
  const trafficSource = useMemo(() => {
    return searchParams.get("src") || "organic";
  }, [searchParams]);

  return <>{children(trafficSource)}</>;
}
