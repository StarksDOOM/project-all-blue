"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { api } from "@/lib/api";
import { propertyKeys } from "@/lib/query-keys";
import { useFilterParams } from "@/hooks/useFilterParams";
import { useCreateSearchAlert } from "@/hooks/useCreateSearchAlert";
import { formatPrimaryPrice, formatSecondaryPrice } from "@/lib/pricing";
import { cn } from "@/lib/utils";
import { PropertyListing } from "@/lib/types";
import { PropertyFilterPanel } from "@/components/properties/PropertyFilterPanel";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

const TransactionContractModal = dynamic(
  () =>
    import("@/components/transactions/TransactionContractModal").then(
      (mod) => mod.TransactionContractModal
    ),
  { ssr: false }
);

const PAGE_SIZE = 20;

interface PropertyTableProps {
  onSelectProperty: (property: PropertyListing) => void;
  selectedPropertyId: number | null;
}

function businessTypeBadgeVariant(type: string): "default" | "secondary" | "outline" {
  if (type === "venta") return "default";
  if (type === "alquiler") return "secondary";
  return "outline";
}

export function PropertyTable({
  onSelectProperty,
  selectedPropertyId,
}: PropertyTableProps) {
  const [contractProperty, setContractProperty] = useState<PropertyListing | null>(null);
  const {
    appliedFilters,
    fingerprint,
    draft,
    setDraftField,
    setInstantFilter,
    setPage,
    resetFilters,
    isDebouncing,
  } = useFilterParams();

  const createAlert = useCreateSearchAlert(appliedFilters);

  const currentPage = appliedFilters.page ?? 1;

  const queryPayload = {
    page: currentPage,
    limit: PAGE_SIZE,
    source_portal: appliedFilters.source_portal ?? "remaxrd",
    sector: appliedFilters.sector,
    keyword: appliedFilters.keyword,
    price_min: appliedFilters.price_min,
    price_max: appliedFilters.price_max,
    bedrooms_min: appliedFilters.bedrooms_min,
    bathrooms_min: appliedFilters.bathrooms_min,
    property_type: appliedFilters.property_type || undefined,
    agency: appliedFilters.agency,
  };

  const { data: totalSnapshot } = useQuery({
    queryKey: propertyKeys.total(fingerprint),
    queryFn: () =>
      api.getPropertiesPage({ ...queryPayload, page: 1, include_total: true }),
    staleTime: 120_000,
    gcTime: 600_000,
  });

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: propertyKeys.list(currentPage, fingerprint),
    queryFn: () =>
      api.getPropertiesPage({
        ...queryPayload,
        include_total: currentPage === 1,
      }),
    staleTime: 60_000,
    gcTime: 300_000,
    refetchOnMount: false,
    retry: 1,
    retryDelay: 1500,
    placeholderData: (previousData) => previousData,
  });

  const rows = data?.data ?? [];
  const metadata = data?.metadata;
  const inventoryTotal = totalSnapshot?.metadata.total ?? metadata?.total ?? null;
  const totalPages =
    inventoryTotal != null
      ? Math.max(1, Math.ceil(inventoryTotal / PAGE_SIZE))
      : metadata?.has_next
        ? currentPage + 1
        : currentPage;
  const canGoPrevious = currentPage > 1;
  const canGoNext =
    metadata?.has_next ?? (inventoryTotal != null && currentPage < totalPages);
  const showPartialSkeleton = Boolean(data && (isFetching || isDebouncing));

  return (
    <div className="space-y-4">
      <PropertyFilterPanel
        filters={appliedFilters}
        draft={draft}
        onDraftChange={setDraftField}
        onInstantChange={setInstantFilter}
        onReset={resetFilters}
        isDebouncing={isDebouncing}
        onSaveAlert={createAlert.openDialog}
      />

      {isLoading && !data ? (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-8 w-full max-w-md" />
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
      ) : isError ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="pt-4 text-sm text-destructive">
            Failed to load properties: {(error as Error).message}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex justify-end text-sm text-muted-foreground">
            {metadata ? (
              <span>
                Page {metadata.page}
                {inventoryTotal != null ? (
                  <> of {totalPages} ({inventoryTotal.toLocaleString()} total)</>
                ) : metadata.has_next ? (
                  <> · more available</>
                ) : null}
              </span>
            ) : null}
          </div>

          <Card className="relative py-0">
            {showPartialSkeleton ? (
              <p className="absolute right-4 top-3 z-10 text-xs font-medium text-muted-foreground">
                Updating results…
              </p>
            ) : null}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Property</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Sector</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody
                className={cn(
                  showPartialSkeleton && "pointer-events-none opacity-50 transition-opacity"
                )}
              >
                {rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                      No properties match the current filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  rows.map((property) => {
                    const isSelected = selectedPropertyId === property.id;
                    return (
                      <TableRow
                        key={property.remote_id}
                        data-state={isSelected ? "selected" : undefined}
                      >
                        <TableCell>
                          <div className="font-medium">{property.title}</div>
                          <div className="text-xs text-muted-foreground">#{property.remote_id}</div>
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{formatPrimaryPrice(property)}</div>
                          {formatSecondaryPrice(property) ? (
                            <div className="text-xs text-muted-foreground">
                              {formatSecondaryPrice(property)}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell>{property.sector}</TableCell>
                        <TableCell>
                          <Badge
                            variant={businessTypeBadgeVariant(property.business_type)}
                            className="capitalize"
                          >
                            {property.business_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex flex-col items-end gap-2">
                            <Link
                              href={`/properties/${property.remote_id}`}
                              prefetch
                              className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                            >
                              Ver detalle
                            </Link>
                            <Button
                              type="button"
                              variant="default"
                              size="sm"
                              onClick={() => setContractProperty(property)}
                            >
                              Generar Contrato
                            </Button>
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              onClick={() => onSelectProperty(property)}
                            >
                              SRL (legacy)
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </Card>

          <Card>
            <CardContent className="flex items-center justify-between py-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setPage(Math.max(1, currentPage - 1))}
                disabled={!canGoPrevious || isFetching}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                type="button"
                variant="outline"
                onClick={() => setPage(currentPage + 1)}
                disabled={!canGoNext || isFetching}
              >
                Next
              </Button>
            </CardContent>
          </Card>
        </>
      )}

      {contractProperty ? (
        <TransactionContractModal
          property={contractProperty}
          open={Boolean(contractProperty)}
          onOpenChange={(open) => {
            if (!open) setContractProperty(null);
          }}
        />
      ) : null}
      {createAlert.dialog}
    </div>
  );
}