"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ContractMarkdownPreviewProps {
  title: string;
  remoteId: string;
  buyerName: string;
  sellerName: string;
  status: string;
  documentBody: string;
}

/** Pure RSC — markdown body render (no client hooks). */
export function ContractMarkdownPreview({
  title,
  remoteId,
  buyerName,
  sellerName,
  status,
  documentBody,
}: ContractMarkdownPreviewProps) {
  return (
    <Card className="print:border-0 print:shadow-none">
      <CardHeader className="print:hidden">
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          #{remoteId} · {buyerName} → {sellerName} · Estado {status}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <article className="prose prose-slate dark:prose-invert max-w-none rounded-lg border bg-white p-6 text-sm leading-relaxed shadow-sm print:border-0 print:shadow-none">
          <ContractMarkdownBody body={documentBody} />
        </article>
      </CardContent>
    </Card>
  );
}

function ContractMarkdownBody({ body }: { body: string }) {
  const lines = body.split("\n");
  return (
    <div className="space-y-2 font-sans text-slate-900">
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (trimmed.startsWith("# ")) {
          return (
            <h1 key={index} className="text-2xl font-bold tracking-tight">
              {trimmed.replace(/^#\s+/, "")}
            </h1>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h2 key={index} className="mt-6 text-lg font-semibold">
              {trimmed.replace(/^##\s+/, "")}
            </h2>
          );
        }
        if (trimmed.startsWith("---")) {
          return <hr key={index} className="my-4 border-slate-200" />;
        }
        if (trimmed.startsWith("|")) {
          return (
            <p key={index} className="font-mono text-xs text-slate-700">
              {line}
            </p>
          );
        }
        if (!trimmed) {
          return <div key={index} className="h-2" />;
        }
        const boldRendered = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        return (
          <p
            key={index}
            className="text-sm text-slate-800"
            dangerouslySetInnerHTML={{ __html: boldRendered }}
          />
        );
      })}
    </div>
  );
}