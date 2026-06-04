# Spec: Transaction Detail Performance Optimization

## Status: SHIPPED
**Roadmap:** STREAM 5 PHASE 1.0  
**Branch:** `feat/stream-5-phase-1-storefront-performance` ← `develop`  
**App:** `apps/storefront-next/`  
**Feature README:** `docs/features/storefront-performance/README.md`

---

## 1. Objective

Reduce TTFB, CLS, and INP on `/dashboard/transactions/[id]` via RSC prefetch, React Query hydration, route streaming, granular Suspense, and dynamic code splitting—without breaking SSE `TRANSACTION_UPDATED` invalidation.

**Targets (lab / local, warm API)**

| Metric | Target |
|--------|--------|
| Route `loading.tsx` FCP shell | < 100ms perceived |
| Duplicate contract fetch on mount | **0** (hydrated cache) |
| Signing panel JS (initial route) | Deferred until dynamic import |
| DocuSign iframe bundle | **ssr: false**, load on signing action only |

---

## 2. Cache & query keys

| Key | Token |
|-----|--------|
| Contract | `['transaction-contract', transactionId]` |
| Signing config | `['signing-config']` |

**Invalidation (unchanged):** `useTransactionRealtime` → `invalidateQueries({ queryKey: ['transaction-contract', id] })`

**Prefetch (RSC):** `Promise.all([contract, signing-config])` before `dehydrate(queryClient)`.

**Client defaults:** `staleTime: 60_000`, avoid refetch-on-mount for hydrated queries.

---

## 3. Architecture

```text
page.tsx (RSC)
  prefetch → dehydrate
  <HydrationBoundary>
    <TransactionDetailView />  (client)
      <Header /> (server children via props)
      <Suspense> Timeline
      <Suspense> Audit
      <Suspense> SigningPanel (dynamic import)
      <ContractMarkdownPreview /> (server)
```

---

## 4. Bundle diagnostics

- `@next/bundle-analyzer` when `ANALYZE=true`
- `experimental.optimizePackageImports`: `lucide-react`, shadcn paths

---

## 5. Verification gates

| Gate | Command |
|------|---------|
| Unit | `npm test` |
| Build | `npm run build` |
| Analyze | `npm run analyze` (optional) |
| Manual | Network tab: single contract GET on hard navigation; SSE still refreshes UI on EXECUTED |

---

## 6. Drift policy

Any new transaction route data source must register in `lib/query-keys.ts` and RSC prefetch list.