"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import Link from "next/link";
import { Home, Landmark, Users, Activity } from "lucide-react";

import { PropertyTable } from "@/components/properties/PropertyTable";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PropertyListing } from "@/lib/types";

const ContractDrawer = dynamic(
  () => import("@/components/properties/ContractDrawer"),
  { ssr: false, loading: () => null }
);

export function HomeDashboardClient() {
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);

  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8">
      <div className="mx-auto max-w-7xl">
        {/* Premium Agency Navigation Header */}
        <div className="mb-8 flex flex-col justify-between gap-4 border-b pb-6 md:flex-row md:items-center">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">All Blue Agency Portal</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Core platform operations, contract orchestration, and marketing lead management.
            </p>
          </div>
          <nav className="flex flex-wrap gap-2">
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground shadow transition-all hover:bg-primary/95"
            >
              <Home className="h-3.5 w-3.5" />
              Properties
            </Link>
            <Link
              href="/dashboard/contracts"
              className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-xs font-semibold text-foreground shadow-sm transition-all hover:bg-muted"
            >
              <Landmark className="h-3.5 w-3.5 text-muted-foreground" />
              Contratos
            </Link>
            <Link
              href="/dashboard/leads"
              className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-xs font-semibold text-foreground shadow-sm transition-all hover:bg-muted"
            >
              <Users className="h-3.5 w-3.5 text-muted-foreground" />
              Prospectos (Leads)
            </Link>
            <Link
              href="/admin/scraper-errors"
              className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-xs font-semibold text-foreground shadow-sm transition-all hover:bg-muted"
            >
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
              Scraper Telemetry
            </Link>
          </nav>
        </div>

        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <div className={selectedProperty ? "min-w-0 flex-1" : "w-full"}>
            <PropertyTable
              onSelectProperty={setSelectedProperty}
              selectedPropertyId={selectedProperty?.id ?? null}
            />
          </div>

          {selectedProperty ? (
            <div className="w-full shrink-0 lg:sticky lg:top-8 lg:w-[380px]">
              <ContractDrawer
                property={selectedProperty}
                onClose={() => setSelectedProperty(null)}
              />
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}