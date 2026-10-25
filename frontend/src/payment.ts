import { api, type OrderOut } from "./api";
import { tg } from "./telegram";

const FINAL = new Set(["paid", "rejected", "cancelled", "refunded"]);

/** Poll an order until it is final or we give up (backoff 0.5 s → 3 s, about 2 minutes in total). */
export async function waitForOrder(code: string, sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))): Promise<OrderOut> {
  let order = await api.getOrder(code);
  for (let attempt = 0; attempt < 45 && !FINAL.has(order.status); attempt++) {
    await sleep(Math.min(500 * 2 ** attempt, 3000));
    order = await api.getOrder(code);
  }
  return order;
}

export type PayOutcome = { kind: "paid" } | { kind: "card"; code: string } | { kind: "not_paid" };

/** Buy a product for an existing server museum (room, reactivation, museum slots). */
export async function payForProduct(
  product: "room" | "reactivate" | "slots",
  museumId: number | null,
  method: "stars" | "card",
): Promise<PayOutcome> {
  const order = await api.createOrder(product, museumId, method);
  if (order.status === "paid") return { kind: "paid" };
  if (method === "card" || !order.invoice_link) return { kind: "card", code: order.code };
  const status = await tg.openInvoice(order.invoice_link);
  if (status === "cancelled" || status === "failed") return { kind: "not_paid" };
  return (await waitForOrder(order.code)).status === "paid" ? { kind: "paid" } : { kind: "not_paid" };
}
