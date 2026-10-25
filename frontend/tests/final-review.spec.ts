/** Regression tests for the plan-2 final review. */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalMuseum } from "../src/account/store";
import { api, ApiError } from "../src/api";
import App from "../src/App.vue";
import { i18n, setupI18n } from "../src/i18n";
import { makeRouter } from "../src/router";
import Gift from "../src/views/Gift.vue";
import { mountView } from "./helpers";

const s = vi.hoisted(() => ({ museum: null as LocalMuseum | null, calls: [] as string[] }));
vi.mock("../src/account/store", async (orig) => ({
  ...(await orig<typeof import("../src/account/store")>()),
  loadMuseum: vi.fn(async () => (s.museum ? structuredClone(s.museum) : null)),
  saveMuseum: vi.fn(async (m: LocalMuseum) => {
    s.museum = structuredClone(m);
  }),
}));

afterEach(() => {
  delete (window as any).Telegram;
  vi.restoreAllMocks();
});

describe("a paid copy whose server museum is gone", () => {
  beforeEach(() => {
    s.calls = [];
    s.museum = {
      id: "abc123", v: 1, title: "Onam", recipient: "", theme: "gallery_light", mascot: "boy", opening: "gift_box",
      template: "blank", created: 0, letter: "", media: [{ t: "i0", k: "image" }], gift: { draft: 7, state: "paid" },
    };
    vi.spyOn(api, "getPrices").mockResolvedValue({ museum: { uzs: 15000, stars: 75 }, room: { uzs: 3000, stars: 15 } } as any);
    vi.spyOn(api, "getMuseum").mockRejectedValue(new ApiError("not_found", 404));
    vi.spyOn(api, "importMuseum").mockImplementation(async () => {
      s.calls.push("import");
      return { id: 60, slug: "n" } as any;
    });
    vi.spyOn(api, "createOrder").mockResolvedValue({ code: "N1", status: "pending", method: "card" } as any);
  });

  it("can be gifted again", async () => {
    const { wrapper, router } = await mountView(Gift, "/gift/abc123", "/gift/:id");
    await wrapper.find("[data-method='card']").trigger("click");
    await wrapper.find("[data-pay]").trigger("click");
    await flushPromises();
    expect(s.calls).toEqual(["import"]);
    expect(router.currentRoute.value.fullPath).toBe("/order/N1?local=abc123");
  });
});

describe("back navigation", () => {
  it("shows Telegram's back button on inner screens and hides it at home", async () => {
    const back = { show: vi.fn(), hide: vi.fn(), onClick: vi.fn(), offClick: vi.fn() };
    (window as any).Telegram = { WebApp: { initData: "x=1&hash=y", initDataUnsafe: {}, BackButton: back } };
    const router = makeRouter();
    await router.push("/");
    mount(App, { global: { plugins: [setupI18n("uz"), router], stubs: { RouterView: true } } });
    await flushPromises();
    expect(back.show).not.toHaveBeenCalled();
    await router.push("/m/abc");
    await flushPromises();
    expect(back.show).toHaveBeenCalled();
    await router.push("/");
    await flushPromises();
    expect(back.hide).toHaveBeenCalled();
  });

  it("outside Telegram inner screens get an in-page back link", async () => {
    const router = makeRouter();
    await router.push("/m/abc");
    const wrapper = mount(App, { global: { plugins: [setupI18n("uz"), router], stubs: { RouterView: true } } });
    await flushPromises();
    expect(wrapper.find("[data-back]").exists()).toBe(true);
  });
});

describe("error messages", () => {
  it("every code the store and backend can raise has a message", () => {
    setupI18n("uz");
    const codes = [
      "storage_full", "too_large", "item_too_large", "broken", "timeout", "already_paid", "payment_in_review",
      "bad_order", "not_editable", "media_full", "start_bot", "telegram_unavailable", "network",
    ];
    for (const code of codes) expect(i18n.global.te(`errors.${code}`), code).toBe(true);
  });
});

describe("uploads", () => {
  it("a stalled upload times out instead of hanging the queue", async () => {
    class StalledXHR {
      upload = { onprogress: null };
      timeout = 0;
      ontimeout: null | (() => void) = null;
      onload = null;
      onerror = null;
      open() {}
      setRequestHeader() {}
      send() {
        expect(this.timeout).toBeGreaterThan(0);
        this.ontimeout?.();
      }
    }
    vi.stubGlobal("XMLHttpRequest", StalledXHR);
    const err = await api.uploadTgMedia(new File(["x"], "a.jpg"), "media").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("network");
    vi.unstubAllGlobals();
  });
});
