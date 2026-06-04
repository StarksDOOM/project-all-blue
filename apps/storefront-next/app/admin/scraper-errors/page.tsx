import Link from "next/link";
import { ScraperErrorMatrix } from "@/components/admin/ScraperErrorMatrix";

export default function ScraperErrorsAdminPage() {
  return (
    <main className="min-h-screen bg-muted/40 p-6 md:p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <div>
          <Link
            href="/"
            className="text-sm font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            ← Volver al inventario
          </Link>
        </div>
        <ScraperErrorMatrix />
      </div>
    </main>
  );
}