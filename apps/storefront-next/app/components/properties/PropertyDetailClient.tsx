"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Bath,
  BedDouble,
  Mail,
  Maximize2,
  MapPin,
  Phone,
  UserCircle,
} from "lucide-react";

import { PortalOriginalLink } from "@/components/properties/PortalOriginalLink";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getPropertyDetail, api } from "@/lib/api";
import { propertyKeys, analyticsKeys } from "@/lib/query-keys";
import {
  formatPrimaryPrice,
  formatSecondaryPrice,
  hasPortalListPrice,
} from "@/lib/pricing";
import { PropertyListing, WholesaleDealMetrics } from "@/lib/types";

const ContractDrawer = dynamic(
  () => import("@/components/properties/ContractDrawer"),
  { ssr: false, loading: () => null }
);
const TransactionContractModal = dynamic(
  () =>
    import("@/components/transactions/TransactionContractModal").then(
      (mod) => mod.TransactionContractModal
    ),
  { ssr: false }
);
const PropertyImageGallery = dynamic(
  () =>
    import("@/components/properties/PropertyImageGallery").then(
      (mod) => mod.PropertyImageGallery
    ),
  { loading: () => <Skeleton className="h-64 w-full rounded-lg" /> }
);

function formatBaths(value: number | null): string {
  if (value == null || value <= 0) return "—";
  const label = value === 1 ? "Baño" : "Baños";
  return `${value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)} ${label}`;
}

function formatBeds(value: number | null): string {
  if (value == null || value <= 0) return "—";
  return `${value} ${value === 1 ? "Habitación" : "Habitaciones"}`;
}

