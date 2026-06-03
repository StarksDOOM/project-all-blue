const REMAX_ORIGIN = "https://www.remaxrd.com";

function extractRemoteId(urlOrSlug: string, remoteId: string): string {
  const id = remoteId.trim();
  if (/^\d{5,}$/.test(id)) {
    return id;
  }
  const match = urlOrSlug.match(/(\d{5,})\s*$/);
  return match?.[1] ?? id;
}

/** RE/MAX RD public detail URL — slug URLs redirect to /propiedades; use redirected/{id}. */
export function ensureRemaxPortalUrl(
  url: string | null | undefined,
  remoteId: string
): string {
  const rid = extractRemoteId(url || "", remoteId);
  if (!rid) {
    return `${REMAX_ORIGIN}/propiedades`;
  }

  try {
    if (url && /^https?:\/\//i.test(url)) {
      const parsed = new URL(url);
      const host = parsed.hostname.replace(/^www\./i, "").toLowerCase();
      if (host === "remaxrd.com" && parsed.pathname.includes("/propiedad/redirected/")) {
        return parsed.href;
      }
    }
  } catch {
    // fall through to redirected template
  }

  return `${REMAX_ORIGIN}/propiedad/redirected/${rid}`;
}

export function openRemaxPortalTab(absoluteUrl: string): void {
  window.open(absoluteUrl, "_blank", "noopener,noreferrer");
}