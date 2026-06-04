import { z } from "zod";

export const transactionFormSchema = z.object({
  buyer_name: z.string().min(2, "Nombre del comprador requerido"),
  buyer_id_doc: z.string().min(5, "Documento del comprador requerido"),
  seller_name: z.string().min(2, "Nombre del vendedor requerido"),
  seller_id_doc: z.string().min(5, "Documento del vendedor requerido"),
  agreed_price: z
    .string()
    .min(1)
    .refine((value) => Number(value) > 0, "El precio pactado debe ser mayor que cero"),
  currency: z.enum(["USD", "DOP"]),
});

export type TransactionFormValues = z.infer<typeof transactionFormSchema>;