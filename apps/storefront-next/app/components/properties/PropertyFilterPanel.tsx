"use client";

import { PropertyFilterParams } from "@/lib/property-filters";
import { BusinessTypeFilter } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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

interface PropertyFilterPanelProps {
  filters: PropertyFilterParams;
  draft: Pick<PropertyFilterParams, "keyword" | "price_min" | "price_max" | "agency">;
  onDraftChange: (
    key: "keyword" | "price_min" | "price_max" | "agency",
    value: string | number | undefined
  ) => void;
  onInstantChange: (patch: Partial<PropertyFilterParams>) => void;
  onReset: () => void;
  isDebouncing?: boolean;
}

export function PropertyFilterPanel({
  filters,
  draft,
  onDraftChange,
  onInstantChange,
  onReset,
  isDebouncing,
}: PropertyFilterPanelProps) {
  return (
    <Card>
      <CardContent className="grid gap-4 pt-6 md:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-2 lg:col-span-2">
          <Label htmlFor="filter-keyword">Keyword</Label>
          <Input
            id="filter-keyword"
            placeholder="Title or description"
            value={draft.keyword ?? ""}
            onChange={(event) => onDraftChange("keyword", event.target.value || undefined)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-sector">Sector</Label>
          <Select
            value={filters.sector || "all"}
            onValueChange={(value) =>
              onInstantChange({ sector: !value || value === "all" ? undefined : value })
            }
          >
            <SelectTrigger id="filter-sector">
              <SelectValue placeholder="All sectors" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sectors</SelectItem>
              {SECTOR_OPTIONS.map((sector) => (
                <SelectItem key={sector} value={sector}>
                  {sector}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-type">Type</Label>
          <Select
            value={filters.property_type || "all"}
            onValueChange={(value) =>
              onInstantChange({
                property_type: (!value || value === "all" ? "" : value) as BusinessTypeFilter,
              })
            }
          >
            <SelectTrigger id="filter-type">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="venta">Sale (Venta)</SelectItem>
              <SelectItem value="alquiler">Rent (Alquiler)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-price-min">Min price (USD)</Label>
          <Input
            id="filter-price-min"
            type="number"
            min={0}
            value={draft.price_min ?? ""}
            onChange={(event) =>
              onDraftChange(
                "price_min",
                event.target.value ? Number(event.target.value) : undefined
              )
            }
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-price-max">Max price (USD)</Label>
          <Input
            id="filter-price-max"
            type="number"
            min={0}
            value={draft.price_max ?? ""}
            onChange={(event) =>
              onDraftChange(
                "price_max",
                event.target.value ? Number(event.target.value) : undefined
              )
            }
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-beds">Min bedrooms</Label>
          <Select
            value={filters.bedrooms_min != null ? String(filters.bedrooms_min) : "any"}
            onValueChange={(value) =>
              onInstantChange({
                bedrooms_min: value === "any" ? undefined : Number(value),
              })
            }
          >
            <SelectTrigger id="filter-beds">
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              {[1, 2, 3, 4, 5].map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}+
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-baths">Min bathrooms</Label>
          <Select
            value={filters.bathrooms_min != null ? String(filters.bathrooms_min) : "any"}
            onValueChange={(value) =>
              onInstantChange({
                bathrooms_min: value === "any" ? undefined : Number(value),
              })
            }
          >
            <SelectTrigger id="filter-baths">
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              {["1", "1.5", "2", "2.5", "3"].map((n) => (
                <SelectItem key={n} value={n}>
                  {n}+
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2 lg:col-span-2">
          <Label htmlFor="filter-agency">Agency</Label>
          <Input
            id="filter-agency"
            placeholder="Agent agency name"
            value={draft.agency ?? ""}
            onChange={(event) => onDraftChange("agency", event.target.value || undefined)}
          />
        </div>

        <div className="flex items-end gap-2 lg:col-span-4">
          <Button type="button" variant="outline" onClick={onReset}>
            Clear filters
          </Button>
          {isDebouncing ? (
            <span className="text-xs text-muted-foreground">Applying filters…</span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}