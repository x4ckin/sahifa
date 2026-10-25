/** Regression tests for the Task 10 review: a gift must never be paid twice or lost. */
import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalMuseum } from "../src/account/store";
import Gift from "../src/views/Gift.vue";
import Home from "../src/views/Home.vue";
import Order from "../src/views/Order.vue";
import { mountView } from "./helpers";

const s = vi.hoisted(() => ({
  museum: null as LocalMuseum | null,
  saveFails: false,
  calls: [] as string[],
  server: {} as Record<number, any>,
  orders: {} as Record<string, any>,
  invoice: "paid",
  getOrderFailures: 0,
}));

vi.mock("../src/account/store", async (orig) => ({
  ...(await orig<typeof import("../src/account/store")>()),
  loadMuseum: vi.fn(async () => (s.museum ? structuredClone(s.museum) : null)),
  listMuseums: vi.fn(async () => (s.museum ? [structuredClone(s.museum)] : [])),
  saveMuseum: vi.fn(async (m: LocalMuseum) => {
    if (s.saveFails) throw new Error("storage_full");
    s.calls.push(`save:${m.gift?.state ?? "-"}`);
    s.museum = structuredClone(m);
  }),
  collectGarbage: vi.fn(async () => 0),
}));
vi.mock("../src/telegram", async (orig) => {
  const real = await orig<typeof import("../src/telegram")>();
  return { ...real, tg: { ...real.tg, openInvoice: vi.fn(async () => s.invoice) } };
});
vi.mock("../src/api", async (orig) => {
  const real = await orig<typeof import("../src/api")>();
  const notFound = () => new real.ApiError("not_found", 404);
  return {
    ...real,
    api: {
      getPrices: vi.fn(async () => ({ museum: { uzs: 15000, stars: 75 }, room: { uzs: 3000, stars: 15 }, slots: { uzs: 5000, stars: 25 } })),
      getMe: vi.fn(async () => ({ bot_username: "SahifaBot", slots: { used: 0, total: 10 } })),
      listMuseums: vi.fn(async () => Object.values(s.server)),
      getMuseum: vi.fn(async (id: number) => {
        s.calls.push(`get:${id}`);
        if (!s.server[id]) throw notFound();
        return s.server[id];
      }),
      deleteMuseum: vi.fn(async (id: number, opts?: { onlyDraft?: boolean }) => {
        s.calls.push(`delete:${id}:${opts?.onlyDraft ? "draft" : "any"}`);
        delete s.server[id];
        return { ok: true };
      }),
      importMuseum: vi.fn(async () => {
        s.calls.push("import");
        s.server[50] = { id: 50, slug: "new", status: "draft" };
        return s.server[50];
      }),
      createOrder: vi.fn(async (product: string, id: number, method: string) => {
        s.calls.push(`order:${id}:${method}`);
        const o = { code: `O${id}${method[0]}`, status: "pending", method, product, museum_id: id, invoice_link: method === "stars" ? "https://t.me/$i" : undefined };
        s.orders[o.code] = o;
        return o;
      }),
      getOrder: vi.fn(async (code: string) => {
        if (s.getOrderFailures > 0) {
          s.getOrderFailures--;
          throw new real.ApiError("network", 0);
        }
        return s.orders[code];
      }),
      tgMediaUrl: (t: string) => t,
    },
  };
});

function museum(extra: Partial<LocalMuseum> = {}): LocalMuseum {
  return {
    id: "abc123", v: 1, title: "Onam", recipient: "", theme: "gallery_light", mascot: "boy", opening: "gift_box",
    template: "blank", created: 0, letter: "", media: [{ t: "i0", k: "image" }], ...extra,
  };
}

beforeEach(() => {
  s.museum = museum();
  s.saveFails = false;
  s.calls = [];
  s.server = {};
  s.orders = {};
  s.invoice = "paid";
  s.getOrderFailures = 0;
});

async function pay() {
  const view = await mountView(Gift, "/gift/abc123", "/gift/:id");
  await view.wrapper.find("[data-pay]").trigger("click");
  await flushPromises();
  return view;
}

