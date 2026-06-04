"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";

import { api } from "@/lib/api";
import { savedSearchKeys } from "@/lib/query-keys";
import { useFilterParams } from "@/hooks/useFilterParams";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Demo user id until JWT/tenant auth is implemented (see spec §4). */
const DEMO_USER_ID = "11111111-1111-1111-1111-111111111111";

function deriveDefaultTitle(filters: ReturnType<typeof useFilterParams>["appliedFilters"]): string {
  const parts: string[] = [];
  if (filters.sector) parts.push(filters.sector);
  if (filters.property_type) parts.push(filters.property_type === "venta" ? "Venta" : "Alquiler");
  if (filters.bedrooms_min) parts.push(`${filters.bedrooms_min}+ hab`);
  if (filters.price_min || filters.price_max) {
    const pmin = filters.price_min ? `$${Math.round(filters.price_min / 1000)}k` : "";
    const pmax = filters.price_max ? `$${Math.round(filters.price_max / 1000)}k` : "";
    parts.push(`${pmin}${pmin && pmax ? "-" : ""}${pmax}`);
  }
  if (filters.keyword) parts.push(`"${filters.keyword}"`);
  const base = parts.length ? parts.join(" · ") : "Búsqueda personalizada";
  return `Alerta ${base}`;
}

export function useCreateSearchAlert() {
  const { appliedFilters } = useFilterParams();
  const queryClient = useQueryClient();

  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (chosenTitle: string) => {
      // Capture live applied state (post debounce) at submit time
      const filtersForSave = {
        ...appliedFilters,
        page: undefined, // never persist pagination
      };
      return api.createSavedSearchAlert({
        user_id: DEMO_USER_ID,
        title: chosenTitle.trim(),
        filters: filtersForSave,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: savedSearchKeys.all });
      setOpen(false);
      setTitle("");
      setSubmitError(null);
    },
    onError: (err: unknown) => {
      setSubmitError(err instanceof Error ? err.message : "No se pudo guardar la alerta");
    },
  });

  const openDialog = () => {
    const defaultTitle = deriveDefaultTitle(appliedFilters);
    setTitle(defaultTitle);
    setSubmitError(null);
    setOpen(true);
  };

  const closeDialog = () => {
    if (!mutation.isPending) {
      setOpen(false);
      setSubmitError(null);
    }
  };

  const handleSubmit = () => {
    const trimmed = title.trim();
    if (!trimmed) {
      setSubmitError("El título es requerido");
      return;
    }
    mutation.mutate(trimmed);
  };

  const dialog = (
    <Dialog open={open} onOpenChange={(next) => (!next ? closeDialog() : setOpen(true))}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" /> Guardar Alerta de Búsqueda
          </DialogTitle>
          <DialogDescription>
            Se guardará el estado actual de filtros (sector, precio, habitaciones, etc.). Recibirás
            coincidencias cuando lleguen propiedades nuevas que cumplan.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 py-2">
          <Label htmlFor="alert-title">Título de la alerta</Label>
          <Input
            id="alert-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !mutation.isPending) handleSubmit();
            }}
            placeholder="Ej: Piantini 2+ hab hasta $300k"
            disabled={mutation.isPending}
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            Captura exacta de los filtros aplicados en la URL en este momento.
          </p>
        </div>

        {submitError ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            {submitError}
          </p>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={closeDialog} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="button" onClick={handleSubmit} disabled={mutation.isPending || !title.trim()}>
            {mutation.isPending ? "Guardando..." : "Guardar alerta"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  return {
    /** Call to open the title prompt dialog using current appliedFilters */
    openDialog,
    isPending: mutation.isPending,
    /** Render this once in your tree (near the button) */
    dialog,
  };
}