function formatAreaDetail(construction: number | null, land: number | null): string {
  const parts: string[] = [];
  if (construction != null && construction > 0) {
    parts.push(`${construction.toLocaleString("en-US")} m² construcción`);
  }
  if (land != null && land > 0) {
    parts.push(`${land.toLocaleString("en-US")} m² terreno`);
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function formatDescriptionText(raw: string): string {
  if (!raw.trim()) {
    return "Sin descripción disponible para este inmueble.";
  }
  if (raw.includes("\n\n")) {
    const [, ...bodyParts] = raw.split("\n\n");
    const body = bodyParts.join("\n\n").trim();
    if (body.length > 0) return body;
  }
  const segments = raw.split("|").map((segment) => segment.trim()).filter(Boolean);
  if (segments.length <= 1) return segments[0] ?? raw;
  const looksLikeMetadata = segments.every(
    (segment) =>
      segment.includes("=") ||
      segment.length < 80 ||
      /^(Apartamento|Casa|Venta|Alquiler|Local|Terreno)/i.test(segment)
  );
  return looksLikeMetadata ? segments.join("\n") : segments.join("\n\n");
}

function PropertyDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="h-6 w-1/3" />
      <Skeleton className="h-64 w-full rounded-lg" />
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-28 w-full" />
      </div>
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

interface PropertyDetailClientProps {
  propertyId: string;
}

export function PropertyDetailClient({ propertyId }: PropertyDetailClientProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState<PropertyListing | null>(null);
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);

  const { data: detailResult, isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: propertyKeys.detail(propertyId, "portal"),
    queryFn: () =>
      getPropertyDetail(propertyId, { refreshFromPortal: true }),
    enabled: propertyId.length > 0,
    staleTime: 120_000,
    refetchOnMount: false,
    retry: 1,
    retryDelay: 1500,
  });

  const property = detailResult?.property ?? null;
  const portalRefreshFailed = detailResult?.portalRefreshFailed ?? false;
  const portalRefreshMessage = detailResult?.portalRefreshMessage;
  const secondaryPrice = property ? formatSecondaryPrice(property) : null;

  const [userRole, setUserRole] = useState<string | null>(null);
  const [alertInfo, setAlertInfo] = useState<{ type: "success" | "error"; title: string; message: string } | null>(null);

  const isAgentOrAdmin = userRole === "agent" || userRole === "admin";
  const propertyBluId = property?.blu_id || property?.remote_id || "";

  const { data: wholesaleData, isLoading: isWholesaleLoading } = useQuery<WholesaleDealMetrics>({
    queryKey: analyticsKeys.wholesale(propertyBluId),
    queryFn: () => api.getWholesaleAnalytics(propertyBluId),
    enabled: isAgentOrAdmin && propertyBluId.length > 0,
    staleTime: 300_000,
    retry: false,
  });

  useEffect(() => {
    const token = window.localStorage.getItem("supabase-access-token");
    if (token) {
      try {
        const base64Url = token.split(".")[1];
        const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
        const jsonPayload = decodeURIComponent(
          window.atob(base64)
            .split("")
            .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
            .join("")
        );
        const payload = JSON.parse(jsonPayload);
        const role = payload?.app_metadata?.role || payload?.user_metadata?.role || "client";
        setUserRole(role);
      } catch {
        setUserRole(null);
      }
    }
  }, []);

  useEffect(() => {
    if (alertInfo) {
      const timer = setTimeout(() => {
        setAlertInfo(null);
      }, 8000);
      return () => clearTimeout(timer);
    }
  }, [alertInfo]);

  const { mutate: generateDirectContract, isPending: isGenerating } = useMutation({
    mutationFn: () => {
      if (!property) throw new Error("Inmueble no cargado.");
      return api.generateContract(property.blu_id || property.remote_id);
    },
    onSuccess: (data) => {
      setAlertInfo({
        type: "success",
        title: "Contrato DocuSign Generado",
        message: `El contrato ha sido enviado para firmas. Envelope ID: ${data.envelope_id}`,
      });
    },
    onError: (err: any) => {
      setAlertInfo({
        type: "error",
        title: "Error de Generación",
        message: err.message || "Ocurrió un error al generar el contrato.",
      });
    },
  });

  return (
    <main className="min-h-screen bg-muted/40 pb-32">
      <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
        <div className="mb-6">
          <Link
            href="/"
            className="text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            ← Volver al inventario
          </Link>
        </div>

        {isLoading && !property ? <PropertyDetailSkeleton /> : null}

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
              {portalRefreshFailed ? (
                <Alert variant="warning">
                  <AlertTitle>Sincronización con portal no disponible</AlertTitle>
                  <AlertDescription>
                    {portalRefreshMessage ??
                      "Live portal sync failed; displaying last known data."}
                  </AlertDescription>
                </Alert>
              ) : null}

              <header className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
                    {property.title}
                  </h1>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isFetching}
                    onClick={() => refetch()}
                  >
                    {isFetching ? "Sincronizando…" : "Sincronizar con portal"}
                  </Button>
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

              <PropertyImageGallery images={property.image_urls} title={property.title} />

              <Card className="border-slate-300 bg-slate-950 text-white shadow-md">
                <CardHeader>
                  <CardDescription className="text-slate-400">Precio</CardDescription>
                  <CardTitle className="text-3xl font-bold text-white md:text-4xl">
                    {formatPrimaryPrice(property)}
                  </CardTitle>
                  {property.business_type === "alquiler" && hasPortalListPrice(property) ? (
                    <p className="text-sm font-medium text-emerald-300">Precio de alquiler mensual</p>
                  ) : null}
                  {secondaryPrice ? (
                    <p className="text-sm text-slate-400">
                      Equivalente en otra moneda · {secondaryPrice}
                    </p>
                  ) : null}
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
                    <p className="text-lg font-semibold leading-snug text-slate-900">
                      {formatAreaDetail(property.area_mt2, property.sqm_land)}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {property.agent_name ? (
                <Card>
                  <CardHeader className="flex flex-row items-center gap-3 space-y-0 pb-2">
                    <UserCircle className="h-5 w-5 text-slate-600" aria-hidden />
                    <div>
                      <CardTitle className="text-base">Contacto del agente</CardTitle>
                      {property.agent_agency ? (
                        <CardDescription>{property.agent_agency}</CardDescription>
                      ) : null}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="font-medium text-slate-900">{property.agent_name}</p>
                    <div className="flex flex-wrap gap-2">
                      {property.agent_phone ? (
                        <a
                          href={`tel:${property.agent_phone}`}
                          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                        >
                          <Phone className="h-4 w-4" />
                          {property.agent_phone}
                        </a>
                      ) : null}
                      {property.agent_whatsapp ? (
                        <a
                          href={property.agent_whatsapp}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={cn(buttonVariants({ variant: "default", size: "sm" }))}
                        >
                          WhatsApp
                        </a>
                      ) : null}
                      {property.agent_email ? (
                        <a
                          href={`mailto:${property.agent_email}`}
                          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                        >
                          <Mail className="h-4 w-4" />
                          Email
                        </a>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              ) : null}

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

              <PortalOriginalLink storedUrl={property.url} remoteId={property.remote_id} />

              {isAgentOrAdmin ? (
                <Card className="border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-lg">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base font-semibold text-white">
                      <span className="text-amber-400">📊</span>
                      {userRole === "admin" ? "Guía de Oferta — Desglose Completo" : "Guía de Oferta"}
                    </CardTitle>
                    <CardDescription className="text-slate-400 text-xs">
                      Métricas calculadas automáticamente · sector {property.sector ?? "—"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {isWholesaleLoading ? (
                      <div className="space-y-2">
                        <Skeleton className="h-5 w-2/3 bg-slate-700" />
                        <Skeleton className="h-5 w-1/2 bg-slate-700" />
                      </div>
                    ) : wholesaleData ? (
                      <div className="space-y-3">
                        {userRole === "admin" && (
                          <>
                            <div className="flex items-center justify-between border-b border-slate-700 pb-2 text-sm">
                              <span className="text-slate-400">Mediana sector (USD/m²)</span>
                              <span className="font-mono font-semibold text-slate-200">
                                ${wholesaleData.sector_median_price_per_sqm.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                              </span>
                            </div>
                            <div className="flex items-center justify-between border-b border-slate-700 pb-2 text-sm">
                              <span className="text-slate-400">EMV Estimado</span>
                              <span className="font-mono font-semibold text-slate-200">
                                ${wholesaleData.auto_emv.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                              </span>
                            </div>
                            <div className="flex items-center justify-between border-b border-slate-700 pb-2 text-sm">
                              <span className="text-slate-400">Margen de Asignación</span>
                              <span className="font-mono font-semibold text-amber-400">
                                ${wholesaleData.assignment_fee.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                              </span>
                            </div>
                          </>
                        )}
                        <div className="flex items-center justify-between rounded-lg bg-slate-700/60 px-3 py-2">
                          <span className="text-sm font-medium text-slate-300">Oferta Máxima al Vendedor</span>
                          <span className="font-mono text-lg font-bold text-emerald-400">
                            ${wholesaleData.mao.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                        <div className="flex items-center justify-between rounded-lg bg-blue-600/30 px-3 py-2 ring-1 ring-blue-500/40">
                          <span className="text-sm font-semibold text-blue-200">Precio para Inversionista</span>
                          <span className="font-mono text-lg font-bold text-white">
                            ${wholesaleData.pitch_price.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">No se pudo calcular. Verifique que la propiedad esté activa.</p>
                    )}
                  </CardContent>
                </Card>
              ) : null}
            </div>

            {isDrawerOpen && selectedProperty ? (
              <div className="w-full shrink-0 lg:sticky lg:top-8 lg:w-[380px]">
                <ContractDrawer property={selectedProperty} onClose={() => {
                  setIsDrawerOpen(false);
                  setSelectedProperty(null);
                }} />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {property ? (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-4 shadow-[0_-8px_30px_rgba(15,23,42,0.12)] backdrop-blur md:px-8">
          <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Acción</p>
              <p className="truncate text-sm font-medium text-slate-900">{property.title}</p>
            </div>
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              {(userRole === "agent" || userRole === "admin" || !userRole) && (
                <Button
                  size="lg"
                  variant="default"
                  className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-all duration-200"
                  onClick={() => generateDirectContract()}
                  disabled={isGenerating}
                >
                  {isGenerating ? "Enviando a DocuSign..." : "DocuSign Directo"}
                </Button>
              )}
              <Button size="lg" className="w-full sm:w-auto" onClick={() => setIsTransactionModalOpen(true)}>
                Generar Contrato
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="w-full sm:w-auto"
                onClick={() => {
                  setSelectedProperty(property);
                  setIsDrawerOpen(true);
                }}
              >
                SRL (legacy)
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {property ? (
        <TransactionContractModal
          property={property}
          open={isTransactionModalOpen}
          onOpenChange={setIsTransactionModalOpen}
        />
      ) : null}

      {alertInfo ? (
        <div className="fixed right-4 top-4 z-50 max-w-md animate-in slide-in-from-top-5 duration-300">
          <div
            className={cn(
              "rounded-xl border p-4 shadow-xl backdrop-blur-md transition-all duration-300",
              alertInfo.type === "success"
                ? "border-emerald-500/30 bg-emerald-950/90 text-emerald-50"
                : "border-red-500/30 bg-red-950/90 text-red-50"
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="font-semibold tracking-wide text-sm">{alertInfo.title}</p>
                <p className="text-xs opacity-90 leading-relaxed font-mono break-all">{alertInfo.message}</p>
              </div>
              <button
                type="button"
                onClick={() => setAlertInfo(null)}
                className="rounded-lg p-1 hover:bg-white/10 transition-colors text-white/70 hover:text-white"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}