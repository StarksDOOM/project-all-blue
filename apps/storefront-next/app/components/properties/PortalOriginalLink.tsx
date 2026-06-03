"use client";

import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ensureRemaxPortalUrl, openRemaxPortalTab } from "@/lib/portal-url";

interface PortalOriginalLinkProps {
  storedUrl: string | null | undefined;
  remoteId: string;
}

export function PortalOriginalLink({ storedUrl, remoteId }: PortalOriginalLinkProps) {
  const portalUrl = ensureRemaxPortalUrl(storedUrl, remoteId);

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        openRemaxPortalTab(portalUrl);
      }}
    >
      <ExternalLink className="h-4 w-4" />
      Ver en portal original
    </Button>
  );
}