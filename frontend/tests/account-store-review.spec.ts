/** Regression tests for the Task 6 checkpoint review: concurrency, devices, real limits. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { collectGarbage, listMuseums, loadMuseum, newMuseum, saveMuseum, type LocalMedia } from "../src/account/store";
import { cloud } from "../src/telegram";
import { makeFakeCloud } from "./fakeCloud";

afterEach(() => {
  delete (window as any).Telegram;
  localStorage.clear();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const token = (i: number) => `eyJ1Ijo3LCJmIjoiQlFBQ0FnSUFBeGtCQUFJQiR7aX0iLCJrIjoiaW1hZ2UifQ.${String(i).padStart(22, "x")}`;
const media = (n: number, caption = ""): LocalMedia[] =>
  Array.from({ length: n }, (_, i) => ({ t: token(i), k: "image" as const, ...(caption ? { c: caption } : {}) }));

describe("store under real CloudStorage rules", () => {
  it("overlapping saves never mix two versions", async () => {
    makeFakeCloud().install();
    const m = newMuseum("blank", { title: "A", letter: "" });
    m.media = media(60, "birinchi");
    await saveMuseum(m);
    const a = { ...m, title: "A1", media: media(80, "aaaa") };
    const b = { ...m, title: "B2", media: media(20, "bbbb") };
    await Promise.all([saveMuseum(a), saveMuseum(b)]); // a debounce firing while the previous save runs
    const loaded = await loadMuseum(m.id);
    expect(loaded?.title).toBe("B2");
    expect(loaded?.media).toEqual(b.media);
  });

  it("two devices saving the same museum leave one complete version", async () => {
    const shared = new Map<string, string>();
    const phone = makeFakeCloud(shared, 1);
    const desktop = makeFakeCloud(shared, 3);
    phone.install();
    const m = newMuseum("blank", { title: "A", letter: "" });
    m.media = media(40, "x");
    await saveMuseum(m);
    const p1 = saveMuseum({ ...m, title: "telefon", media: media(70, "phone") });
    desktop.install(); // the other device starts while the phone is mid-save
    const p2 = saveMuseum({ ...m, title: "kompyuter", media: media(10, "desk") });
    await Promise.all([p1, p2]);
    const loaded = await loadMuseum(m.id);
    expect(["telefon", "kompyuter"]).toContain(loaded?.title);
    const expected = loaded?.title === "telefon" ? media(70, "phone") : media(10, "desk");
    expect(loaded?.media).toEqual(expected);
  });

  it("garbage collection never deletes a save in progress on another device", async () => {
    const shared = new Map<string, string>();
    makeFakeCloud(shared).install();
    const m = newMuseum("blank", { title: "A", letter: "" });
    m.media = media(10);
    await saveMuseum(m);
    // the other device has written the pages of a newer revision but not its meta yet
    const live = JSON.parse(shared.get(`m_${m.id}`)!);
    const freshRev = Date.now().toString(36) + "zz99";
    shared.set(`m_${m.id}_${freshRev}p0`, JSON.stringify(media(1)));
    await collectGarbage();
    expect(shared.has(`m_${m.id}_${freshRev}p0`)).toBe(true);
    expect(live.rev).toBeTruthy();
  });

  it("garbage collection never deletes a museum missing from the index", async () => {
    const shared = new Map<string, string>();
    makeFakeCloud(shared).install();
    const m = newMuseum("blank", { title: "Yangi", letter: "" });
    await saveMuseum(m);
    shared.set("idx", "[]"); // another device overwrote the index
    await collectGarbage();
    expect((await listMuseums()).map((x) => x.id)).toEqual([m.id]);
  });

  it("museums created at the same time on two devices are both listed", async () => {
    const shared = new Map<string, string>();
    const a = makeFakeCloud(shared, 1);
    const b = makeFakeCloud(shared, 4);
    a.install();
    const x = newMuseum("blank", { title: "X", letter: "" });
    const px = saveMuseum(x);
    b.install();
    const y = newMuseum("blank", { title: "Y", letter: "" });
    await Promise.all([px, saveMuseum(y)]);
    expect((await listMuseums()).map((m) => m.title).sort()).toEqual(["X", "Y"]);
  });

  it("a missing letter marks the museum broken and it is never saved over", async () => {
    const shared = new Map<string, string>();
    makeFakeCloud(shared).install();
    const m = newMuseum("love", { title: "A", letter: "Azizam" });
    await saveMuseum(m);
    for (const k of [...shared.keys()]) if (/_l\d+$/.test(k)) shared.delete(k);
    const loaded = await loadMuseum(m.id);
    expect(loaded?.broken).toBe(true);
    await expect(saveMuseum(loaded!)).rejects.toThrow("broken");
    expect((await listMuseums())[0].broken).toBe(true);
  });

  it("cyrillic captions and a 3000-character cyrillic letter fit the byte limits", async () => {
    makeFakeCloud().install();
    const m = newMuseum("blank", { title: "Наш музей", letter: "Ж".repeat(3000) });
    m.media = media(155, "Самарканд — наше первое путешествие ".repeat(5).slice(0, 200));
    await saveMuseum(m);
    expect(await loadMuseum(m.id)).toEqual(m);
  });

  it("refuses to save when the 1024-key budget would be exceeded", async () => {
    const shared = new Map<string, string>();
    for (let i = 0; i < 1015; i++) shared.set(`junk${i}`, "x");
    makeFakeCloud(shared).install();
    const m = newMuseum("blank", { title: "A", letter: "" });
    m.media = media(155, "c".repeat(200));
    await expect(saveMuseum(m)).rejects.toThrow("storage_full");
  });

  it("a CloudStorage callback that never fires rejects instead of hanging", async () => {
    vi.useFakeTimers();
    (window as any).Telegram = {
      WebApp: {
        initData: "x=1&hash=y", initDataUnsafe: {}, isVersionAtLeast: () => true,
        CloudStorage: { getItems: () => undefined },
      },
    };
    const pending = cloud.get(["idx"]);
    const check = expect(pending).rejects.toThrow("timeout");
    await vi.advanceTimersByTimeAsync(11_000);
    await check;
  });

  it("old Telegram clients without CloudStorage fall back to local storage", async () => {
    (window as any).Telegram = {
      WebApp: {
        initData: "x=1&hash=y", initDataUnsafe: {}, isVersionAtLeast: (v: string) => v < "6.9",
        CloudStorage: { setItem: () => { throw new Error("WebAppMethodUnsupported"); } },
      },
    };
    await cloud.set("idx", "[]");
    expect(localStorage.getItem("sahifa:idx")).toBe("[]");
  });
});
