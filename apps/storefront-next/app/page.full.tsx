"use client";

import { useState } from "react";
import ContractDrawer from "./components/properties/ContractDrawer";
import { PropertyTable } from "./components/properties/PropertyTable";
import { PropertyListing } from "./lib/types";

export default function Home() {
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);

  return (
    <main className="min-h-screen bg-slate-100 p-6 md:p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Property Dashboard</h1>
          <p className="mt-1 text-sm text-slate-600">
            Browse synced RE/MAX inventory with server-side pagination.
          </p>
        </header>

        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <div className={selectedProperty ? "min-w-0 flex-1" : "w-full"}>
            <PropertyTable
              onSelectProperty={setSelectedProperty}
              selectedPropertyId={selectedProperty?.id ?? null}
            />
          </div>

          {selectedProperty ? (
            <div className="w-full shrink-0 lg:w-[380px] lg:sticky lg:top-8">
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