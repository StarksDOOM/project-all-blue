"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

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

let cachedNativeReplaceState: typeof window.history.replaceState | null = null;

function getNativeReplaceState(): typeof window.history.replaceState {
  if (typeof window === "undefined") return () => {};
  if (cachedNativeReplaceState) return cachedNativeReplaceState;

  try {
    const iframe = document.createElement("iframe");
    iframe.style.display = "none";
    document.body.appendChild(iframe);
    const nativeReplace = iframe.contentWindow?.history.replaceState;
    document.body.removeChild(iframe);
    if (nativeReplace) {
      cachedNativeReplaceState = nativeReplace.bind(window.history);
      return cachedNativeReplaceState;
    }
  } catch (e) {
    console.error("Failed to get native replaceState, falling back to monkey-patched", e);
  }
  return window.history.replaceState.bind(window.history);
}

export function useFilterParams() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Initialize filters from search parameters ONLY once on mount
  const initialFilters = useMemo(() => {
    return parseFiltersFromSearchParams(searchParams);
  }, []); // Empty dependency: only compute once on initial mount

  const [appliedFilters, setAppliedFilters] = useState<PropertyFilterParams>(initialFilters);

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

  // Updates the browser URL bar silently using the native, unpatched replaceState
  const replaceFiltersInUrl = useCallback(
    (next: PropertyFilterParams) => {
      const query = filtersToSearchParams({
        ...DEFAULT_PROPERTY_FILTERS,
        ...next,
        page: next.page ?? 1,
      });
      const qs = query.toString();
      const newUrl = qs ? `${pathname}?${qs}` : pathname;

      const nativeReplace = getNativeReplaceState();
      nativeReplace(null, "", newUrl);
    },
    [pathname]
  );

  // Sync debounced changes to local applied filters and URL
  useEffect(() => {
    const pendingChange = DEBOUNCED_FIELDS.some(
      (field) => debouncedDraft[field] !== appliedFilters[field]
    );
    if (!pendingChange) return;

    const nextFilters = {
      ...appliedFilters,
      ...debouncedDraft,
      page: 1,
    };
    setAppliedFilters(nextFilters);
    replaceFiltersInUrl(nextFilters);
  }, [debouncedDraft, appliedFilters, replaceFiltersInUrl]);

  const setInstantFilter = useCallback(
    (patch: Partial<PropertyFilterParams>) => {
      const nextFilters = { ...appliedFilters, ...patch, page: 1 };
      setAppliedFilters(nextFilters);
      replaceFiltersInUrl(nextFilters);
    },
    [appliedFilters, replaceFiltersInUrl]
  );

  const setDraftField = useCallback(
    <K extends keyof DraftFilterFields>(key: K, value: DraftFilterFields[K]) => {
      setDraft((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const setPage = useCallback(
    (page: number) => {
      const nextFilters = { ...appliedFilters, page };
      setAppliedFilters(nextFilters);
      replaceFiltersInUrl(nextFilters);
    },
    [appliedFilters, replaceFiltersInUrl]
  );

  const resetFilters = useCallback(() => {
    setDraft({});
    const nextFilters = { ...DEFAULT_PROPERTY_FILTERS };
    setAppliedFilters(nextFilters);
    replaceFiltersInUrl(nextFilters);
  }, [replaceFiltersInUrl]);

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