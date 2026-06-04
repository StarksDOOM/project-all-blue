"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function methodBadgeVariant(
  method: string
): "default" | "secondary" | "outline" | "destructive" {
  if (method === "json" || method === "api") {
    return "secondary";
  }
  if (method === "dom") {
    return "outline";
  }
  return "default";
}

export function ScraperErrorMatrix() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["admin-scraper-errors"],
    queryFn: () => api.getScraperErrors({ resolved: false, limit: 100 }),
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="space-y-3 pt-6">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>No se pudo cargar telemetría</AlertTitle>
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    );
  }

  const rows = data?.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Scraper error matrix</CardTitle>
        <CardDescription>
          Unresolved RE/MAX parse/enrichment failures ({data?.total ?? 0} rows)
        </CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Sin errores pendientes</AlertTitle>
            <AlertDescription>
              No hay fallos de scraper sin resolver en la base de datos.
            </AlertDescription>
          </Alert>
        ) : (
          <div className="overflow-x-auto rounded-md border border-slate-200">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Remote ID</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead>URL</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-nowrap text-xs text-slate-600">
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {row.remote_id ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={methodBadgeVariant(row.scraper_method)}>
                        {row.scraper_method}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm font-medium text-red-800">
                      {row.error_type}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-xs text-slate-600">
                      {row.url ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}