describe("gift safety", () => {
  it("a draft that was already paid is marked paid, never deleted", async () => {
    s.museum = museum({ gift: { draft: 7, state: "draft" } });
    s.server[7] = { id: 7, slug: "paid7", status: "active" };
    const { router } = await pay();
    expect(s.calls.some((c) => c.startsWith("delete") || c === "import" || c.startsWith("order"))).toBe(false);
    expect(s.museum?.gift?.state).toBe("paid");
    expect(router.currentRoute.value.path).toBe("/done/7");
  });

  it("a receipt under review resumes that order instead of starting again", async () => {
    s.museum = museum({ gift: { draft: 7, state: "draft", order: "OC7" } });
    s.server[7] = { id: 7, slug: "d7", status: "draft" };
    s.orders.OC7 = { code: "OC7", status: "awaiting_review", method: "card", product: "museum", museum_id: 7 };
    const { router } = await pay();
    expect(s.calls.some((c) => c.startsWith("delete") || c === "import")).toBe(false);
    expect(router.currentRoute.value.fullPath).toBe("/order/OC7?local=abc123");
  });

  it("an unchanged museum reuses its draft (a card transfer may already be on its way)", async () => {
    await pay(); // first attempt: import + stars order
    s.calls = [];
    s.invoice = "cancelled";
    await pay(); // same content again
    expect(s.calls).not.toContain("import");
    expect(s.calls.some((c) => c.startsWith("delete"))).toBe(false);
    expect(s.calls).toContain("order:50:stars");
  });

  it("a changed museum replaces only an unpaid draft, asking the server to refuse anything else", async () => {
    s.invoice = "cancelled";
    await pay();
    s.museum!.title = "Boshqa nom";
    s.calls = [];
    await pay();
    expect(s.calls.filter((c) => c.startsWith("delete") || c === "import")).toEqual(["delete:50:draft", "import"]);
  });

  it("a pending card order is resumed even if the museum changed", async () => {
    s.museum = museum({ gift: { draft: 7, state: "draft", order: "OC7", hash: "old" } });
    s.server[7] = { id: 7, slug: "d7", status: "draft" };
    s.orders.OC7 = { code: "OC7", status: "pending", method: "card", product: "museum", museum_id: 7 };
    const { router } = await pay();
    expect(s.calls.some((c) => c.startsWith("delete"))).toBe(false);
    expect(router.currentRoute.value.fullPath).toBe("/order/OC7?local=abc123");
  });

  it("a failed save stops before any order is created", async () => {
    s.saveFails = true;
    const { wrapper } = await pay();
    expect(s.calls.some((c) => c.startsWith("order"))).toBe(false);
    expect(wrapper.find(".error").exists()).toBe(true);
  });

  it("a failed Stars invoice shows an error", async () => {
    s.invoice = "failed";
    const { wrapper } = await pay();
    expect(wrapper.find(".error").exists()).toBe(true);
  });
});

describe("order screen safety", () => {
  it("reviewing keeps polling and hides the card details", async () => {
    s.orders.OC7 = { code: "OC7", status: "reviewing", method: "card", product: "museum", museum_id: 7, amount_uzs: 15000, cards: [{ number: "8600", holder: "A" }] };
    const { wrapper } = await mountView(Order, "/order/OC7", "/order/:code");
    expect(wrapper.text()).toContain("tekshirilmoqda");
    expect(wrapper.text()).not.toContain("8600");
  });

  it("a network error while polling is retried", async () => {
    vi.useFakeTimers();
    s.getOrderFailures = 1;
    s.orders.OC7 = { code: "OC7", status: "awaiting_review", method: "card", product: "museum", museum_id: 7, amount_uzs: 15000 };
    const { wrapper } = await mountView(Order, "/order/OC7", "/order/:code");
    await vi.advanceTimersByTimeAsync(4000);
    await flushPromises();
    expect(wrapper.text()).toContain("tekshirilmoqda");
    vi.useRealTimers();
  });
});

describe("home self-heal", () => {
  it("a local draft whose server museum is paid shows as gifted and is fixed", async () => {
    s.museum = museum({ gift: { draft: 7, state: "draft" } });
    s.server[7] = { id: 7, slug: "p7", title: "Onam", status: "active", expires_at: new Date(Date.now() + 5 * 86400000).toISOString(), counts: { image: 1, video: 0 } };
    const { wrapper } = await mountView(Home);
    await flushPromises();
    expect(wrapper.text()).toContain("Sovg'a qilingan");
    expect(s.museum?.gift?.state).toBe("paid");
  });
});
