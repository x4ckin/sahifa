import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LocalMedia, LocalMuseum } from "../src/account/store";
import NewDecor from "../src/views/NewDecor.vue";
import NewMedia from "../src/views/NewMedia.vue";
import NewReview from "../src/views/NewReview.vue";
import { mountView } from "./helpers";

const state = vi.hoisted(() => ({ museum: null as LocalMuseum | null, saved: [] as LocalMuseum[], uploads: 0 }));

vi.mock("../src/account/store", async (orig) => ({
  ...(await orig<typeof import("../src/account/store")>()),
  loadMuseum: vi.fn(async () => (state.museum ? structuredClone(state.museum) : null)),
  saveMuseum: vi.fn(async (m: LocalMuseum) => {
    state.saved.push(structuredClone(m));
  }),
}));
vi.mock("../src/api", async (orig) => ({
  ...(await orig<typeof import("../src/api")>()),
  api: {
    uploadTgMedia: vi.fn(async (f: File) => {
      state.uploads++;
      return { token: `T-${f.name}`, kind: f.type.startsWith("video") ? "video" : "image" };
    }),
    tgMediaUrl: (t: string) => `https://api.test/api/tg-media/${t}`,
  },
}));

const items = (n: number, k: "image" | "video" = "image"): LocalMedia[] =>
  Array.from({ length: n }, (_, i) => ({ t: `${k}${i}`, k }));

function museum(extra: Partial<LocalMuseum> = {}): LocalMuseum {
  return {
    id: "abc123", v: 1, title: "Bizning muzeyimiz", recipient: "", theme: "gallery_light", mascot: "boy",
    opening: "gift_box", template: "blank", created: 0, letter: "", media: [], ...extra,
  };
}

async function pick(wrapper: any, files: File[]) {
  const input = wrapper.find("input[type=file][data-media-input]");
  Object.defineProperty(input.element, "files", { value: files, configurable: true });
  await input.trigger("change");
  await flushPromises();
  await new Promise((r) => setTimeout(r, 0));
  await flushPromises();
}

const latestSave = () => state.saved[state.saved.length - 1];

beforeEach(() => {
  vi.useRealTimers();
  state.museum = museum();
  state.saved = [];
  state.uploads = 0;
});

describe("create — media", () => {
  it("adding photos saves tokens to the museum", async () => {
    const { wrapper } = await mountView(NewMedia, "/new/abc123/media", "/new/:id/media");
    await pick(wrapper, [new File(["a"], "a.jpg", { type: "image/jpeg" }), new File(["b"], "b.mp4", { type: "video/mp4" })]);
    await new Promise((r) => setTimeout(r, 700)); // debounce
    expect(latestSave().media).toEqual([{ t: "T-a.jpg", k: "image" }, { t: "T-b.mp4", k: "video" }]);
  });

  it("limits stop at 130 photos and 25 videos", async () => {
    state.museum = museum({ media: [...items(130), ...items(25, "video")] });
    const { wrapper } = await mountView(NewMedia, "/new/abc123/media", "/new/:id/media");
    await pick(wrapper, [new File(["a"], "a.jpg", { type: "image/jpeg" })]);
    expect(state.uploads).toBe(0);
    expect(wrapper.text()).toContain("Limit: 130 ta surat va 25 ta video");
  });

  it("shows rooms needed when over 30 photos", async () => {
    state.museum = museum({ media: items(35) });
    const { wrapper } = await mountView(NewMedia, "/new/abc123/media", "/new/:id/media");
    expect(wrapper.text()).toContain("+1 xona");
    expect(wrapper.find("[data-counter]").text()).toContain("35/130");
  });

  it("moving an item changes the cover and is saved", async () => {
    state.museum = museum({ media: items(3) });
    const { wrapper } = await mountView(NewMedia, "/new/abc123/media", "/new/:id/media");
    await wrapper.findAll("[data-move-up]")[1].trigger("click");
    await new Promise((r) => setTimeout(r, 700));
    expect(latestSave().media.map((m) => m.t)).toEqual(["image1", "image0", "image2"]);
  });
});

describe("create — decor", () => {
  it("text fields enforce max lengths", async () => {
    const { wrapper } = await mountView(NewDecor, "/new/abc123/decor", "/new/:id/decor");
    expect(wrapper.find("[data-recipient]").attributes("maxlength")).toBe("60");
    expect(wrapper.find("[data-title]").attributes("maxlength")).toBe("80");
    expect(wrapper.find("[data-letter]").attributes("maxlength")).toBe("3000");
  });

  it("choosing a theme saves it", async () => {
    const { wrapper } = await mountView(NewDecor, "/new/abc123/decor", "/new/:id/decor");
    await wrapper.find("[data-option='oriental_palace']").trigger("click");
    await new Promise((r) => setTimeout(r, 700));
    expect(latestSave().theme).toBe("oriental_palace");
  });

  it("open date must be within 120 days", async () => {
    const { wrapper } = await mountView(NewDecor, "/new/abc123/decor", "/new/:id/decor");
    const far = new Date(Date.now() + 200 * 86400000).toISOString().slice(0, 10);
    await wrapper.find("[data-open-at]").setValue(far);
    await new Promise((r) => setTimeout(r, 700));
    expect(wrapper.text()).toContain("120 kun ichida");
    expect(state.saved.every((m) => !m.open_at)).toBe(true);
    const near = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
    await wrapper.find("[data-open-at]").setValue(near);
    await new Promise((r) => setTimeout(r, 700));
    expect(latestSave().open_at?.slice(0, 10)).toBe(near);
  });
});

describe("create — review", () => {
  it("shows the gallery and offers to gift", async () => {
    state.museum = museum({ media: items(2), letter: "Azizam" });
    const { wrapper, router } = await mountView(NewReview, "/new/abc123/review", "/new/:id/review");
    expect(wrapper.findAll("[data-gallery] img")).toHaveLength(2);
    expect(wrapper.text()).toContain("Azizam");
    await wrapper.find("[data-gift]").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/gift/abc123");
  });
});
