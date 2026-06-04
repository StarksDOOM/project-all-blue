import { describe, expect, it } from "vitest";

import { transactionFormSchema } from "./transaction-schema";

describe("transactionFormSchema", () => {
  it("accepts a valid Promesa de Venta payload", () => {
    const result = transactionFormSchema.safeParse({
      buyer_name: "Juan Pérez",
      buyer_id_doc: "402-XXXXXXX-X",
      seller_name: "María Rodriguez",
      seller_id_doc: "001-XXXXXXX-X",
      agreed_price: "150000",
      currency: "USD",
    });
    expect(result.success).toBe(true);
  });

  it("rejects short buyer name and non-positive price", () => {
    const result = transactionFormSchema.safeParse({
      buyer_name: "J",
      buyer_id_doc: "402",
      seller_name: "María Rodriguez",
      seller_id_doc: "001-XXXXXXX-X",
      agreed_price: "0",
      currency: "USD",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const messages = result.error.issues.map((issue) => issue.message);
      expect(messages.some((msg) => msg.includes("comprador"))).toBe(true);
      expect(messages.some((msg) => msg.includes("precio"))).toBe(true);
    }
  });

  it("rejects invalid currency codes", () => {
    const result = transactionFormSchema.safeParse({
      buyer_name: "Juan Pérez",
      buyer_id_doc: "402-XXXXXXX-X",
      seller_name: "María Rodriguez",
      seller_id_doc: "001-XXXXXXX-X",
      agreed_price: "150000",
      currency: "EUR",
    });
    expect(result.success).toBe(false);
  });
});