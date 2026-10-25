import { afterEach, describe, expect, it, vi } from "vitest";

import { cloud, tg } from "../src/telegram";

afterEach(() => {
  delete (window as any).Telegram;
  localStorage.clear();
});

function fakeWebApp(overrides: Record<string, unknown> = {}) {
  const store: Record<string, string> = {};
  const wa = {
    initData: "query_id=1&hash=x",
    initDataUnsafe: { user: { id: 7, first_name: "Ali", language_code: "ru" }, start_param: "m_abc" },
    CloudStorage: {
      setItem: (k: string, v: string, cb: (e: unknown, ok?: boolean) => void) => { store[k] = v; cb(null, true); },
      getItems: (ks: string[], cb: (e: unknown, v?: Record<string, string>) => void) =>
        cb(null, Object.fromEntries(ks.map((k) => [k, store[k] ?? ""]))),
      removeItems: (ks: string[], cb: (e: unknown, ok?: boolean) => void) => { ks.forEach((k) => delete store[k]); cb(null, true); },
      getKeys: (cb: (e: unknown, ks?: string[]) => void) => cb(null, Object.keys(store)),
    },
    MainButton: { setText: vi.fn().mockReturnThis(), show: vi.fn().mockReturnThis(), hide: vi.fn().mockReturnThis(), onClick: vi.fn(), offClick: vi.fn() },
    openInvoice: (_url: string, cb: (s: string) => void) => cb("paid"),
    ...overrides,
  };
  (window as any).Telegram = { WebApp: wa };
  return { wa, store };
}

describe("telegram", () => {
  it("falls back when the SDK is missing", async () => {
    expect(tg.available()).toBe(false);
    expect(tg.initData()).toBe("");
    expect(tg.user()).toBeNull();
    const cleanup = tg.mainButton("x", () => {});
    expect(typeof cleanup).toBe("function");
    expect(await tg.openInvoice("https://t.me/$x")).toBe("failed");
    await cloud.set("m_a", "1");
    expect(localStorage.getItem("sahifa:m_a")).toBe("1");
    expect(await cloud.get(["m_a", "nope"])).toEqual({ m_a: "1", nope: "" });
    expect(await cloud.keys()).toEqual(["m_a"]);
    await cloud.remove(["m_a"]);
    expect(await cloud.keys()).toEqual([]);
  });

  it("wraps CloudStorage callbacks in promises", async () => {
    const { store } = fakeWebApp();
    await cloud.set("idx", "[]");
    expect(store.idx).toBe("[]");
    expect(await cloud.get(["idx"])).toEqual({ idx: "[]" });
    expect(tg.available()).toBe(true);
    expect(tg.user()?.id).toBe(7);
    expect(tg.startParam()).toBe("m_abc");
    expect(await tg.openInvoice("https://t.me/$x")).toBe("paid");
  });

  it("rejects when CloudStorage reports an error", async () => {
    fakeWebApp({
      CloudStorage: { setItem: (_k: string, _v: string, cb: (e: unknown) => void) => cb("STORAGE_KEY_CLOUD_LIMIT") },
    });
    await expect(cloud.set("a", "b")).rejects.toThrow("STORAGE_KEY_CLOUD_LIMIT");
  });

  it("main button cleanup unbinds the handler", () => {
    const { wa } = fakeWebApp();
    const fn = () => {};
    const cleanup = tg.mainButton("Davom", fn);
    expect(wa.MainButton.setText).toHaveBeenCalledWith("Davom");
    cleanup();
    expect(wa.MainButton.offClick).toHaveBeenCalledWith(fn);
    expect(wa.MainButton.hide).toHaveBeenCalled();
  });
});
