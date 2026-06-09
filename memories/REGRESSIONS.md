# Regression Prevention Log

This log documents critical lessons, environment conflicts, and regression-prone areas in `project-all-blue` that must be checked and adhered to by all agents before coding or running verification tasks.

---

## Environment & Build Conflicts

### 1. Next.js Cache Conflict (storefront-next)
- **Problem**: Running a production build (`npm run build` or `next build`) in `apps/storefront-next` while the storefront development server (`npm run dev` or `next dev`) is actively running causes a cache collision in the shared `.next/` directory. Next.js builds delete and recreate app manifests, which immediately corrupts the active dev server's cache, resulting in `ENOENT` errors (e.g., missing `app-build-manifest.json` or temporary `_buildManifest.js`) and causing `500 Internal Server Error` on page loads.
- **Directive**: **NEVER run `npm run build` while `npm run dev` is running.**
- **Verification Alternative**: To verify TypeScript type correctness and syntax compilation without corrupting the development cache, always run:
  ```powershell
  npx tsc --noEmit
  ```
  This performs type checking in-memory, runs faster, and carries zero risk of cache corruption. If you must run a full `npm run build` for deployment or production bundle validation, you must **kill the active dev server first**, run the build, delete the `.next` directory to clear the build outputs, and restart the dev server cleanly.

---

## State & Routing Guidelines

### 2. Next.js App Router Shallow Filtering
- **Problem**: Standard Next.js `router.push` or `router.replace` navigation on dynamic page segments causes Next.js to trigger a client-to-server RSC (React Server Component) request to re-evaluate page props. If the page defines a `loading.tsx` file, Next.js will unmount the entire page tree to display the loader fallback while the request is pending, causing input focus loss and keyboard buffer clearing during typing.
- **Directive**: Always use local client-side state (`useState`) as the single source of truth for dynamic queries/filters. Update the browser URL bar silently using the native, unpatched `history.replaceState` (extracted from a clean `iframe` realm to bypass Next.js's monkey-patched version). This prevents Next.js from intercepting the URL change and sending RSC requests or displaying `loading.tsx` fallbacks.
