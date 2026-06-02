"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BusinessTypeFilter, PropertyListing } from "@/lib/types";

const PAGE_SIZE = 20;

const SECTOR_OPTIONS = [
  "",
  "Piantini",
  "Ensanche Naco",
  "La Esperilla",
  "Bella Vista",
  "Evaristo Morales",
  "Los Prados",
  "El Millón",
  "Zona Universitaria",
  "Viejo Arroyo Hondo",
];

interface PropertyTableProps {
  onSelectProperty: (property: PropertyListing) => void;
  selectedPropertyId: number | null;
}

function formatPrimaryPrice(property: PropertyListing): string {
  if (property.currency === "DOP") {
    return `RD$${property.price_raw.toLocaleString("en-US", {
      maximumFractionDigits: 0,
    })}`;
  }
  return `$${property.price_raw.toLocaleString("en-US", {
    maximumFractionDigits: 0,
  })} USD`;
}

export function PropertyTable({
  onSelectProperty,
  selectedPropertyId,
}: PropertyTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [sectorFilter, setSectorFilter] = useState("");
  const [businessTypeFilter, setBusinessTypeFilter] = useState<BusinessTypeFilter>("");

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ["properties", currentPage, sectorFilter, businessTypeFilter],
    queryFn: () =>
      api.getPropertiesPage({
        page: currentPage,
        limit: PAGE_SIZE,
        source_portal: "remaxrd",
        sector: sectorFilter || undefined,
      }),
    placeholderData: (previousData) => previousData,
  });

  const filteredRows = useMemo(() => {
    const rows = data?.data ?? [];
    if (!businessTypeFilter) {
      return rows;
    }
    return rows.filter((row) => row.business_type === businessTypeFilter);
  }, [data?.data, businessTypeFilter]);

  const metadata = data?.metadata;
  const totalPages = metadata?.pages ?? 1;
  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  const handleSectorChange = (value: string) => {
    setSectorFilter(value);
    setCurrentPage(1);
  };

  const handleBusinessTypeChange = (value: BusinessTypeFilter) => {
    setBusinessTypeFilter(value);
    setCurrentPage(1);
  };

  if (isLoading && !data) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-slate-600">
        Syncing database...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
        Failed to load properties: {(error as Error).message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex min-w-[180px] flex-col gap-1">
          <label htmlFor="sector-filter" className="text-xs font-semibold uppercase text-slate-500">
            Sector
          </label>
          <select
            id="sector-filter"
            value={sectorFilter}
            onChange={(event) => handleSectorChange(event.target.value)}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          >
            <option value="">All Sectors</option>
            {SECTOR_OPTIONS.filter(Boolean).map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </div>

        <div className="flex min-w-[180px] flex-col gap-1">
          <label
            htmlFor="business-type-filter"
            className="text-xs font-semibold uppercase text-slate-500"
          >
            Type
          </label>
          <select
            id="business-type-filter"
            value={businessTypeFilter}
            onChange={(event) =>
              handleBusinessTypeChange(event.target.value as BusinessTypeFilter)
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          >
            <option value="">All Types</option>
            <option value="alquiler">Rent (Alquiler)</option>
            <option value="venta">Sale (Venta)</option>
          </select>
        </div>

        <div className="ml-auto text-sm text-slate-600">
          {isFetching ? "Refreshing..." : null}
          {metadata ? (
            <span>
              Showing page {metadata.page} of {metadata.pages} ({metadata.total.toLocaleString()}{" "}
              total)
            </span>
          ) : null}
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="p-4 text-left font-semibold text-slate-700">Property</th>
              <th className="p-4 text-left font-semibold text-slate-700">Price</th>
              <th className="p-4 text-left font-semibold text-slate-700">Sector</th>
              <th className="p-4 text-left font-semibold text-slate-700">Type</th>
              <th className="p-4 text-right font-semibold text-slate-700">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-8 text-center text-slate-500">
                  No properties match the current filters on this page.
                </td>
              </tr>
            ) : (
              filteredRows.map((property) => {
                const isSelected = selectedPropertyId === property.id;
                return (
                  <tr
                    key={property.remote_id}
                    className={`border-b border-slate-100 ${
                      isSelected ? "bg-blue-50" : "hover:bg-slate-50"
                    }`}
                  >
                    <td className="p-4">
                      <div className="font-medium text-slate-900">{property.title}</div>
                      <div className="text-xs text-slate-500">#{property.remote_id}</div>
                    </td>
                    <td className="p-4">
                      <div className="font-medium text-slate-900">
                        {formatPrimaryPrice(property)}
                      </div>
                      {property.currency === "DOP" ? (
                        <div className="text-xs text-slate-500">
                          ≈ ${property.price_usd.toLocaleString("en-US")} USD
                        </div>
                      ) : null}
                    </td>
                    <td className="p-4 text-slate-700">{property.sector}</td>
                    <td className="p-4 capitalize text-slate-700">{property.business_type}</td>
                    <td className="p-4 text-right">
                      <div className="flex flex-col items-end gap-2">
                        <Link
                          href={`/properties/${property.remote_id}`}
                          className="text-sm font-medium text-slate-700 underline-offset-2 hover:underline"
                        >
                          Ver detalle
                        </Link>
                        <button
                          type="button"
                          onClick={() => onSelectProperty(property)}
                          className="text-sm font-medium text-blue-600 underline-offset-2 hover:underline"
                        >
                          Generate Contract
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
        <button
          type="button"
          onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
          disabled={!canGoPrevious || isFetching}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>

        <span className="text-sm text-slate-700">
          Page {currentPage} of {totalPages}
        </span>

        <button
          type="button"
          onClick={() => setCurrentPage((page) => page + 1)}
          disabled={!canGoNext || isFetching}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}