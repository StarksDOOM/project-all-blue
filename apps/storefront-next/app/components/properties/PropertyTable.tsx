"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatPrimaryPrice, formatSecondaryPrice } from "@/lib/pricing";
import { cn } from "@/lib/utils";
import { BusinessTypeFilter, PropertyListing } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PAGE_SIZE = 20;

const SECTOR_OPTIONS = [
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

function businessTypeBadgeVariant(type: string): "default" | "secondary" | "outline" {
  if (type === "venta") return "default";
  if (type === "alquiler") return "secondary";
  return "outline";
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

  if (isLoading && !data) {
    return (
      <Card>
        <CardContent className="space-y-3">
          <Skeleton className="h-8 w-full max-w-md" />
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/30 bg-destructive/5">
        <CardContent className="pt-4 text-sm text-destructive">
          Failed to load properties: {(error as Error).message}
          <p className="mt-2 text-xs text-muted-foreground">
            Ensure FastAPI is running at{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-foreground">
              http://127.0.0.1:8000
            </code>
            .
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="flex min-w-[200px] flex-col gap-2">
            <Label htmlFor="sector-filter">Sector</Label>
            <Select
              value={sectorFilter || "all"}
              onValueChange={(value) => {
                setSectorFilter(!value || value === "all" ? "" : value);
                setCurrentPage(1);
              }}
            >
              <SelectTrigger id="sector-filter" className="w-full min-w-[200px]" size="default">
                <SelectValue placeholder="All Sectors" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sectors</SelectItem>
                {SECTOR_OPTIONS.map((sector) => (
                  <SelectItem key={sector} value={sector}>
                    {sector}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex min-w-[200px] flex-col gap-2">
            <Label htmlFor="business-type-filter">Type</Label>
            <Select
              value={businessTypeFilter || "all"}
              onValueChange={(value) => {
                setBusinessTypeFilter(
                  !value || value === "all" ? "" : (value as BusinessTypeFilter)
                );
                setCurrentPage(1);
              }}
            >
              <SelectTrigger
                id="business-type-filter"
                className="w-full min-w-[200px]"
                size="default"
              >
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="alquiler">Rent (Alquiler)</SelectItem>
                <SelectItem value="venta">Sale (Venta)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="ml-auto text-sm text-muted-foreground">
            {isFetching ? <span>Refreshing…</span> : null}
            {metadata ? (
              <span>
                Page {metadata.page} of {metadata.pages} ({metadata.total.toLocaleString()}{" "}
                total)
              </span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card className="py-0">
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
          <TableBody>
            {filteredRows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No properties match the current filters on this page.
                </TableCell>
              </TableRow>
            ) : (
              filteredRows.map((property) => {
                const isSelected = selectedPropertyId === property.id;
                return (
                  <TableRow key={property.remote_id} data-state={isSelected ? "selected" : undefined}>
                    <TableCell>
                      <div className="font-medium">{property.title}</div>
                      <div className="text-xs text-muted-foreground">#{property.remote_id}</div>
                    </TableCell>
                    <TableCell>
                      <div className="font-medium">{formatPrimaryPrice(property)}</div>
                      <div className="text-xs text-muted-foreground">
                        {formatSecondaryPrice(property)}
                      </div>
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
                          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                        >
                          Ver detalle
                        </Link>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onSelectProperty(property)}
                        >
                          Generate Contract
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
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
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
            onClick={() => setCurrentPage((page) => page + 1)}
            disabled={!canGoNext || isFetching}
          >
            Next
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}