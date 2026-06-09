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
        className="comm-slider w-full"
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
// Main Component
// ---------------------------------------------------------------------------

interface CommercialYieldDashboardProps {
  propertyBluId: string;
  wholesaleData: WholesaleDealMetrics | null | undefined;
}

export function CommercialYieldDashboard({
  propertyBluId,
  wholesaleData,
}: CommercialYieldDashboardProps) {
  // State for sliders
  const [rentPerSqm, setRentPerSqm] = useState(15.0);
  const [vacancy, setVacancy] = useState(10); // stored as 0-100 for slider UX
  const [taxesIns, setTaxesIns] = useState(0);

  // Debounce state updates
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedParams, setDebouncedParams] = useState({
    monthly_rent_per_sqm: 15.0,
    comm_vacancy_rate: 0.10,
    annual_taxes_insurance: 0,
  });

  const updateParams = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedParams({
        monthly_rent_per_sqm: rentPerSqm,
        comm_vacancy_rate: vacancy / 100,
        annual_taxes_insurance: taxesIns,
      });
    }, 300);
  }, [rentPerSqm, vacancy, taxesIns]);

  useEffect(() => {
    updateParams();
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [updateParams]);

  // Fetch Commercial metrics
  const { data: commData, isLoading: isCommLoading } =
    useQuery<WholesaleDealMetrics>({
      queryKey: analyticsKeys.wholesaleComm(
        propertyBluId,
        debouncedParams.monthly_rent_per_sqm,
        debouncedParams.comm_vacancy_rate,
        debouncedParams.annual_taxes_insurance
      ),
      queryFn: () =>
        api.getWholesaleAnalytics(propertyBluId, undefined, debouncedParams),
      enabled: propertyBluId.length > 0,
      staleTime: 60_000,
      retry: false,
    });

  if (!wholesaleData) return null;

  const hasResults = commData?.commercial_metrics != null;

  return (
    <Card className="border-slate-700/50 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 text-white shadow-xl">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-white">
          <span className="text-blue-400">🏢</span>
          Commercial Yield Dashboard
        </CardTitle>
        <CardDescription className="text-slate-400 text-xs">
          Commercial Cap Rate yield projections · Adjust assumptions below
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* ---- Assumption sliders ---- */}
        <div className="space-y-4 rounded-xl bg-slate-800/40 p-4 ring-1 ring-slate-700/30">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            Commercial Assumptions
          </p>

          <SliderInput
            id="comm-rent-sqm"
            label="Monthly Rent / SqM"
            value={rentPerSqm}
            min={0}
            max={100}
            step={0.5}
            formatDisplay={(v) => `$${v.toFixed(2)}`}
            onChange={setRentPerSqm}
          />

          <SliderInput
            id="comm-vacancy"
            label="Vacancy Rate"
            value={vacancy}
            min={0}
            max={100}
            step={1}
            suffix="%"
            onChange={setVacancy}
          />

          <SliderInput
            id="comm-taxes-ins"
            label="Annual Taxes & Insurance"
            value={taxesIns}
            min={0}
            max={50000}
            step={100}
            formatDisplay={(v) => `$${v.toLocaleString()}`}
            onChange={setTaxesIns}
          />
        </div>

        {/* ---- Metrics grid ---- */}
        {isCommLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton
                key={i}
                className="h-16 w-full rounded-lg bg-slate-800"
              />
            ))}
          </div>
        ) : hasResults ? (
          <>
            {/* Row 1: Financial breakdowns */}
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard
                label="Annual Gross Rent"
                value={formatUSD(commData.commercial_metrics!.annual_gross_rent)}
                sub={`$${rentPerSqm.toFixed(2)}/sqm × 12 mo`}
              />
              <MetricCard
                label="Effective Gross Income"
                value={formatUSD(commData.commercial_metrics!.effective_gross_income)}
                sub={`After ${vacancy}% vacancy`}
                accent="amber"
              />
              <MetricCard
                label="Annual NOI"
                value={formatUSD(commData.commercial_metrics!.annual_noi)}
                accent={commData.commercial_metrics!.annual_noi >= 0 ? "green" : "default"}
                sub="After Taxes & Insurance"
              />
            </div>

            {/* Row 2: Cap Rate Hero Metric */}
            <div className="rounded-xl bg-gradient-to-r from-emerald-600/20 to-blue-600/20 px-4 py-3 ring-1 ring-emerald-500/30">
              <p className="text-[10px] font-medium uppercase tracking-wider text-emerald-300">
                Capitalisation Rate (Cap Rate)
              </p>
              <p className="mt-1 font-mono text-2xl font-black text-white">
                {formatPct(commData.commercial_metrics!.cap_rate_pct)}
              </p>
              <p className="text-[10px] text-slate-400 font-mono">
                on {formatUSD(wholesaleData.pitch_price)} entry price
              </p>
            </div>
          </>
        ) : (
          <p className="text-center text-xs text-slate-500 py-4">
            Unable to compute commercial metrics. Verify parameters are correct.
          </p>
        )}
      </CardContent>

      {/* Slider CSS */}
      <style jsx global>{`
        .comm-slider {
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
        .comm-slider::-webkit-slider-thumb {
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
        .comm-slider::-webkit-slider-thumb:hover {
          box-shadow: 0 0 0 4px #60a5fa, 0 2px 12px rgba(59, 130, 246, 0.4);
        }
        .comm-slider::-webkit-slider-thumb:active {
          cursor: grabbing;
        }
        .comm-slider::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #fff;
          border: none;
          box-shadow: 0 0 0 3px #3b82f6, 0 2px 8px rgba(0, 0, 0, 0.3);
          cursor: grab;
        }
        .comm-slider::-moz-range-track {
          height: 6px;
          border-radius: 9999px;
          background: #334155;
        }
        .comm-slider::-moz-range-progress {
          height: 6px;
          border-radius: 9999px;
          background: #3b82f6;
        }
      `}</style>
    </Card>
  );
}
