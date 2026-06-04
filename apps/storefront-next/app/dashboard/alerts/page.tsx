"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Trash2, Bell, BellOff } from "lucide-react";

import { api } from "@/lib/api";
import { savedSearchKeys } from "@/lib/query-keys";
import { SavedSearchAlert } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const DEMO_USER_ID = "11111111-1111-1111-1111-111111111111";

function formatFilterChips(filters: Record<string, unknown>): React.ReactNode {
  const chips: string[] = [];
  if (filters.sector) chips.push(String(filters.sector));
  if (filters.property_type) chips.push(filters.property_type === "venta" ? "Venta" : "Alquiler");
  if (typeof filters.bedrooms_min === "number") chips.push(`${filters.bedrooms_min}+ hab`);
  if (typeof filters.bathrooms_min === "number") chips.push(`${filters.bathrooms_min}+ baños`);
  if (typeof filters.price_min === "number" || typeof filters.price_max === "number") {
    const lo = typeof filters.price_min === "number" ? `$${Math.round(filters.price_min / 1000)}k` : "";
    const hi = typeof filters.price_max === "number" ? `$${Math.round(filters.price_max / 1000)}k` : "";
    chips.push(`${lo}${lo && hi ? "–" : ""}${hi}`);
  }
  if (filters.agency) chips.push(String(filters.agency));
  if (filters.keyword) chips.push(`q:${filters.keyword}`);
  if (chips.length === 0) chips.push("Todos los filtros");
  return chips.map((c, i) => (
    <Badge key={i} variant="secondary" className="text-[10px]">
      {c}
    </Badge>
  ));
}

export default function SavedSearchAlertsPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: savedSearchKeys.list(DEMO_USER_ID),
    queryFn: () => api.listSavedSearchAlerts(DEMO_USER_ID),
    staleTime: 30_000,
  });

  const updateMut = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { is_active?: boolean; title?: string } }) =>
      api.updateSavedSearchAlert(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: savedSearchKeys.all }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteSavedSearchAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: savedSearchKeys.all }),
  });

  const alerts = data?.data ?? [];

  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Mis Alertas de Búsqueda</h1>
            <p className="text-sm text-muted-foreground">
              Gestiona las búsquedas guardadas. Las alertas activas se evaluarán contra nuevas propiedades en el pipeline de ingestión.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => router.push("/") }>
            ← Volver al dashboard de propiedades
          </Button>
        </div>

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Card key={i} className="h-48 animate-pulse bg-muted/60" />
            ))}
          </div>
        ) : isError ? (
          <Card className="border-destructive/30 bg-destructive/5">
            <CardContent className="pt-6 text-sm text-destructive">
              Error cargando alertas: {(error as Error)?.message ?? "desconocido"}
            </CardContent>
          </Card>
        ) : alerts.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              Aún no tienes alertas guardadas. Aplica filtros en el panel principal y haz clic en
              “Guardar Alerta de Búsqueda”.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {alerts.map((alert: SavedSearchAlert) => {
              const isActive = alert.is_active;
              return (
                <Card key={alert.id} className={!isActive ? "opacity-70" : undefined}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <CardTitle className="flex items-center gap-2 text-lg">
                          {isActive ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
                          <span className="truncate">{alert.title}</span>
                        </CardTitle>
                        <CardDescription className="mt-0.5 text-xs">
                          Creada {new Date(alert.created_at).toLocaleDateString()} · {isActive ? "Activa" : "Silenciada"}
                        </CardDescription>
                      </div>
                      <Badge variant={isActive ? "default" : "outline"} className="shrink-0">
                        {isActive ? "Activa" : "Mute"}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    <div className="flex flex-wrap gap-1.5">
                      {formatFilterChips(alert.filters_json as Record<string, unknown>)}
                    </div>

                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          updateMut.mutate({
                            id: alert.id,
                            patch: { is_active: !isActive },
                          })
                        }
                        disabled={updateMut.isPending || deleteMut.isPending}
                      >
                        {isActive ? "Silenciar notificaciones" : "Reactivar alerta"}
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => {
                          if (confirm(`¿Eliminar la alerta “${alert.title}”?`)) {
                            deleteMut.mutate(alert.id);
                          }
                        }}
                        disabled={updateMut.isPending || deleteMut.isPending}
                      >
                        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                        Eliminar
                      </Button>
                    </div>

                    {alert.last_matched_at ? (
                      <p className="text-[11px] text-muted-foreground">
                        Último match: {new Date(alert.last_matched_at).toLocaleString()}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        <p className="pt-4 text-center text-[11px] text-muted-foreground">
          Las coincidencias se registran en segundo plano al ingerir nuevas propiedades (ver spec PHASE 3.0).
          User ID demo: {DEMO_USER_ID}
        </p>
      </div>
    </main>
  );
}
