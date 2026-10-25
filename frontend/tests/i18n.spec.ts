import { describe, expect, it } from "vitest";

import { MASCOTS, OPENINGS, TEMPLATES, TEMPLATE_DEFAULTS, THEMES } from "../src/catalog";
import { errorText, pickLocale, setupI18n } from "../src/i18n";
import ru from "../src/i18n/ru";
import uz from "../src/i18n/uz";

function flatKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? flatKeys(v as Record<string, unknown>, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("catalog", () => {
  it("catalog keys match the backend contract", () => {
    expect(THEMES.map((t) => t.key)).toEqual([
      "gallery_light", "gallery_night", "oriental_palace", "spring_garden", "winter_tale", "cosmos",
    ]);
    expect(OPENINGS.map((o) => o.key)).toEqual(["gift_box", "sealed_letter", "golden_key", "starry_sky"]);
    expect(MASCOTS.map((m) => m.key)).toEqual([
      "boy", "girl", "penguin", "cat", "puppy", "bear", "bunny", "fox", "robot", "dragon",
    ]);
    expect(TEMPLATES.map((t) => t.key)).toEqual(["birthday", "love", "mom", "wedding", "graduation", "march8", "blank"]);
    for (const key of [...THEMES, ...OPENINGS, ...MASCOTS, ...TEMPLATES].map((x) => x.key)) {
      expect(key).toMatch(/^[a-z0-9_]{1,32}$/);
    }
    for (const t of TEMPLATES) {
      const d = TEMPLATE_DEFAULTS[t.key];
      expect(THEMES.some((x) => x.key === d.theme)).toBe(true);
      expect(OPENINGS.some((x) => x.key === d.opening)).toBe(true);
    }
  });
});

describe("i18n", () => {
  it("every message key exists in uz and ru", () => {
    expect(flatKeys(ru).sort()).toEqual(flatKeys(uz).sort());
  });

  it("every catalog item has a translation", () => {
    const keys = new Set(flatKeys(uz));
    for (const item of [...THEMES, ...OPENINGS, ...MASCOTS, ...TEMPLATES]) expect(keys.has(item.i18nKey)).toBe(true);
  });

  it("picks russian only for ru", () => {
    expect(pickLocale("ru")).toBe("ru");
    expect(pickLocale("uz")).toBe("uz");
    expect(pickLocale("en")).toBe("uz");
    expect(pickLocale(undefined)).toBe("uz");
  });

  it("translates backend error codes, with a generic fallback", () => {
    setupI18n("uz");
    expect(errorText("start_bot")).toMatch(/bot/i);
    expect(errorText("something_new")).toBe(errorText("unknown"));
  });
});
