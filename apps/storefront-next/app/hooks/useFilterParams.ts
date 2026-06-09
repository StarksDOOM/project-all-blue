"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  DEFAULT_PROPERTY_FILTERS,
  filtersFingerprint,
  filtersToSearchParams,
  parseFiltersFromSearchParams,
  type PropertyFilterParams,
} from "@/lib/property-filters";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";

type DraftFilterFields = Pick<
  PropertyFilterParams,
  "keyword" | "price_min" | "price_max" | "agency"
>;

const DEBOUNCED_FIELDS: (keyof DraftFilterFields)[] = [
  "keyword",
  "price_min",
  "price_max",
  "agency",
];

export function useFilterParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const appliedFilters = useMemo(
    () => parseFiltersFromSearchParams(searchParams),
    [searchParams]
  );

  const fingerprint = useMemo(
    () => filtersFingerprint(appliedFilters),
    [appliedFilters]
  );

  const [draft, setDraft] = useState<DraftFilterFields>({
    keyword: appliedFilters.keyword,
    price_min: appliedFilters.price_min,
    price_max: appliedFilters.price_max,
    agency: appliedFilters.agency,
  });

  const prevAppliedFiltersRef = useRef<PropertyFilterParams>(appliedFilters);

  useEffect(() => {
    const prev = prevAppliedFiltersRef.current;

    setDraft((currentDraft) => {
      const nextDraft = { ...currentDraft };
      let updated = false;

      DEBOUNCED_FIELDS.forEach((field) => {
        const urlVal = appliedFilters[field];
        const prevUrlVal = prev[field];

        if (urlVal !== prevUrlVal) {
          // Only sync if the current draft value matches the old URL value
          // (meaning the user wasn't editing this field and the change is external)
          if (currentDraft[field] === prevUrlVal) {
            nextDraft[field] = urlVal as any;
            updated = true;
          }
        }
      });

      return updated ? nextDraft : currentDraft;
    });

    prevAppliedFiltersRef.current = appliedFilters;
  }, [appliedFilters]);

  const debouncedDraft = useDebouncedValue(draft, 300);

  const replaceFilters = useCallback(
    (next: PropertyFilterParams) => {
      const query = filtersToSearchParams({
        ...DEFAULT_PROPERTY_FILTERS,
        ...next,
        page: next.page ?? 1,
      });
      const qs = query.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router]
  );

  useEffect(() => {
    const pendingChange = DEBOUNCED_FIELDS.some(
      (field) => debouncedDraft[field] !== appliedFilters[field]
    );
    if (!pendingChange) return;

    replaceFilters({
      ...appliedFilters,
      ...debouncedDraft,
      page: 1,
    });
  }, [debouncedDraft, appliedFilters, replaceFilters]);

  const setInstantFilter = useCallback(
    (patch: Partial<PropertyFilterParams>) => {
      replaceFilters({ ...appliedFilters, ...patch, page: 1 });
    },
    [appliedFilters, replaceFilters]
  );

  const setDraftField = useCallback(
    <K extends keyof DraftFilterFields>(key: K, value: DraftFilterFields[K]) => {
      setDraft((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const setPage = useCallback(
    (page: number) => {
      replaceFilters({ ...appliedFilters, page });
    },
    [appliedFilters, replaceFilters]
  );

  const resetFilters = useCallback(() => {
    setDraft({});
    replaceFilters({ ...DEFAULT_PROPERTY_FILTERS });
  }, [replaceFilters]);

  const isDebouncing = DEBOUNCED_FIELDS.some(
    (field) => draft[field] !== debouncedDraft[field]
  );

  return {
    appliedFilters,
    fingerprint,
    draft,
    setDraftField,
    setInstantFilter,
    setPage,
    resetFilters,
    isDebouncing,
  };
}