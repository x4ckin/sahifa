import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalMuseum } from "../src/account/store";
import LocalMuseumView from "../src/views/LocalMuseum.vue";
import ServerMuseum from "../src/views/ServerMuseum.vue";
import { mountView } from "./helpers";

const s = vi.hoisted(() => ({ calls: [] as string[], museum: null as any, local: null as LocalMuseum | null }));

vi.mock("../src/api", async (orig) => {
  const real = await orig<typeof import("../src/api")>();
  return {
    ...real,
    api: {
      getMuseum: vi.fn(async () => s.museum),
      getMe: vi.fn(async () => ({ bot_username: "SahifaBot" })),
      getPrices: vi.fn(async () => ({ room: { uzs: 3000, stars: 15 }, reactivate: { uzs: 15000, stars: 75 } })),
      createTransfer: vi.fn(async () => {
        s.calls.push("transfer");
        return { link: "https://t.me/SahifaBot?start=tr_abc", expires_at: "2026-11-08T12:00:00+00:00" };
      }),
      cancelTransfer: vi.fn(async () => {
        s.calls.push("cancel");
        return { ok: true };
      }),
      deleteMuseum: vi.fn(async () => {
        s.calls.push("delete");
        return { ok: true };
      }),
      deleteServerMedia: vi.fn(async () => ({ ok: true })),
      tgMediaUrl: (t: string) => t,
    },
  };
});
vi.mock("../src/account/store", async (orig) => ({
  ...(await orig<typeof import("../src/account/store")>()),
  loadMuseum: vi.fn(async () => s.local),
  deleteLocalMuseum: vi.fn(async () => {
    s.calls.push("delete-local");
  }),
}));

beforeEach(() => {
  s.calls = [];
  s.museum = {
    id: 42, slug: "Xk29", title: "Onam", status: "active", locked: true, paid_at: "2026-10-01T00:00:00Z",
    expires_at: new Date(Date.now() + 87 * 86400000).toISOString(), theme: "oriental_palace", opening_style: "gift_box",
    mascot: "boy", recipient_name: "Aziza", letter_text: "Rahmat", media: [], counts: { image: 0, video: 0 },
    limits: { rooms: 3, images: 30, videos: 5 },
  };
  s.local = {
    id: "abc123", v: 1, title: "Bepul", recipient: "", theme: "gallery_light", mascot: "boy", opening: "gift_box",
    template: "blank", created: 0, letter: "", media: [{ t: "x", k: "image" }],
  };
});

describe("server museum page", () => {
  it("locked settings are read-only", async () => {
    const { wrapper } = await mountView(ServerMuseum, "/museum/42", "/museum/:id");
    expect(wrapper.text()).toContain("faqat surat va video");
    expect(wrapper.find("input[data-title]").exists()).toBe(false);
    expect(wrapper.text()).toContain("Sharqona saroy");
    expect(wrapper.text()).toMatch(/Faol · \d{2}\.\d{2}\.\d{4} gacha/);
  });

  it("transfer link can be copied and cancelled", async () => {
    const { wrapper } = await mountView(ServerMuseum, "/museum/42", "/museum/:id");
    await wrapper.find("[data-transfer]").trigger("click");
    await flushPromises();
    expect(wrapper.find("[data-transfer-link]").text()).toBe("https://t.me/SahifaBot?start=tr_abc");
    await wrapper.find("[data-transfer-cancel]").trigger("click");
    await flushPromises();
    expect(s.calls).toEqual(["transfer", "cancel"]);
    expect(wrapper.find("[data-transfer-link]").exists()).toBe(false);
  });

  it("deleting asks for confirmation", async () => {
    const { wrapper, router } = await mountView(ServerMuseum, "/museum/42", "/museum/:id");
    await wrapper.find("[data-delete]").trigger("click");
    await flushPromises();
    expect(s.calls).toEqual([]);
    await wrapper.find("[data-delete-confirm]").trigger("click");
    await flushPromises();
    expect(s.calls).toEqual(["delete"]);
    expect(router.currentRoute.value.path).toBe("/");
  });
});

describe("local museum page", () => {
  it("offers edit and gift, and deletes only after confirmation", async () => {
    const { wrapper, router } = await mountView(LocalMuseumView, "/local/abc123", "/local/:id");
    expect(wrapper.text()).toContain("Bepul");
    await wrapper.find("[data-delete]").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Chatdagi fayllar qoladi");
    await wrapper.find("[data-delete-confirm]").trigger("click");
    await flushPromises();
    expect(s.calls).toEqual(["delete-local"]);
    expect(router.currentRoute.value.path).toBe("/");
  });

  it("a gifted museum goes through the gift screen, which checks the server copy", async () => {
    s.local = { ...s.local!, gift: { draft: 42, state: "paid" } };
    const { wrapper, router } = await mountView(LocalMuseumView, "/local/abc123", "/local/:id");
    await wrapper.find("[data-gift]").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/gift/abc123");
  });
});
