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

  const lastSubmittedFingerprintRef = useRef<string>(fingerprint);

  useEffect(() => {
    // If the URL updated to match our last submitted filters, skip updating draft
    if (fingerprint === lastSubmittedFingerprintRef.current) return;

    setDraft({
      keyword: appliedFilters.keyword,
      price_min: appliedFilters.price_min,
      price_max: appliedFilters.price_max,
      agency: appliedFilters.agency,
    });

    lastSubmittedFingerprintRef.current = fingerprint;
  }, [fingerprint, appliedFilters]);

  const debouncedDraft = useDebouncedValue(draft, 300);

  const replaceFilters = useCallback(
    (next: PropertyFilterParams) => {
      const query = filtersToSearchParams({
        ...DEFAULT_PROPERTY_FILTERS,
        ...next,
        page: next.page ?? 1,
      });
      const qs = query.toString();

      // Track the fingerprint of what we just pushed to the URL to prevent sync overwrites
      lastSubmittedFingerprintRef.current = filtersFingerprint({
        ...DEFAULT_PROPERTY_FILTERS,
        ...next,
      });

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