"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bath, BedDouble, ExternalLink, Maximize2, MapPin } from "lucide-react";
import ContractDrawer from "@/components/properties/ContractDrawer";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getPropertyDetail } from "@/lib/api";
import { PropertyListing } from "@/lib/types";

function formatBaths(value: number | null): string {
  if (value == null || value <= 0) {
    return "—";
  }
  const label = value === 1 ? "Baño" : "Baños";
  return `${value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)} ${label}`;
}

function formatBeds(value: number | null): string {
  if (value == null || value <= 0) {
    return "—";
  }
  return `${value} ${value === 1 ? "Habitación" : "Habitaciones"}`;
}

function formatArea(value: number | null): string {
  if (value == null || value <= 0) {
    return "—";
  }
  return `${value.toLocaleString("en-US")} m²`;
}

function formatPrimaryPrice(property: PropertyListing): string {
  if (property.currency === "DOP") {
    return `RD$${property.price_raw.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  }
  return `$${property.price_raw.toLocaleString("en-US", { maximumFractionDigits: 0 })} USD`;
}

function formatUsdSecondary(property: PropertyListing): string {
  const usd =
    property.currency === "DOP"
      ? property.price_usd
      : property.price_raw;
  return `$${usd.toLocaleString("en-US", { maximumFractionDigits: 0 })} USD`;
}



/** Present raw_description with readable line breaks (portal metadata uses pipe segments). */
function formatDescriptionText(raw: string): string {
  if (!raw.trim()) {
    return "Sin descripción disponible para este inmueble.";
  }
  return raw
    .split("|")
    .map((segment) => segment.trim())
    .filter(Boolean)
    .join("\n\n");
}

function PropertyDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="h-6 w-1/3" />
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-14 w-full" />
    </div>
  );
}

export default function PropertyDetailPage() {
  const params = useParams();
  const propertyId = typeof params.id === "string" ? params.id : "";

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);

  const { data: property, isLoading, isError, error } = useQuery({
    queryKey: ["property-detail", propertyId],
    queryFn: () => getPropertyDetail(propertyId),
    enabled: propertyId.length > 0,
  });

  const handleOpenContractDrawer = () => {
    if (!property) {
      return;
    }
    setSelectedProperty(property);
    setIsDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedProperty(null);
  };

  return (
    <main className="min-h-screen bg-slate-100 pb-32">
      <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
        <div className="mb-6">
          <Link
            href="/"
            className="text-sm font-medium text-slate-600 underline-offset-2 hover:text-slate-900 hover:underline"
          >
            ← Volver al inventario
          </Link>
        </div>

        {isLoading ? <PropertyDetailSkeleton /> : null}

        {isError ? (
          <Card className="border-red-200 bg-red-50">
            <CardHeader>
              <CardTitle className="text-red-800">No se pudo cargar el inmueble</CardTitle>
              <CardDescription className="text-red-700">
                {(error as Error).message}
              </CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {property ? (
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
            <div className="min-w-0 flex-1 space-y-6">
              <header className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
                    {property.title}
                  </h1>
                  {property.is_active ? (
                    <Badge className="border-transparent bg-emerald-600 text-white hover:bg-emerald-600/90">
                      Disponible
                    </Badge>
                  ) : (
                    <Badge variant="outline">No disponible</Badge>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-slate-600">
                  <MapPin className="h-4 w-4 shrink-0" aria-hidden />
                  <span className="font-medium">{property.sector}</span>
                  <span className="text-slate-400">·</span>
                  <span>{property.province}</span>
                  <span className="text-slate-400">·</span>
                  <span className="capitalize">{property.business_type}</span>
                  <span className="text-slate-400">·</span>
                  <span className="font-mono text-xs text-slate-500">#{property.remote_id}</span>
                </div>
              </header>

              <Card className="border-slate-300 bg-slate-950 text-white shadow-md">
                <CardHeader>
                  <CardDescription className="text-slate-400">Precio</CardDescription>
                  <CardTitle className="text-3xl font-bold text-white md:text-4xl">
                    {formatPrimaryPrice(property)}
                  </CardTitle>
                  {property.currency === "DOP" ? (
                    <p className="text-base text-slate-300">{formatUsdSecondary(property)}</p>
                  ) : (
                    <p className="text-sm text-slate-400">
                      Referencia en dólares para trámites contractuales
                    </p>
                  )}

                </CardHeader>
              </Card>

              <div className="grid gap-4 sm:grid-cols-3">
                <Card>
                  <CardHeader className="flex flex-row items-center gap-3 space-y-0 pb-2">
                    <BedDouble className="h-5 w-5 text-slate-600" aria-hidden />
                    <CardTitle className="text-base">Habitaciones</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold text-slate-900">{formatBeds(property.beds)}</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center gap-3 space-y-0 pb-2">
                    <Bath className="h-5 w-5 text-slate-600" aria-hidden />
                    <CardTitle className="text-base">Baños</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold text-slate-900">
                      {formatBaths(property.baths)}
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center gap-3 space-y-0 pb-2">
                    <Maximize2 className="h-5 w-5 text-slate-600" aria-hidden />
                    <CardTitle className="text-base">Área</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-semibold text-slate-900">
                      {formatArea(property.area_mt2)}
                    </p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Descripción</CardTitle>
                  <CardDescription>Detalle del listado en portal {property.source_portal}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                      {formatDescriptionText(property.raw_description)}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {property.url ? (
                <a
                  href={property.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                >
                  <ExternalLink className="h-4 w-4" />
                  Ver en portal original
                </a>
              ) : null}
            </div>

            {isDrawerOpen && selectedProperty ? (
              <div className="w-full shrink-0 lg:sticky lg:top-8 lg:w-[380px]">
                <ContractDrawer property={selectedProperty} onClose={handleCloseDrawer} />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {property ? (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-4 shadow-[0_-8px_30px_rgba(15,23,42,0.12)] backdrop-blur md:px-8">
          <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Acción
              </p>
              <p className="truncate text-sm font-medium text-slate-900">{property.title}</p>
            </div>
            <Button size="lg" className="w-full sm:w-auto" onClick={handleOpenContractDrawer}>
              Iniciar Trámite de Contrato
            </Button>
          </div>
        </div>
      ) : null}
    </main>
  );
}