/**
 * Free museums live in Telegram CloudStorage (per user, per bot, synced to every device).
 *
 * Keys (≤128 chars, values ≤4096 chars):
 *   idx                 JSON list of museum ids, in display order
 *   m_<id>              meta: settings + {rev, pages, letter}
 *   m_<id>_<rev>p<n>    media page n of revision rev
 *   m_<id>_<rev>l       letter text of revision rev
 *
 * A save writes the new revision's pages and letter under new keys, then the meta, then the index,
 * then removes the old revision. An interrupted save therefore leaves the previous version intact.
 */
import type { MascotKey, OpeningKey, TemplateKey, ThemeKey } from "../catalog";
import { TEMPLATE_DEFAULTS } from "../catalog";
import { cloud } from "../telegram";

export interface LocalMedia {
  t: string; // signed Telegram media token
  k: "image" | "video";
  c?: string; // caption
  d?: string; // taken on
}

export interface LocalMuseum {
  id: string;
  v: 1;
  title: string;
  recipient: string;
  theme: ThemeKey;
  mascot: MascotKey;
  opening: OpeningKey;
  music_id?: string;
  voice?: string;
  music?: string;
  open_at?: string;
  template: TemplateKey;
  created: number;
  letter: string;
  media: LocalMedia[];
  gift?: { draft: number; state: "draft" | "paid" };
}

interface Meta extends Omit<LocalMuseum, "letter" | "media"> {
  rev: number;
  pages: number;
  hasLetter: boolean;
}

const PAGE_LIMIT = 4000;
const ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789";

const metaKey = (id: string) => `m_${id}`;
const pageKey = (id: string, rev: number, n: number) => `m_${id}_${rev}p${n}`;
const letterKey = (id: string, rev: number) => `m_${id}_${rev}l`;

function newId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  return Array.from(bytes, (b) => ID_CHARS[b % ID_CHARS.length]).join("");
}

export function newMuseum(template: TemplateKey, text: { title: string; letter: string }): LocalMuseum {
  const defaults = TEMPLATE_DEFAULTS[template];
  return {
    id: newId(),
    v: 1,
    title: text.title,
    recipient: "",
    theme: defaults.theme,
    mascot: "boy",
    opening: defaults.opening,
    template,
    created: Date.now(),
    letter: text.letter,
    media: [],
  };
}

/** Greedy packing: each page is a JSON array no longer than `limit` characters. */
export function packPages(media: LocalMedia[], limit = PAGE_LIMIT): string[] {
  const pages: string[] = [];
  let current: LocalMedia[] = [];
  for (const item of media) {
    if (current.length && JSON.stringify([...current, item]).length > limit) {
      pages.push(JSON.stringify(current));
      current = [];
    }
    current.push(item);
  }
  if (current.length) pages.push(JSON.stringify(current));
  return pages;
}

function parse<T>(raw: string | undefined): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

async function readIndex(): Promise<string[]> {
  return parse<string[]>((await cloud.get(["idx"])).idx) ?? [];
}

async function readMeta(id: string): Promise<Meta | null> {
  return parse<Meta>((await cloud.get([metaKey(id)]))[metaKey(id)]);
}

export async function loadMuseum(id: string): Promise<LocalMuseum | null> {
  const meta = await readMeta(id);
  if (!meta) return null;
  const keys = Array.from({ length: meta.pages }, (_, n) => pageKey(id, meta.rev, n));
  if (meta.hasLetter) keys.push(letterKey(id, meta.rev));
  const values = keys.length ? await cloud.get(keys) : {};
  const media: LocalMedia[] = [];
  for (let n = 0; n < meta.pages; n++) {
    const page = parse<LocalMedia[]>(values[pageKey(id, meta.rev, n)]);
    if (!page) return null; // a missing page: treat the museum as unreadable rather than silently short
    media.push(...page);
  }
  const { rev: _rev, pages: _pages, hasLetter, ...rest } = meta;
  return { ...rest, letter: hasLetter ? values[letterKey(id, meta.rev)] ?? "" : "", media };
}

export async function listMuseums(): Promise<LocalMuseum[]> {
  const museums = await Promise.all((await readIndex()).map((id) => loadMuseum(id)));
  return museums.filter((m): m is LocalMuseum => m !== null);
}

function revisionKeys(id: string, meta: Meta | null): string[] {
  if (!meta) return [];
  const keys = Array.from({ length: meta.pages }, (_, n) => pageKey(id, meta.rev, n));
  if (meta.hasLetter) keys.push(letterKey(id, meta.rev));
  return keys;
}

export async function saveMuseum(museum: LocalMuseum): Promise<void> {
  const { id, letter, media, ...settings } = museum;
  const previous = await readMeta(id);
  const rev = (previous?.rev ?? 0) + 1;
  const pages = packPages(media);

  for (const [n, page] of pages.entries()) await cloud.set(pageKey(id, rev, n), page);
  if (letter) await cloud.set(letterKey(id, rev), letter);
  const meta: Meta = { ...settings, id, rev, pages: pages.length, hasLetter: Boolean(letter) };
  await cloud.set(metaKey(id), JSON.stringify(meta));

  const index = await readIndex();
  if (!index.includes(id)) await cloud.set("idx", JSON.stringify([...index, id]));

  // the new revision is live; dropping the old one may fail without harm
  await cloud.remove(revisionKeys(id, previous)).catch(() => undefined);
}

export async function deleteLocalMuseum(id: string): Promise<void> {
  const index = await readIndex();
  await cloud.set("idx", JSON.stringify(index.filter((x) => x !== id)));
  const meta = await readMeta(id);
  await cloud.remove([metaKey(id)]);
  await cloud.remove(revisionKeys(id, meta));
}

/** Remove keys left behind by interrupted saves (pages of revisions no meta points to). */
export async function collectGarbage(): Promise<number> {
  const all = await cloud.keys();
  const index = new Set(await readIndex());
  const live = new Set<string>(["idx"]);
  for (const id of index) {
    live.add(metaKey(id));
    for (const k of revisionKeys(id, await readMeta(id))) live.add(k);
  }
  const stale = all.filter((k) => k.startsWith("m_") && !live.has(k));
  await cloud.remove(stale);
  return stale.length;
}
