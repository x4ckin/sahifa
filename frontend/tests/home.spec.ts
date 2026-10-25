import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalMuseum } from "../src/account/store";
import Home from "../src/views/Home.vue";
import { mountView } from "./helpers";

const store = vi.hoisted(() => ({ list: [] as LocalMuseum[] }));
const server = vi.hoisted(() => ({ me: null as any, museums: [] as any[], orders: [] as any[] }));

vi.mock("../src/account/store", async (orig) => ({
  ...(await orig<typeof import("../src/account/store")>()),
  listMuseums: vi.fn(async () => store.list),
  saveMuseum: vi.fn(async () => undefined),
  collectGarbage: vi.fn(async () => 0),
}));
vi.mock("../src/api", async (orig) => ({
  ...(await orig<typeof import("../src/api")>()),
  api: {
    getMe: vi.fn(async () => server.me),
    listMuseums: vi.fn(async () => server.museums),
    getPrices: vi.fn(async () => ({ slots: { uzs: 5000, stars: 25 } })),
    createOrder: vi.fn(async (...args: unknown[]) => {
      server.orders.push(args);
      return { code: "SLT222", status: "pending", method: "card" };
    }),
  },
}));

function local(id: string, title: string, extra: Partial<LocalMuseum> = {}): LocalMuseum {
  return {
    id, v: 1, title, recipient: "", theme: "gallery_light", mascot: "boy", opening: "gift_box",
    template: "blank", created: 0, letter: "", media: [], ...extra,
  };
}
const inDays = (n: number) => new Date(Date.now() + n * 86400000).toISOString();

beforeEach(() => {
  store.list = [];
  server.me = { id: 1, first_name: "Ali", lang: "uz", is_free: false, slots: { used: 0, total: 10 }, bot_username: "SahifaBot" };
  server.museums = [];
  server.orders = [];
});

describe("home", () => {
  it("shows account and server museums with the right badges", async () => {
    store.list = [
      local("aaaaaa", "Bepul muzey", { media: [{ t: "x", k: "image" }] }),
      local("bbbbbb", "Onajonimga", { gift: { draft: 5, state: "paid" } }),
    ];
    server.museums = [
      { id: 5, slug: "s5", title: "Onajonimga", status: "active", expires_at: inDays(87), counts: { image: 1, video: 0 } },
      { id: 9, slug: "s9", title: "Topshirilgan", status: "active", expires_at: inDays(30), counts: { image: 3, video: 0 } },
      { id: 11, slug: "s11", title: "Eski qoralama", status: "draft", expires_at: null, counts: { image: 0, video: 0 } },
    ];
    const { wrapper } = await mountView(Home);
    const cards = wrapper.findAll("[data-museum]");
    expect(cards.map((c) => c.find("b").text())).toEqual(["Bepul muzey", "Onajonimga", "Topshirilgan"]);
    expect(cards[0].text()).toContain("Bepul · akkauntda");
    expect(cards[1].text()).toContain("Sovg'a qilingan");
    expect(cards[1].text()).toMatch(/8[67] kun qoldi/);
    expect(cards[2].text()).toContain("Sizga topshirilgan");
  });

  it("counter uses account museums and slots.total", async () => {
    store.list = [local("aaaaaa", "A"), local("bbbbbb", "B"), local("cccccc", "C")];
    server.me.slots = { used: 1, total: 15 };
    const { wrapper } = await mountView(Home);
    expect(wrapper.find("[data-counter]").text()).toBe("3 / 15");
  });

  it("full slots offer the +5 pack instead of a new museum", async () => {
    store.list = Array.from({ length: 10 }, (_, i) => local(`m${i}aaaa`, `M${i}`));
    const { wrapper, router } = await mountView(Home);
    expect(wrapper.find("[data-new]").exists()).toBe(false);
    const buy = wrapper.find("[data-buy-slots-card]");
    expect(buy.text()).toContain("5 000");
    await buy.trigger("click");
    await flushPromises();
    expect(server.orders[0]).toEqual(["slots", null, "card"]);
    expect(router.currentRoute.value.path).toBe("/order/SLT222");
  });

  it("starting a template creates and opens a museum", async () => {
    const { wrapper, router } = await mountView(Home);
    await wrapper.find("[data-template='birthday']").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.path).toMatch(/^\/new\/[a-z0-9]{6}\/media$/);
  });
});
