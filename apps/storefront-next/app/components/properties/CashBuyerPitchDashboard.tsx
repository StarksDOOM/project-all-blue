"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { analyticsKeys } from "@/lib/query-keys";
import type { WholesaleDealMetrics } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatUSD(value: number): string {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function formatPct(value: number): string {
  return `${value.toFixed(2)}%`;
}

// ---------------------------------------------------------------------------
// Slider Input
// ---------------------------------------------------------------------------

interface SliderInputProps {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix?: string;
  formatDisplay?: (v: number) => string;
  onChange: (v: number) => void;
}

function SliderInput({
  id,
  label,
  value,
  min,
  max,
  step,
  suffix = "",
  formatDisplay,
  onChange,
}: SliderInputProps) {
  const display = formatDisplay ? formatDisplay(value) : `${value}${suffix}`;
  const pct = max > min ? ((value - min) / (max - min)) * 100 : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label
          htmlFor={id}
          className="text-xs font-medium text-slate-400 uppercase tracking-wide"
        >
          {label}
        </label>
        <span className="font-mono text-sm font-semibold text-white tabular-nums">
          {display}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="str-slider w-full"
        style={
          {
            "--slider-pct": `${pct}%`,
          } as React.CSSProperties
        }
      />
      <div className="flex justify-between text-[10px] text-slate-600">
        <span>{formatDisplay ? formatDisplay(min) : `${min}${suffix}`}</span>
        <span>{formatDisplay ? formatDisplay(max) : `${max}${suffix}`}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  accent?: "default" | "green" | "blue" | "amber";
}

function MetricCard({ label, value, sub, accent = "default" }: MetricCardProps) {
  const colorMap = {
    default: "text-white",
    green: "text-emerald-400",
    blue: "text-blue-400",
    amber: "text-amber-400",
  };

  return (
    <div className="rounded-lg bg-slate-800/60 px-3 py-2.5 ring-1 ring-slate-700/50">
      <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className={`mt-0.5 font-mono text-lg font-bold ${colorMap[accent]}`}>
        {value}
      </p>
      {sub ? (
        <p className="text-[10px] text-slate-500 font-mono">{sub}</p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface CashBuyerPitchDashboardProps {
  propertyBluId: string;
  wholesaleData: WholesaleDealMetrics | null | undefined;
  locationSlug?: string;
  trafficSource?: string;
}

export function CashBuyerPitchDashboard({
  propertyBluId,
  wholesaleData,
  locationSlug,
  trafficSource,
}: CashBuyerPitchDashboardProps) {
  const rec = wholesaleData?.recommended_str_assumptions;

  // Lead Magnet lock state (only active when locationSlug is present)
  const [isLocked, setIsLocked] = useState(() => {
    if (typeof window === "undefined" || !locationSlug) return false;
    return !window.sessionStorage.getItem("lead_magnet_unlocked");
  });

  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // STR assumption state (hydrated from recommended_str_assumptions)
  const [nightlyRate, setNightlyRate] = useState(rec?.nightly_rate ?? 120);
  const [occupancy, setOccupancy] = useState(rec ? Math.round(rec.occupancy_pct * 100) : 40); // stored as 0-100 for slider UX
  const [monthlyMaintenance, setMonthlyMaintenance] = useState(rec?.monthly_maintenance ?? 150);

  const [hasHydrated, setHasHydrated] = useState(!!rec);

  // Sync recommended defaults when they load asynchronously
  useEffect(() => {
    const freshRec = wholesaleData?.recommended_str_assumptions;
    if (freshRec && !hasHydrated) {
      setNightlyRate(freshRec.nightly_rate);
      setOccupancy(Math.round(freshRec.occupancy_pct * 100));
      setMonthlyMaintenance(freshRec.monthly_maintenance);
      setHasHydrated(true);
    }
  }, [wholesaleData, hasHydrated]);

  // Debounce timer ref
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedParams, setDebouncedParams] = useState({
    nightly_rate: rec?.nightly_rate ?? 120,
    occupancy_pct: rec?.occupancy_pct ?? 0.40,
    monthly_maintenance: rec?.monthly_maintenance ?? 150,
  });

  // Debounce param updates (300ms)
  const updateParams = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedParams({
        nightly_rate: nightlyRate,
        occupancy_pct: occupancy / 100,
        monthly_maintenance: monthlyMaintenance,
      });
    }, 300);
  }, [nightlyRate, occupancy, monthlyMaintenance]);

  useEffect(() => {
    updateParams();
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [updateParams]);

  // Fetch STR metrics
  const { data: strData, isLoading: isStrLoading } =
    useQuery<WholesaleDealMetrics>({
      queryKey: analyticsKeys.wholesaleStr(
        propertyBluId,
        debouncedParams.nightly_rate,
        debouncedParams.occupancy_pct,
        debouncedParams.monthly_maintenance
      ),
      queryFn: () =>
        api.getWholesaleAnalytics(propertyBluId, debouncedParams),
      enabled:
        propertyBluId.length > 0 && debouncedParams.nightly_rate > 0,
      staleTime: 60_000,
      retry: false,
    });

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    const emailClean = email.trim();
    if (!emailClean) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    const emailPattern = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
    if (!emailPattern.test(emailClean)) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.captureLead({
        email: emailClean,
        location_slug: locationSlug || "unknown",
        traffic_source: trafficSource || "organic",
        simulated_purchase_price: wholesaleData?.pitch_price ?? 0,
        simulated_nightly_rate: nightlyRate,
        simulated_occupancy: occupancy / 100,
        simulated_maintenance: monthlyMaintenance,
      });

      if (typeof window !== "undefined") {
        window.sessionStorage.setItem("lead_magnet_unlocked", "true");
      }
      setIsLocked(false);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to capture lead. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!wholesaleData) return null;

  const hasResults =
    strData?.str_monthly_gross != null && debouncedParams.nightly_rate > 0;

  return (
    <Card className="border-slate-700/50 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 text-white shadow-xl">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-white">
          <span className="text-blue-400">🏠</span>
          Cash Buyer Pitch Dashboard
        </CardTitle>
        <CardDescription className="text-slate-400 text-xs">
          Short-Term Rental yield projections · Adjust assumptions below
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* ---- Assumption sliders ---- */}
        <div className="space-y-4 rounded-xl bg-slate-800/40 p-4 ring-1 ring-slate-700/30">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            STR Assumptions
          </p>

          <SliderInput
            id="str-nightly-rate"
            label="Nightly Rate"
            value={nightlyRate}
            min={0}
            max={500}
            step={5}
            formatDisplay={(v) => `$${v}`}
            onChange={setNightlyRate}
          />

          <SliderInput
            id="str-occupancy"
            label="Occupancy"
            value={occupancy}
            min={0}
            max={100}
            step={5}
            suffix="%"
            onChange={setOccupancy}
          />

          <SliderInput
            id="str-monthly-maintenance"
            label="Monthly Maintenance"
            value={monthlyMaintenance}
            min={0}
            max={2000}
            step={25}
            formatDisplay={(v) => `$${v}`}
            onChange={setMonthlyMaintenance}
          />
        </div>

        {/* ---- Metrics grid ---- */}
        {nightlyRate === 0 ? (
          <p className="text-center text-xs text-slate-500 py-4">
            Set a nightly rate above $0 to see projections.
          </p>
        ) : isStrLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton
                key={i}
                className="h-16 w-full rounded-lg bg-slate-800"
              />
            ))}
          </div>
        ) : hasResults ? (
          <>
            {/* Row 1: Monthly breakdown */}
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard
                label="Monthly Gross"
                value={formatUSD(strData!.str_monthly_gross!)}
                sub={`$${nightlyRate}/night × 30 × ${occupancy}%`}
              />
              <MetricCard
                label="PM Cost (20%)"
                value={formatUSD(strData!.str_pm_cost!)}
                accent="amber"
              />
              <MetricCard
                label="Monthly Net"
                value={formatUSD(strData!.str_monthly_net!)}
                accent={strData!.str_monthly_net! >= 0 ? "green" : "default"}
                sub="After PM + Maintenance + reserve"
              />
            </div>

            {/* Row 2: Annual + Cash-on-Cash */}
            <div className="grid gap-3 sm:grid-cols-2">
              <MetricCard
                label="Annual NOI"
                value={formatUSD(strData!.str_annual_noi!)}
                accent={strData!.str_annual_noi! >= 0 ? "green" : "default"}
              />
              <div className="rounded-xl bg-gradient-to-r from-emerald-600/20 to-blue-600/20 px-4 py-3 ring-1 ring-emerald-500/30">
                <p className="text-[10px] font-medium uppercase tracking-wider text-emerald-300">
                  Cash-on-Cash Return
                </p>
                <p className="mt-1 font-mono text-2xl font-black text-white">
                  {formatPct(strData!.str_cash_on_cash_pct!)}
                </p>
                <p className="text-[10px] text-slate-400 font-mono">
                  on {formatUSD(wholesaleData.pitch_price)} entry
                </p>
              </div>
            </div>

            {/* Row 3: Projections */}
            <div className="relative overflow-hidden rounded-xl bg-slate-800/30 p-4 ring-1 ring-slate-700/20">
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Net Profit Projections
              </p>
              
              <div className={`grid gap-3 sm:grid-cols-3 transition-all duration-300 ${isLocked ? "blur-md select-none pointer-events-none" : ""}`}>
                <MetricCard
                  label="6 Months"
                  value={formatUSD(strData!.str_projection_6mo!)}
                  accent="blue"
                />
                <MetricCard
                  label="1 Year"
                  value={formatUSD(strData!.str_projection_1yr!)}
                  accent="blue"
                />
                <MetricCard
                  label="3 Years"
                  value={formatUSD(strData!.str_projection_3yr!)}
                  accent="green"
                />
              </div>

              {isLocked && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/90 p-4 text-center">
                  <p className="mb-1 text-[10px] font-bold text-blue-400 uppercase tracking-widest">
                    🔒 Gated Projections
                  </p>
                  <h4 className="text-xs font-bold text-white mb-3">
                    Unlock Full ROI Projections & PDF Prospectus
                  </h4>
                  <form onSubmit={handleUnlock} className="flex w-full max-w-sm flex-col gap-2 sm:flex-row">
                    <input
                      type="email"
                      required
                      placeholder="Enter your email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={isSubmitting}
                      className="flex-1 rounded bg-slate-800 px-3 py-1.5 text-xs text-white placeholder-slate-500 outline-none ring-1 ring-slate-700 focus:ring-blue-500 focus:bg-slate-700/90"
                    />
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="rounded bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-1.5 text-xs font-bold text-white hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 flex items-center justify-center gap-1 transition-all"
                    >
                      {isSubmitting ? "Unlocking..." : "Unlock"}
                    </button>
                  </form>
                  {errorMsg && (
                    <p className="mt-2 text-[10px] text-rose-400 font-mono">{errorMsg}</p>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <p className="text-center text-xs text-slate-500 py-4">
            Unable to compute projections. Verify the property is active.
          </p>
        )}
      </CardContent>

      {/* Slider CSS — injected once */}
      <style jsx global>{`
        .str-slider {
          -webkit-appearance: none;
          appearance: none;
          height: 6px;
          border-radius: 9999px;
          background: linear-gradient(
            to right,
            #3b82f6 0%,
            #3b82f6 var(--slider-pct, 50%),
            #334155 var(--slider-pct, 50%),
            #334155 100%
          );
          outline: none;
          cursor: pointer;
        }
        .str-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #fff;
          box-shadow: 0 0 0 3px #3b82f6, 0 2px 8px rgba(0, 0, 0, 0.3);
          cursor: grab;
          transition: box-shadow 0.15s ease;
        }
        .str-slider::-webkit-slider-thumb:hover {
          box-shadow: 0 0 0 4px #60a5fa, 0 2px 12px rgba(59, 130, 246, 0.4);
        }
        .str-slider::-webkit-slider-thumb:active {
          cursor: grabbing;
        }
        .str-slider::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #fff;
          border: none;
          box-shadow: 0 0 0 3px #3b82f6, 0 2px 8px rgba(0, 0, 0, 0.3);
          cursor: grab;
        }
        .str-slider::-moz-range-track {
          height: 6px;
          border-radius: 9999px;
          background: #334155;
        }
        .str-slider::-moz-range-progress {
          height: 6px;
          border-radius: 9999px;
          background: #3b82f6;
        }
      `}</style>
    </Card>
  );
}
