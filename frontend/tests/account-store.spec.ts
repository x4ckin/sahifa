import { afterEach, describe, expect, it, vi } from "vitest";

import { roomsNeeded } from "../src/account/rooms";
import {
  deleteLocalMuseum,
  listMuseums,
  loadMuseum,
  newMuseum,
  packPages,
  saveMuseum,
  type LocalMedia,
} from "../src/account/store";
import { cloud } from "../src/telegram";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

const token = (i: number) => `eyJ1Ijo3LCJmIjoiQlFBQ0FnSUFBeGtCQUFJQiR7aX0iLCJrIjoiaW1hZ2UifQ.${String(i).padStart(22, "x")}`;
const media = (images: number, videos = 0): LocalMedia[] => [
  ...Array.from({ length: images }, (_, i) => ({ t: token(i), k: "image" as const, c: "x".repeat(200), d: "2021-05-01" })),
  ...Array.from({ length: videos }, (_, i) => ({ t: token(1000 + i), k: "video" as const })),
];

async function keys() {
  return (await cloud.keys()).sort();
}

describe("account store", () => {
  it("round-trips a museum with 130 photos and 25 videos", async () => {
    const m = newMuseum("love", { title: "Bizning yo'l", letter: "Azizam…" });
    m.media = media(130, 25);
    m.recipient = "Aziza";
    await saveMuseum(m);
    const loaded = await loadMuseum(m.id);
    expect(loaded).toEqual(m);
    expect((await listMuseums()).map((x) => x.id)).toEqual([m.id]);
    for (const k of await keys()) expect(k.length).toBeLessThanOrEqual(128);
    const values = await cloud.get(await keys());
    for (const v of Object.values(values)) expect(v.length).toBeLessThanOrEqual(4096);
  });

  it("packPages never exceeds 4000 chars", () => {
    const pages = packPages(media(130, 25));
    expect(pages.length).toBeGreaterThan(1);
    for (const p of pages) expect(p.length).toBeLessThanOrEqual(4000);
    expect(pages.flatMap((p) => JSON.parse(p))).toHaveLength(155);
  });

  it("saveMuseum keeps the previous version when a page write fails", async () => {
    const m = newMuseum("blank", { title: "Birinchi", letter: "" });
    m.media = media(10);
    await saveMuseum(m);
    const before = await loadMuseum(m.id);

    const realSet = cloud.set.bind(cloud);
    let calls = 0;
    vi.spyOn(cloud, "set").mockImplementation(async (k, v) => {
      calls += 1;
      if (calls === 2) throw new Error("network");
      return realSet(k, v);
    });
    const changed = { ...m, title: "Ikkinchi", media: media(40) };
    await expect(saveMuseum(changed)).rejects.toThrow("network");
    vi.restoreAllMocks();

    expect(await loadMuseum(m.id)).toEqual(before);
    expect((await listMuseums()).map((x) => x.title)).toEqual(["Birinchi"]);
  });

  it("a new museum only appears in the list once fully written", async () => {
    const m = newMuseum("blank", { title: "Yangi", letter: "" });
    m.media = media(40);
    const realSet = cloud.set.bind(cloud);
    vi.spyOn(cloud, "set").mockImplementation(async (k, v) => {
      if (k === "idx") throw new Error("network");
      return realSet(k, v);
    });
    await expect(saveMuseum(m)).rejects.toThrow();
    vi.restoreAllMocks();
    expect(await listMuseums()).toEqual([]);
  });

  it("shrinking a museum removes stale pages", async () => {
    const m = newMuseum("blank", { title: "A", letter: "uzun maktub" });
    m.media = media(60);
    await saveMuseum(m);
    m.media = media(2);
    m.letter = "";
    await saveMuseum(m);
    const ks = await keys();
    expect(ks.filter((k) => /_\d+p\d+$/.test(k)).length).toBe(1);
    expect(ks.some((k) => /_\d+l$/.test(k))).toBe(false);
    expect((await loadMuseum(m.id))?.media).toHaveLength(2);
  });

  it("delete removes all keys and the index entry", async () => {
    const a = newMuseum("blank", { title: "A", letter: "x" });
    a.media = media(20);
    const b = newMuseum("blank", { title: "B", letter: "" });
    await saveMuseum(a);
    await saveMuseum(b);
    await deleteLocalMuseum(a.id);
    expect((await listMuseums()).map((x) => x.id)).toEqual([b.id]);
    expect((await keys()).some((k) => k.includes(a.id))).toBe(false);
  });

  it("listMuseums skips a broken entry instead of failing", async () => {
    const a = newMuseum("blank", { title: "A", letter: "" });
    await saveMuseum(a);
    await cloud.set("idx", JSON.stringify([a.id, "zzzzzz"]));
    expect((await listMuseums()).map((x) => x.id)).toEqual([a.id]);
  });

  it("roomsNeeded matches the backend table", () => {
    const table: [number, number, number][] = [
      [30, 5, 0], [0, 0, 0], [31, 5, 1], [40, 7, 1], [41, 5, 2], [30, 8, 2], [130, 25, 10],
    ];
    for (const [img, vid, rooms] of table) expect(roomsNeeded(img, vid)).toBe(rooms);
    expect(() => roomsNeeded(131, 0)).toThrow();
  });
});

describe("garbage collection", () => {
  it("removes pages of revisions no meta points to, keeps live ones", async () => {
    const { collectGarbage } = await import("../src/account/store");
    const m = newMuseum("blank", { title: "A", letter: "x" });
    m.media = media(3);
    await saveMuseum(m);
    await cloud.set(`m_${m.id}_99p0`, "[]"); // left by an interrupted save
    await cloud.set("m_gone00", "{}"); // museum no longer in the index
    expect(await collectGarbage()).toBe(2);
    expect(await loadMuseum(m.id)).toEqual(m);
  });
});
