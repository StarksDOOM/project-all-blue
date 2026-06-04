"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  transactionFormSchema,
  type TransactionFormValues,
} from "@/lib/transaction-schema";
import { Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { PropertyListing } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface TransactionContractModalProps {
  property: PropertyListing;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function defaultAgreedPrice(property: PropertyListing): number {
  if (property.list_price != null && property.list_price > 0) {
    return property.list_price;
  }
  if (property.price_raw > 0) {
    return property.price_raw;
  }
  return property.price_usd > 0 ? property.price_usd : 0;
}

export function TransactionContractModal({
  property,
  open,
  onOpenChange,
}: TransactionContractModalProps) {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<TransactionFormValues>({
    resolver: zodResolver(transactionFormSchema),
    defaultValues: {
      buyer_name: "",
      buyer_id_doc: "",
      seller_name: property.agent_name ?? "",
      seller_id_doc: "",
      agreed_price: String(defaultAgreedPrice(property)),
      currency: (property.currency === "DOP" ? "DOP" : "USD") as "USD" | "DOP",
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      const transaction = await api.createTransaction({
        property_id: property.blu_id || property.remote_id,
        buyer_name: values.buyer_name,
        buyer_id_doc: values.buyer_id_doc,
        seller_name: values.seller_name,
        seller_id_doc: values.seller_id_doc,
        agreed_price: Number(values.agreed_price),
        currency: values.currency,
      });
      await api.generateTransactionContract(transaction.id);
      onOpenChange(false);
      router.push(`/dashboard/transactions/${transaction.id}`);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo generar el contrato.";
      setSubmitError(message);
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent onClose={() => onOpenChange(false)}>
        <DialogHeader>
          <DialogTitle>Generar Contrato</DialogTitle>
          <DialogDescription>
            Promesa de Venta — {property.title} (#{property.remote_id})
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="buyer_name">Comprador</Label>
              <Input id="buyer_name" {...register("buyer_name")} />
              {errors.buyer_name ? (
                <p className="text-xs text-destructive">{errors.buyer_name.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="buyer_id_doc">Cédula / RNC comprador</Label>
              <Input id="buyer_id_doc" {...register("buyer_id_doc")} />
              {errors.buyer_id_doc ? (
                <p className="text-xs text-destructive">{errors.buyer_id_doc.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="seller_name">Vendedor</Label>
              <Input id="seller_name" {...register("seller_name")} />
              {errors.seller_name ? (
                <p className="text-xs text-destructive">{errors.seller_name.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="seller_id_doc">Cédula / RNC vendedor</Label>
              <Input id="seller_id_doc" {...register("seller_id_doc")} />
              {errors.seller_id_doc ? (
                <p className="text-xs text-destructive">{errors.seller_id_doc.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="agreed_price">Precio pactado</Label>
              <Input
                id="agreed_price"
                type="number"
                step="0.01"
                min="0"
                {...register("agreed_price")}
              />
              {errors.agreed_price ? (
                <p className="text-xs text-destructive">{errors.agreed_price.message}</p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="currency">Moneda</Label>
              <select
                id="currency"
                className="flex h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                {...register("currency")}
              >
                <option value="USD">USD</option>
                <option value="DOP">DOP</option>
              </select>
            </div>
          </div>

          {submitError ? (
            <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {submitError}
            </p>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generando…
                </>
              ) : (
                "Generar borrador"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}