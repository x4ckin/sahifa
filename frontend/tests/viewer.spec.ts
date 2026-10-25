import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../src/api";
import { initialPath } from "../src/router";
import Viewer from "../src/views/Viewer.vue";
import { mountView } from "./helpers";

const s = vi.hoisted(() => ({ result: null as any, error: null as any }));

vi.mock("../src/api", async (orig) => {
  const real = await orig<typeof import("../src/api")>();
  return {
    ...real,
    api: {
      publicMuseum: vi.fn(async () => {
        if (s.error) throw s.error;
        return s.result;
      }),
    },
  };
});

beforeEach(() => {
  delete (window as any).Telegram;
  s.error = null;
  s.result = {
    state: "open", slug: "Xk29", title: "Bizning yo'l", recipient_name: "Aziza", letter_text: "Azizam…",
    theme: "gallery_light", mascot: "boy", opening_style: "gift_box", music_id: null, music_url: null,
    voice_url: "https://api.test/media/1/v.m4a", open_at: null, rooms: 3,
    media: [
      { id: 1, kind: "image", url: "https://api.test/media/1/a.webp", thumb_url: "t", caption: "Samarqand", taken_on: "2021", position: 1 },
      { id: 2, kind: "video", url: "https://api.test/media/1/b.mp4", thumb_url: "p", caption: null, taken_on: null, position: 2 },
    ],
  };
});

describe("viewer", () => {
  it("viewer works without Telegram SDK", async () => {
    const { wrapper } = await mountView(Viewer, "/m/Xk29", "/m/:slug");
    expect(wrapper.text()).toContain("Bizning yo'l");
    expect(wrapper.text()).toContain("Aziza uchun");
    expect(wrapper.text()).toContain("Samarqand");
    expect(wrapper.findAll("img")).toHaveLength(1);
    expect(wrapper.findAll("video")).toHaveLength(1);
    expect(wrapper.find("audio").attributes("src")).toBe("https://api.test/media/1/v.m4a");
    expect(wrapper.find("[data-create-own]").exists()).toBe(true);
  });

  it("locked shows a countdown and no media", async () => {
    s.result = { state: "locked", open_at: new Date(Date.now() + 2 * 86400000 + 3600000 + 30000).toISOString(), opening_style: "gift_box", recipient_name: "Aziza", title: "Sir" };
    const { wrapper } = await mountView(Viewer, "/m/Xk29", "/m/:slug");
    expect(wrapper.text()).toContain("Sovg'a ochilishiga");
    expect(wrapper.find("[data-countdown]").text()).toMatch(/^2 kun 1 soat/);
    expect(wrapper.findAll("img")).toHaveLength(0);
  });

  it("expired and missing gifts say so", async () => {
    s.result = { state: "expired" };
    let { wrapper } = await mountView(Viewer, "/m/Xk29", "/m/:slug");
    expect(wrapper.text()).toContain("muddati tugagan");
    s.error = new ApiError("not_found", 404);
    ({ wrapper } = await mountView(Viewer, "/m/nope", "/m/:slug"));
    expect(wrapper.text()).toContain("Sovg'a topilmadi");
  });

  it("start_param m_<slug> routes to the viewer", () => {
    expect(initialPath("m_Xk29fQ_aZ8m")).toBe("/m/Xk29fQ_aZ8m");
    expect(initialPath(null)).toBeNull();
    expect(initialPath("ref_12")).toBeNull();
    expect(initialPath("m_../../x")).toBeNull();
  });
});
