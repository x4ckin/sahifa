import { api, type OrderOut } from "./api";

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
