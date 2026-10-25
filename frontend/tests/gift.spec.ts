import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalMuseum } from "../src/account/store";
import { ApiError } from "../src/api";
import Done from "../src/views/Done.vue";
import Gift from "../src/views/Gift.vue";
import Order from "../src/views/Order.vue";
import { mountView } from "./helpers";

const s = vi.hoisted(() => ({
  museum: null as LocalMuseum | null,
  saved: [] as LocalMuseum[],
  calls: [] as string[],
  order: null as any,
  invoice: "paid" as string,
}));

vi.mock("../src/account/store", async (orig) => ({
  ...(await orig<typeof import("../src/account/store")>()),
  loadMuseum: vi.fn(async () => (s.museum ? structuredClone(s.museum) : null)),
  saveMuseum: vi.fn(async (m: LocalMuseum) => {
    s.saved.push(structuredClone(m));
    s.museum = structuredClone(m);
  }),
}));
vi.mock("../src/telegram", async (orig) => {
  const real = await orig<typeof import("../src/telegram")>();
  return { ...real, tg: { ...real.tg, openInvoice: vi.fn(async () => s.invoice) } };
});
vi.mock("../src/api", async (orig) => {
  const real = await orig<typeof import("../src/api")>();
  return {
    ...real,
    api: {
      getPrices: vi.fn(async () => ({
        museum: { uzs: 15000, stars: 75 }, room: { uzs: 3000, stars: 15 },
        reactivate: { uzs: 15000, stars: 75 }, slots: { uzs: 5000, stars: 25 },
      })),
      getMe: vi.fn(async () => ({ bot_username: "SahifaBot", slots: { used: 0, total: 10 } })),
      deleteMuseum: vi.fn(async (id: number) => {
        s.calls.push(`delete:${id}`);
        throw new real.ApiError("not_found", 404);
      }),
      importMuseum: vi.fn(async () => {
        s.calls.push("import");
        return { id: 42, slug: "Xk29fQ_aZ8m" };
      }),
      createOrder: vi.fn(async (product: string, id: number, method: string) => {
        s.calls.push(`order:${product}:${id}:${method}`);
        return s.order;
      }),
      getOrder: vi.fn(async () => s.order),
      uploadReceipt: vi.fn(async () => ({ ...s.order, status: "awaiting_review" })),
      getMuseum: vi.fn(async () => ({ id: 42, slug: "Xk29fQ_aZ8m", title: "Onam", status: "active" })),
      tgMediaUrl: (t: string) => t,
    },
  };
});

const images = (n: number) => Array.from({ length: n }, (_, i) => ({ t: `i${i}`, k: "image" as const }));
function museum(extra: Partial<LocalMuseum> = {}): LocalMuseum {
  return {
    id: "abc123", v: 1, title: "Onam", recipient: "Aziza", theme: "gallery_light", mascot: "boy",
    opening: "gift_box", template: "mom", created: 0, letter: "Rahmat", media: images(3), ...extra,
  };
}

beforeEach(() => {
  s.museum = museum();
  s.saved = [];
  s.calls = [];
  s.invoice = "paid";
  s.order = { code: "ORD222", status: "pending", method: "stars", product: "museum", museum_id: 42,
    amount_uzs: 15000, amount_stars: 75, invoice_link: "https://t.me/$inv", reject_reason: null };
});

describe("gift", () => {
  it("summary adds rooms automatically", async () => {
    s.museum = museum({ media: images(45) });
    const { wrapper } = await mountView(Gift, "/gift/abc123", "/gift/:id");
    expect(wrapper.text()).toContain("Qo'shimcha xona × 2");
    expect(wrapper.find("[data-total]").text()).toContain("21 000");
    expect(wrapper.text()).toContain("105 ⭐");
  });

  it("regifting a changed museum replaces the unpaid draft first", async () => {
    s.museum = museum({ gift: { draft: 7, state: "draft", hash: "old" } });
    const { api } = await import("../src/api");
    vi.mocked(api.getMuseum).mockResolvedValueOnce({ id: 7, slug: "d7", status: "draft" } as any);
    const { wrapper } = await mountView(Gift, "/gift/abc123", "/gift/:id");
    await wrapper.find("[data-pay]").trigger("click");
    await flushPromises();
    expect(s.calls.slice(0, 3)).toEqual(["delete:7", "import", "order:museum:42:stars"]);
  });

  it("stars payment marks the museum paid", async () => {
    const { wrapper, router } = await mountView(Gift, "/gift/abc123", "/gift/:id");
    await wrapper.find("[data-pay]").trigger("click");
    s.order = { ...s.order, status: "paid" };
    await flushPromises();
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/done/42"));
    expect(s.museum?.gift).toMatchObject({ draft: 42, state: "paid" });
  });

  it("card payment goes to the order screen", async () => {
    s.order = { ...s.order, method: "card", invoice_link: undefined, cards: [{ number: "8600 0000 0000 0001", holder: "Ali" }] };
    const { wrapper, router } = await mountView(Gift, "/gift/abc123", "/gift/:id");
    await wrapper.find("[data-method='card']").trigger("click");
    await wrapper.find("[data-pay]").trigger("click");
    await flushPromises();
    expect(s.calls).toContain("order:museum:42:card");
    expect(router.currentRoute.value.fullPath).toBe("/order/ORD222?local=abc123");
  });

  it("a failed import shows the error and opens no payment", async () => {
    const { api } = await import("../src/api");
    vi.mocked(api.importMuseum).mockRejectedValueOnce(new ApiError("media_gone", 410));
    const { wrapper } = await mountView(Gift, "/gift/abc123", "/gift/:id");
    await wrapper.find("[data-pay]").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Fayl Telegram chatingizdan o'chirilgan");
    expect(s.calls.some((c) => c.startsWith("order"))).toBe(false);
  });
});

describe("order (card)", () => {
  it("card order shows rejection reason and allows resend", async () => {
    s.order = { ...s.order, method: "card", status: "rejected", reject_reason: "amount",
      cards: [{ number: "8600 0000 0000 0001", holder: "Ali" }], comment: "ORD222" };
    const { wrapper } = await mountView(Order, "/order/ORD222", "/order/:code");
    expect(wrapper.text()).toContain("summa noto'g'ri");
    expect(wrapper.text()).toContain("8600 0000 0000 0001");
    expect(wrapper.find("input[type=file][data-receipt]").exists()).toBe(true);
  });

  it("paid order marks the local museum paid and opens the done screen", async () => {
    s.museum = museum({ gift: { draft: 42, state: "draft" } });
    s.order = { ...s.order, method: "card", status: "paid" };
    const { router } = await mountView(Order, "/order/ORD222?local=abc123", "/order/:code");
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/done/42"));
    expect(s.museum?.gift?.state).toBe("paid");
  });
});

describe("done", () => {
  it("done screen builds the t.me link from bot_username", async () => {
    const { wrapper } = await mountView(Done, "/done/42", "/done/:id");
    await vi.waitFor(() => expect(wrapper.find("[data-link]").text()).toBe("https://t.me/SahifaBot?start=m_Xk29fQ_aZ8m"));
  });
});
