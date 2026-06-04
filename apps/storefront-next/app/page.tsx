"use client";

import { useState } from "react";
import ContractDrawer from "./components/properties/ContractDrawer";
import { PropertyTable } from "./components/properties/PropertyTable";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./components/ui/card";
import { PropertyListing } from "./lib/types";

export default function Home() {
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);

  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8">
      <div className="mx-auto max-w-7xl">
        <Card className="mb-6 border-0 bg-transparent shadow-none ring-0">
          <CardHeader className="px-0">
            <CardTitle className="text-2xl">Property Dashboard</CardTitle>
            <CardDescription>
              Browse synced RE/MAX inventory with server-side pagination.{" "}
              <a
                href="/admin/scraper-errors"
                className="font-medium text-slate-700 underline-offset-4 hover:underline"
              >
                Scraper telemetry
              </a>
            </CardDescription>
          </CardHeader>
        </Card>

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