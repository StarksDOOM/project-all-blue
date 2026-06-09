"use client";

import React from "react";
import { Calendar, Mail, MapPin, Sliders, ChevronLeft, ChevronRight } from "lucide-react";
import type { LeadCaptureRecord } from "@/lib/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface LeadsDataGridProps {
  leads: LeadCaptureRecord[];
  totalCount: number;
  currentPage: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function LeadsDataGrid({
  leads,
  totalCount,
  currentPage,
  pageSize,
  onPageChange,
}: LeadsDataGridProps) {
  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("es-DO", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatOccupancy = (val: number) => {
    return `${Math.round(val * 100)}%`;
  };

  const formatLocation = (slug: string) => {
    return slug
      .split("-")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const getSourceBadgeClass = (source: string) => {
    const s = source.toLowerCase();
    if (s.includes("ad") || s.includes("facebook") || s.includes("fb")) {
      return "bg-blue-500/10 text-blue-500 border border-blue-500/20";
    }
    if (s.includes("news") || s.includes("email") || s.includes("campaign")) {
      return "bg-purple-500/10 text-purple-500 border border-purple-500/20";
    }
    if (s.includes("google") || s.includes("search") || s.includes("seo")) {
      return "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20";
    }
    if (s === "organic") {
      return "bg-muted text-muted-foreground border border-muted-foreground/10";
    }
    return "bg-amber-500/10 text-amber-500 border border-amber-500/20";
  };

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
        <Table>
          <TableHeader className="bg-muted/50">
            <TableRow>
              <TableHead className="font-semibold text-foreground w-[180px]">
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>Date Captured</span>
                </div>
              </TableHead>
              <TableHead className="font-semibold text-foreground w-[220px]">
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span>Email</span>
                </div>
              </TableHead>
              <TableHead className="font-semibold text-foreground">
                <div className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <span>Landing Context</span>
                </div>
              </TableHead>
              <TableHead className="font-semibold text-foreground text-right w-[340px]">
                <div className="flex items-center justify-end gap-2">
                  <Sliders className="h-4 w-4 text-muted-foreground" />
                  <span>Simulation State</span>
                </div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  No se encontraron prospectos (leads) capturados.
                </TableCell>
              </TableRow>
            ) : (
              leads.map((lead) => (
                <TableRow key={lead.id} className="transition-colors hover:bg-muted/30">
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(lead.created_at)}
                  </TableCell>
                  <TableCell className="font-mono text-sm font-medium text-foreground select-all">
                    {lead.email}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-foreground/80 font-medium">
                        /invest/{lead.location_slug}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-normal">
                        ({formatLocation(lead.location_slug)})
                      </span>
                      <Badge variant="outline" className={`${getSourceBadgeClass(lead.traffic_source)} text-[10px] px-2 py-0.5 font-semibold`}>
                        {lead.traffic_source}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5 flex-wrap">
                      <Badge variant="outline" className="bg-background border-border text-foreground text-xs px-2 py-0.5 font-medium">
                        Price: {formatPrice(lead.simulated_purchase_price)}
                      </Badge>
                      <Badge variant="outline" className="bg-background border-border text-foreground text-xs px-2 py-0.5 font-medium">
                        Nightly: {formatPrice(lead.simulated_nightly_rate)}/n
                      </Badge>
                      <Badge variant="outline" className="bg-background border-border text-foreground text-xs px-2 py-0.5 font-medium">
                        Occ: {formatOccupancy(lead.simulated_occupancy)}
                      </Badge>
                      <Badge variant="outline" className="bg-background border-border text-foreground text-xs px-2 py-0.5 font-medium">
                        Maint: {formatPrice(lead.simulated_maintenance)}/m
                      </Badge>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2 py-1">
          <p className="text-xs text-muted-foreground">
            Mostrando <span className="font-medium">{leads.length}</span> de{" "}
            <span className="font-medium">{totalCount}</span> prospectos
          </p>
          <div className="flex items-center gap-2">
            <Button
              id="leads-prev-page-btn"
              variant="outline"
              size="sm"
              disabled={currentPage === 1}
              onClick={() => onPageChange(currentPage - 1)}
              className="h-8 px-2 transition-all active:scale-95"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Anterior
            </Button>
            <span className="text-xs font-medium text-foreground">
              Página {currentPage} de {totalPages}
            </span>
            <Button
              id="leads-next-page-btn"
              variant="outline"
              size="sm"
              disabled={currentPage === totalPages}
              onClick={() => onPageChange(currentPage + 1)}
              className="h-8 px-2 transition-all active:scale-95"
            >
              Siguiente
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
