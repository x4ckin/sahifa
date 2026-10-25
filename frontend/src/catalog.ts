/** Keys shared with the backend and the 3D scene (plan 3) — a contract, do not rename. */

export interface CatalogItem<K extends string = string> {
  key: K;
  emoji: string;
  i18nKey: string;
}

export const THEMES = [
  { key: "gallery_light", emoji: "🏛", i18nKey: "theme.gallery_light" },
  { key: "gallery_night", emoji: "🌙", i18nKey: "theme.gallery_night" },
  { key: "oriental_palace", emoji: "🕌", i18nKey: "theme.oriental_palace" },
  { key: "spring_garden", emoji: "🌸", i18nKey: "theme.spring_garden" },
  { key: "winter_tale", emoji: "❄️", i18nKey: "theme.winter_tale" },
  { key: "cosmos", emoji: "🪐", i18nKey: "theme.cosmos" },
] as const satisfies readonly CatalogItem[];

export const OPENINGS = [
  { key: "gift_box", emoji: "🎁", i18nKey: "opening.gift_box" },
  { key: "sealed_letter", emoji: "💌", i18nKey: "opening.sealed_letter" },
  { key: "golden_key", emoji: "🗝️", i18nKey: "opening.golden_key" },
  { key: "starry_sky", emoji: "✨", i18nKey: "opening.starry_sky" },
] as const satisfies readonly CatalogItem[];

export const MASCOTS = [
  { key: "boy", emoji: "🧑", i18nKey: "mascot.boy" },
  { key: "girl", emoji: "👧", i18nKey: "mascot.girl" },
  { key: "penguin", emoji: "🐧", i18nKey: "mascot.penguin" },
  { key: "cat", emoji: "🐱", i18nKey: "mascot.cat" },
  { key: "puppy", emoji: "🐶", i18nKey: "mascot.puppy" },
  { key: "bear", emoji: "🧸", i18nKey: "mascot.bear" },
  { key: "bunny", emoji: "🐰", i18nKey: "mascot.bunny" },
  { key: "fox", emoji: "🦊", i18nKey: "mascot.fox" },
  { key: "robot", emoji: "🤖", i18nKey: "mascot.robot" },
  { key: "dragon", emoji: "🐲", i18nKey: "mascot.dragon" },
] as const satisfies readonly CatalogItem[];

export const TEMPLATES = [
  { key: "birthday", emoji: "🎂", i18nKey: "template.birthday" },
  { key: "love", emoji: "💞", i18nKey: "template.love" },
  { key: "mom", emoji: "🌷", i18nKey: "template.mom" },
  { key: "wedding", emoji: "💍", i18nKey: "template.wedding" },
  { key: "graduation", emoji: "🎓", i18nKey: "template.graduation" },
  { key: "march8", emoji: "💐", i18nKey: "template.march8" },
  { key: "blank", emoji: "✏️", i18nKey: "template.blank" },
] as const satisfies readonly CatalogItem[];

export type ThemeKey = (typeof THEMES)[number]["key"];
export type OpeningKey = (typeof OPENINGS)[number]["key"];
export type MascotKey = (typeof MASCOTS)[number]["key"];
export type TemplateKey = (typeof TEMPLATES)[number]["key"];

/** What each template pre-fills; the user can change all of it. letterKey → i18n text. */
export const TEMPLATE_DEFAULTS: Record<TemplateKey, { theme: ThemeKey; opening: OpeningKey; letterKey: string | null }> = {
  birthday: { theme: "gallery_light", opening: "gift_box", letterKey: "letter.birthday" },
  love: { theme: "gallery_night", opening: "starry_sky", letterKey: "letter.love" },
  mom: { theme: "spring_garden", opening: "sealed_letter", letterKey: "letter.mom" },
  wedding: { theme: "oriental_palace", opening: "golden_key", letterKey: "letter.wedding" },
  graduation: { theme: "gallery_light", opening: "golden_key", letterKey: "letter.graduation" },
  march8: { theme: "spring_garden", opening: "gift_box", letterKey: "letter.march8" },
  blank: { theme: "gallery_light", opening: "gift_box", letterKey: null },
};
