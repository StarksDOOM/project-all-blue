"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, FileText, RefreshCw, Landmark } from "lucide-react";

import { api } from "@/lib/api";
import { contractKeys } from "@/lib/query-keys";
import { DashboardContract } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function ContractsDashboardPage() {
  const router = useRouter();
  const [userRole, setUserRole] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  useEffect(() => {
    document.title = "Registro de Transacciones | All Blue";
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

  const { data: contracts, isLoading, isError, error, refetch, isFetching } = useQuery<DashboardContract[]>({
    queryKey: contractKeys.list(),
    queryFn: () => api.listContracts(),
    enabled: isAuthenticated && (userRole === "agent" || userRole === "admin"),
    staleTime: 30_000,
  });

  // Authorization check screen
  if (isAuthenticated && userRole !== "agent" && userRole !== "admin") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12 text-center sm:px-6 lg:px-8">
        <Card className="w-full max-w-md border-destructive/30 bg-destructive/5 shadow-lg">
          <CardHeader>
            <Landmark className="mx-auto h-12 w-12 text-destructive" />
            <CardTitle className="mt-4 text-xl font-bold tracking-tight text-destructive">Acceso Denegado</CardTitle>
            <CardDescription className="mt-2 text-sm text-muted-foreground">
              No tienes permisos suficientes para ver el registro de contratos de la agencia.
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

  // Helper for status badge rendering
  const renderStatusBadge = (status: string | null) => {
    const s = status?.toLowerCase() || "unknown";
    if (s === "executed" || s === "completed") {
      return (
        <Badge className="bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 hover:bg-emerald-500/20 font-medium px-2.5 py-0.5 rounded text-xs transition-colors duration-200">
          Firmado
        </Badge>
      );
    }
    if (s === "pending_signature" || s === "sent") {
      return (
        <Badge className="bg-amber-500/10 text-amber-500 border border-amber-500/20 hover:bg-amber-500/20 font-medium px-2.5 py-0.5 rounded text-xs transition-colors duration-200">
          Pendiente
        </Badge>
      );
    }
    if (s === "declined") {
      return (
        <Badge className="bg-rose-500/10 text-rose-500 border border-rose-500/20 hover:bg-rose-500/20 font-medium px-2.5 py-0.5 rounded text-xs transition-colors duration-200">
          Rechazado
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="text-muted-foreground font-medium px-2.5 py-0.5 rounded text-xs transition-colors duration-200">
        {status || "Desconocido"}
      </Badge>
    );
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(price);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("es-DO", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <main className="min-h-screen bg-muted/30 p-6 md:p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Header Section */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Registro de Transacciones</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Monitorea el estado y el historial de firmas de los contratos de reserva generados en All Blue.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              id="refresh-contracts-btn"
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

        {/* Content Area */}
        {isLoading ? (
          <Card className="border-none shadow-md">
            <CardContent className="flex h-64 items-center justify-center">
              <div className="flex flex-col items-center gap-2">
                <RefreshCw className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Cargando contratos...</p>
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
              <Button id="retry-contracts-btn" variant="outline" onClick={() => refetch()}>
                Reintentar
              </Button>
            </CardContent>
          </Card>
        ) : !contracts || contracts.length === 0 ? (
          <Card className="border-none py-12 text-center shadow-md">
            <CardContent className="flex flex-col items-center justify-center space-y-4">
              <div className="rounded-full bg-muted p-4">
                <FileText className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-medium text-foreground">No se encontraron contratos</h3>
                <p className="text-sm text-muted-foreground">
                  Aún no has generado ningún contrato de reserva para propiedades.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="overflow-hidden border-none shadow-md">
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow>
                  <TableHead className="font-semibold text-foreground w-[160px]">ID de Contrato</TableHead>
                  <TableHead className="font-semibold text-foreground">Propiedad</TableHead>
                  <TableHead className="font-semibold text-foreground text-right w-[150px]">Precio Pactado</TableHead>
                  <TableHead className="font-semibold text-foreground w-[180px]">Fecha de Creación</TableHead>
                  <TableHead className="font-semibold text-foreground w-[130px]">Estado Firma</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contracts.map((contract) => (
                  <TableRow key={contract.id} className="transition-colors hover:bg-muted/30">
                    <TableCell className="font-mono text-xs text-muted-foreground select-all">
                      {contract.id.substring(0, 8)}...
                    </TableCell>
                    <TableCell className="font-medium text-foreground max-w-[280px] truncate">
                      {contract.property?.title || "Borrador de Inmueble"}
                    </TableCell>
                    <TableCell className="text-right font-semibold text-foreground">
                      {contract.property ? formatPrice(contract.property.price_usd) : "N/D"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(contract.created_at)}
                    </TableCell>
                    <TableCell>
                      {renderStatusBadge(contract.status)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </main>
  );
}
