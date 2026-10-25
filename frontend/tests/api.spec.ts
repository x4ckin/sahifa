import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "../src/api";

afterEach(() => {
  vi.unstubAllGlobals();
  delete (window as any).Telegram;
});

function stubFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("api", () => {
  it("sends initData header", async () => {
    (window as any).Telegram = { WebApp: { initData: "abc=1&hash=z", initDataUnsafe: {} } };
    const fetchMock = stubFetch(200, { id: 1 });
    await api.getMe();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/me$/);
    expect(init.headers["X-Telegram-Init-Data"]).toBe("abc=1&hash=z");
  });

  it("maps {error} bodies to ApiError", async () => {
    stubFetch(409, { error: "locked" });
    const err = await api.patchMuseum(1, { title: "x" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("locked");
    expect(err.status).toBe(409);
  });

  it("network failure becomes ApiError('network')", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await api.getPrices().catch((e) => e);
    expect(err.code).toBe("network");
  });

  it("reports upload progress", async () => {
    const progress: number[] = [];
    class FakeXHR {
      upload = { onprogress: null as null | ((e: any) => void) };
      status = 200;
      responseText = JSON.stringify({ token: "T", kind: "image" });
      headers: Record<string, string> = {};
      onload: null | (() => void) = null;
      onerror: null | (() => void) = null;
      open() {}
      setRequestHeader(k: string, v: string) { this.headers[k] = v; }
      send() {
        this.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
        this.upload.onprogress?.({ lengthComputable: true, loaded: 100, total: 100 });
        this.onload?.();
      }
    }
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const result = await api.uploadTgMedia(new File(["x"], "a.jpg", { type: "image/jpeg" }), "media", (p) => progress.push(p));
    expect(result).toEqual({ token: "T", kind: "image" });
    expect(progress).toEqual([0.5, 1]);
  });

  it("builds media proxy urls", () => {
    expect(api.tgMediaUrl("a.b")).toMatch(/\/api\/tg-media\/a\.b$/);
  });
});
