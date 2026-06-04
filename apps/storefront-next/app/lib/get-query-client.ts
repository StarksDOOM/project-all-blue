import { QueryClient } from "@tanstack/react-query";
import { cache } from "react";

/** Per-request QueryClient for RSC prefetch + dehydrate (Next.js 15 App Router). */
export const getQueryClient = cache(
  () =>
    new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60_000,
          retry: 1,
          refetchOnWindowFocus: false,
        },
      },
    })
);