"use client";

import { PropertyTable } from "./components/properties/PropertyTable";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-100 p-6 md:p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Property Dashboard</h1>
          <p className="mt-1 text-sm text-slate-600">
            Browse synced RE/MAX inventory with server-side pagination.
          </p>
        </header>
        <PropertyTable
          onSelectProperty={() => undefined}
          selectedPropertyId={null}
        />
      </div>
    </main>
  );
}