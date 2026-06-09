"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Landmark, Users, ExternalLink, Copy, Check, BarChart3 } from "lucide-react";

import { api } from "@/lib/api";
import { leadKeys } from "@/lib/query-keys";
import { LeadsListResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LeadsDataGrid } from "@/components/leads/LeadsDataGrid";

const LEAD_MAGNET_CONFIGS = [
  { slug: "punta-cana", name: "Punta Cana", adr: 169, occ: 0.45 },
  { slug: "las-terrenas", name: "Las Terrenas", adr: 234, occ: 0.40 },
  { slug: "santo-domingo", name: "Santo Domingo", adr: 80, occ: 0.40 },
];

export default function LeadsDashboardPage() {
  const router = useRouter();
  const [userRole, setUserRole] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);
  
  const pageSize = 25; // 25 leads per page
  const skip = (currentPage - 1) * pageSize;

  useEffect(() => {
    document.title = "Registro de Prospectos | All Blue";
  }, []);

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
        setUserRole(role.toLowerCase());
        setIsAuthenticated(true);
      } catch {
        setUserRole(null);
        setIsAuthenticated(false);
      }
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<LeadsListResponse>({
    queryKey: leadKeys.list(skip, pageSize),
    queryFn: () => api.getLeads(skip, pageSize),
    enabled: isAuthenticated && (userRole === "agent" || userRole === "admin"),
    staleTime: 30_000,
  });

  const getLeadCountForSlug = (slug: string) => {
    if (!data?.data) return 0;
    // Note: since the list is paginated, to get a global count we could use global endpoint,
    // but counting within the loaded page or showing "captured leads" is a helpful snapshot.
    // In our case, total count per slug might be filtered locally or we can state that it reflects the current view.
    return data.data.filter((lead) => lead.location_slug === slug).length;
  };

  const handleCopyLink = (slug: string) => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    const url = `${origin}/invest/${slug}?src=agent-share`;
    navigator.clipboard.writeText(url);
    setCopiedSlug(slug);
    setTimeout(() => setCopiedSlug(null), 2000);
  };

  // Authorization check screen
  if (isAuthenticated && userRole !== "agent" && userRole !== "admin") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12 text-center sm:px-6 lg:px-8">
        <Card className="w-full max-w-md border-destructive/30 bg-destructive/5 shadow-lg">
          <CardHeader>
            <Landmark className="mx-auto h-12 w-12 text-destructive" />
            <CardTitle className="mt-4 text-xl font-bold tracking-tight text-destructive">Acceso Denegado</CardTitle>
            <CardDescription className="mt-2 text-sm text-muted-foreground">
              No tienes permisos suficientes para ver el registro de prospectos (leads) de la agencia.
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-4">
            <Button
              id="back-home-denied-btn"
              variant="outline"
              onClick={() => router.push("/")}
              className="w-full transition-all hover:bg-muted"
            >
              <ArrowLeft className="mr-2 h-4 w-4" /> Volver a Propiedades
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-muted/30 p-6 md:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Header Section */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Registro de Prospectos (Leads)</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Monitorea y visualiza los leads de inversionistas capturados por el motor de lead magnets.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              id="refresh-leads-btn"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isLoading || isFetching}
              className="h-9 px-3 transition-all active:scale-95"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
              Actualizar
            </Button>
            <Button
              id="back-home-btn"
              variant="outline"
              size="sm"
              onClick={() => router.push("/")}
              className="h-9 px-3 transition-all hover:bg-muted"
            >
              <ArrowLeft className="mr-2 h-4 w-4" /> Volver
            </Button>
          </div>
        </div>

        {/* Lead Magnet Directories Section */}
        <div>
          <h2 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-primary" />
            <span>Directorio de Lead Magnets Activos</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {LEAD_MAGNET_CONFIGS.map((config) => {
              const count = getLeadCountForSlug(config.slug);
              return (
                <Card key={config.slug} className="border border-border bg-card shadow-sm hover:shadow-md transition-shadow">
                  <CardHeader className="pb-2">
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-base font-bold text-foreground">{config.name}</CardTitle>
                        <CardDescription className="text-xs">/invest/{config.slug}</CardDescription>
                      </div>
                      <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 text-[10px] font-semibold">
                        {count} leads (pág)
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="text-xs text-muted-foreground space-y-1">
                      <div className="flex justify-between">
                        <span>Configured ADR:</span>
                        <span className="font-semibold text-foreground">${config.adr}/n</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Configured Occ:</span>
                        <span className="font-semibold text-foreground">{config.occ * 100}%</span>
                      </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => window.open(`/invest/${config.slug}`, "_blank")}
                        className="flex-1 text-[11px] h-7 px-2 hover:bg-muted"
                      >
                        <ExternalLink className="h-3 w-3 mr-1" />
                        Preview
                      </Button>
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => handleCopyLink(config.slug)}
                        className="flex-1 text-[11px] h-7 px-2 hover:bg-muted"
                      >
                        {copiedSlug === config.slug ? (
                          <>
                            <Check className="h-3 w-3 mr-1 text-emerald-500" />
                            Copied!
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3 mr-1" />
                            Copy Link
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Content Area */}
        {isLoading ? (
          <Card className="border-none shadow-md">
            <CardContent className="flex h-64 items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <RefreshCw className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Cargando prospectos...</p>
              </div>
            </CardContent>
          </Card>
        ) : isError ? (
          <Card className="border-destructive/30 bg-destructive/5 shadow-md">
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-destructive">Error al Cargar Registro</CardTitle>
              <CardDescription className="text-sm text-destructive/80">
                {(error as Error)?.message || "Ocurrió un error inesperado al conectar con el servidor."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button id="retry-leads-btn" variant="outline" onClick={() => refetch()}>
                Reintentar
              </Button>
            </CardContent>
          </Card>
        ) : !data || data.data.length === 0 ? (
          <Card className="border-none py-12 text-center shadow-md">
            <CardContent className="flex flex-col items-center justify-center space-y-4">
              <div className="rounded-full bg-muted p-4">
                <Users className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-medium text-foreground">No se encontraron prospectos</h3>
                <p className="text-sm text-muted-foreground">
                  Aún no se han capturado prospectos a través de las calculadoras públicas.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <span>Prospectos Registrados</span>
            </h2>
            <LeadsDataGrid
              leads={data.data}
              totalCount={data.total}
              currentPage={currentPage}
              pageSize={pageSize}
              onPageChange={(p) => setCurrentPage(p)}
            />
          </div>
        )}
      </div>
    </main>
  );
}
