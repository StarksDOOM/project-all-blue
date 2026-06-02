"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ContractRecord, InitializeContractPayload, PropertyListing } from "@/lib/types";

interface ContractDrawerProps {
  property: PropertyListing;
  onClose: () => void;
}

const EMPTY_COUNTERPARTY: InitializeContractPayload = {
  buyer_name: "",
  buyer_id: "",
  seller_name: "",
  seller_id: "",
};

function isCounterpartyValid(payload: InitializeContractPayload): boolean {
  return (
    payload.buyer_name.trim().length > 0 &&
    payload.buyer_id.trim().length > 0 &&
    payload.seller_name.trim().length > 0 &&
    payload.seller_id.trim().length > 0
  );
}

export default function ContractDrawer({ property, onClose }: ContractDrawerProps) {
  const [counterparty, setCounterparty] = useState<InitializeContractPayload>(EMPTY_COUNTERPARTY);
  const [compiledContract, setCompiledContract] = useState<ContractRecord | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const initializeMutation = useMutation({
    mutationFn: (payload: InitializeContractPayload) =>
      api.initializeContract(property.remote_id, payload),
    onSuccess: (contract) => {
      setCompiledContract(contract);
    },
  });

  useEffect(() => {
    setCounterparty(EMPTY_COUNTERPARTY);
    setCompiledContract(null);
    setCopyFeedback(null);
    initializeMutation.reset();
  }, [property.remote_id]);

  const handleClose = () => {
    setCounterparty(EMPTY_COUNTERPARTY);
    setCompiledContract(null);
    setCopyFeedback(null);
    initializeMutation.reset();
    onClose();
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isCounterpartyValid(counterparty)) {
      return;
    }
    initializeMutation.mutate({
      buyer_name: counterparty.buyer_name.trim(),
      buyer_id: counterparty.buyer_id.trim(),
      seller_name: counterparty.seller_name.trim(),
      seller_id: counterparty.seller_id.trim(),
    });
  };

  const handleCopy = async () => {
    if (!compiledContract?.document_body) {
      return;
    }
    try {
      await navigator.clipboard.writeText(compiledContract.document_body);
      setCopyFeedback("Copied to clipboard.");
    } catch {
      setCopyFeedback("Unable to copy. Check browser permissions.");
    }
  };

  const isPreviewMode = compiledContract != null;
  const isSubmitting = initializeMutation.isPending;
  const canSubmit = isCounterpartyValid(counterparty) && !isSubmitting;

  const buyerLabel =
    property.business_type === "alquiler" ? "Arrendatario (Tenant)" : "Comprador (Buyer)";
  const sellerLabel =
    property.business_type === "alquiler" ? "Arrendador (Landlord)" : "Vendedor (Seller)";

  return (
    <aside className="flex h-full max-h-[calc(100vh-4rem)] w-full max-w-md flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">
            {isPreviewMode ? "Contract Preview" : "Initialize Contract"}
          </h2>
          <p className="text-xs text-slate-500 capitalize">
            {property.business_type} · #{property.remote_id}
          </p>
        </div>
        {!isPreviewMode ? (
          <button
            type="button"
            onClick={handleClose}
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
          >
            Close
          </button>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col overflow-hidden p-6">
        <div className="mb-4 rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Property</p>
          <p className="font-medium text-slate-900">{property.title}</p>
          <p className="text-sm text-slate-600">{property.sector}</p>
        </div>

        {!isPreviewMode ? (
          <form onSubmit={handleSubmit} className="flex flex-1 flex-col gap-4 overflow-y-auto">
            <div className="space-y-2">
              <label htmlFor="buyer-name" className="text-xs font-semibold uppercase text-slate-500">
                {buyerLabel} — Name
              </label>
              <input
                id="buyer-name"
                type="text"
                value={counterparty.buyer_name}
                disabled={isSubmitting}
                placeholder="Juan Pérez"
                onChange={(event) =>
                  setCounterparty((prev) => ({ ...prev, buyer_name: event.target.value }))
                }
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="buyer-id" className="text-xs font-semibold uppercase text-slate-500">
                {buyerLabel} — Cédula / Passport
              </label>
              <input
                id="buyer-id"
                type="text"
                value={counterparty.buyer_id}
                disabled={isSubmitting}
                placeholder="001-1234567-8"
                onChange={(event) =>
                  setCounterparty((prev) => ({ ...prev, buyer_id: event.target.value }))
                }
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>

            <div className="space-y-2">
              <label
                htmlFor="seller-name"
                className="text-xs font-semibold uppercase text-slate-500"
              >
                {sellerLabel} — Name
              </label>
              <input
                id="seller-name"
                type="text"
                value={counterparty.seller_name}
                disabled={isSubmitting}
                placeholder="María Rodríguez"
                onChange={(event) =>
                  setCounterparty((prev) => ({ ...prev, seller_name: event.target.value }))
                }
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="seller-id" className="text-xs font-semibold uppercase text-slate-500">
                {sellerLabel} — Cédula / Passport
              </label>
              <input
                id="seller-id"
                type="text"
                value={counterparty.seller_id}
                disabled={isSubmitting}
                placeholder="130-0000000-1"
                onChange={(event) =>
                  setCounterparty((prev) => ({ ...prev, seller_id: event.target.value }))
                }
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>

            {initializeMutation.isError ? (
              <p className="text-sm text-red-600">
                {(initializeMutation.error as Error).message}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={!canSubmit}
              className="mt-auto w-full rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Compiling Document..." : "Generate Legal Draft"}
            </button>
          </form>
        ) : (
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-700">
                {compiledContract.contract_type}
              </span>
              <span className="rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-800">
                {compiledContract.status}
              </span>
              <span className="text-slate-500">{compiledContract.contract_number}</span>
            </div>

            <div className="flex-1 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900 p-4">
              <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-neutral-100">
                {compiledContract.document_body}
              </pre>
            </div>

            {copyFeedback ? (
              <p className="mt-2 text-xs text-emerald-600">{copyFeedback}</p>
            ) : null}

            <div className="mt-4 flex gap-3">
              <button
                type="button"
                onClick={handleCopy}
                className="flex-1 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50"
              >
                Copy to Clipboard
              </button>
              <button
                type="button"
                onClick={handleClose}
                className="flex-1 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}