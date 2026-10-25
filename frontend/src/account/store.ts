/**
 * Free museums live in Telegram CloudStorage (per user, per bot, synced to every device).
 * These are the user's only copy, so every rule below exists to never lose or mix data.
 *
 * Keys (≤128 chars [A-Za-z0-9_-], values ≤4096 bytes, ≤1024 keys):
 *   idx                     display-order hint only (never the source of truth)
 *   m_<id>                  meta: settings + {rev, pages, letterParts}  — the museum exists iff this exists
 *   m_<id>_<rev>_p<n>       media page n of revision rev
 *   m_<id>_<rev>_l<n>       letter part n of revision rev
 *
 * rev = base36 time + 4 random chars, unique per save, so two devices never write the same keys.
 * A save writes its pages and letter first, then the meta (the switch-over), then tidies up.
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
  /** link to the server copy: draft id, payment state, open order code, and a hash of what was imported */
  gift?: { draft: number; state: "draft" | "paid"; order?: string; hash?: string };
  /** set when stored data is incomplete; such a museum is shown but never saved over */
  broken?: true;
}

interface Meta extends Omit<LocalMuseum, "letter" | "media" | "broken"> {
  rev: string;
  pages: number;
  letterParts: number;
}

export class StoreError extends Error {}

const VALUE_LIMIT = 4096;
const PAGE_LIMIT = 4000; // bytes, leaves headroom under Telegram's 4096
const KEY_BUDGET = 1024;
const GC_GRACE_MS = 24 * 3600 * 1000;
const ID = /^[a-z0-9]{6}$/;
const META_KEY = /^m_([a-z0-9]{6})$/;
const PART_KEY = /^m_([a-z0-9]{6})_([a-z0-9]+)_(p|l)\d+$/;

const metaKey = (id: string) => `m_${id}`;
const pageKey = (id: string, rev: string, n: number) => `m_${id}_${rev}_p${n}`;
const letterKey = (id: string, rev: string, n: number) => `m_${id}_${rev}_l${n}`;
const utf8 = (s: string) => new TextEncoder().encode(s).length;

function random(n: number): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  return Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => chars[b % chars.length]).join("");
}

const newRev = () => Date.now().toString(36) + random(4);
const revTime = (rev: string) => parseInt(rev.slice(0, -4), 36) || 0;

export function newMuseum(template: TemplateKey, text: { title: string; letter: string }): LocalMuseum {
  const defaults = TEMPLATE_DEFAULTS[template];
  return {
    id: random(6),
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

/** Greedy packing of media into JSON arrays of at most `limit` UTF-8 bytes each. */
export function packPages(media: LocalMedia[], limit = PAGE_LIMIT): string[] {
  const pages: string[] = [];
  let current: LocalMedia[] = [];
  for (const item of media) {
    if (utf8(JSON.stringify([item])) > limit) throw new StoreError("item_too_large");
    if (current.length && utf8(JSON.stringify([...current, item])) > limit) {
      pages.push(JSON.stringify(current));
      current = [];
    }
    current.push(item);
  }
  if (current.length) pages.push(JSON.stringify(current));
  return pages;
}

/** Split text into parts of at most `limit` UTF-8 bytes, never inside a character. */
function splitText(text: string, limit = PAGE_LIMIT): string[] {
  const parts: string[] = [];
  let current = "";
  let size = 0;
  for (const ch of text) {
    const n = utf8(ch);
    if (size + n > limit) {
      parts.push(current);
      current = "";
      size = 0;
    }
    current += ch;
    size += n;
  }
  if (current) parts.push(current);
  return parts;
}

function parseJson<T>(raw: string | undefined): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function validMeta(m: Meta | null): m is Meta {
  return (
    !!m && typeof m.rev === "string" && Number.isInteger(m.pages) && m.pages >= 0 &&
    Number.isInteger(m.letterParts) && m.letterParts >= 0 && typeof m.title === "string"
  );
}

function partKeys(id: string, meta: Meta): string[] {
  return [
    ...Array.from({ length: meta.pages }, (_, n) => pageKey(id, meta.rev, n)),
    ...Array.from({ length: meta.letterParts }, (_, n) => letterKey(id, meta.rev, n)),
  ];
}

async function readMetas(ids: string[]): Promise<Map<string, Meta | null>> {
  const raw = ids.length ? await cloud.get(ids.map(metaKey)) : {};
  return new Map(ids.map((id) => [id, parseJson<Meta>(raw[metaKey(id)])]));
}

function brokenFrom(id: string, meta: Meta | null): LocalMuseum {
  return {
    ...newMuseum("blank", { title: meta?.title ?? "?", letter: "" }),
    ...(meta ?? {}),
    id,
    letter: "",
    media: [],
    broken: true,
  };
}

async function assemble(id: string, meta: Meta | null): Promise<LocalMuseum | null> {
  if (meta === null) return null;
  if (!validMeta(meta)) return brokenFrom(id, meta);
  const keys = partKeys(id, meta);
  const values = keys.length ? await cloud.get(keys) : {};
  const media: LocalMedia[] = [];
  for (let n = 0; n < meta.pages; n++) {
    const page = parseJson<LocalMedia[]>(values[pageKey(id, meta.rev, n)]);
    if (!Array.isArray(page)) return brokenFrom(id, meta);
    media.push(...page);
  }
  let letter = "";
  for (let n = 0; n < meta.letterParts; n++) {
    const part = values[letterKey(id, meta.rev, n)];
    if (!part) return brokenFrom(id, meta); // CloudStorage returns "" for a missing key
    letter += part;
  }
  const { rev: _rev, pages: _pages, letterParts: _parts, ...settings } = meta;
  return { ...settings, id, letter, media };
}

export async function loadMuseum(id: string): Promise<LocalMuseum | null> {
  if (!ID.test(id)) return null;
  return assemble(id, (await readMetas([id])).get(id) ?? null);
}

/** Every museum that has a meta, ordered by the idx hint and then by creation time. */
export async function listMuseums(): Promise<LocalMuseum[]> {
  const [keys, hint] = await Promise.all([cloud.keys(), cloud.get(["idx"])]);
  const order = parseJson<string[]>(hint.idx) ?? [];
  const ids = keys.map((k) => META_KEY.exec(k)?.[1]).filter((x): x is string => Boolean(x));
  const metas = await readMetas(ids);
  const museums = (await Promise.all(ids.map((id) => assemble(id, metas.get(id) ?? null)))).filter(
    (m): m is LocalMuseum => m !== null,
  );
  const rank = (m: LocalMuseum) => {
    const i = order.indexOf(m.id);
    return i === -1 ? Number.MAX_SAFE_INTEGER : i;
  };
  return museums.sort((a, b) => rank(a) - rank(b) || a.created - b.created);
}

async function writeMuseum(museum: LocalMuseum): Promise<void> {
  const { id, letter, media, broken: _broken, ...settings } = museum;
  const previous = (await readMetas([id])).get(id) ?? null;
  const rev = newRev();
  const pages = packPages(media);
  const letterParts = splitText(letter);
  const meta: Meta = { ...settings, id, rev, pages: pages.length, letterParts: letterParts.length };
  const metaJson = JSON.stringify(meta);
  if (utf8(metaJson) > VALUE_LIMIT) throw new StoreError("too_large");

  const existing = new Set(await cloud.keys());
  const needed = pages.length + letterParts.length + (existing.has(metaKey(id)) ? 0 : 1) + (existing.has("idx") ? 0 : 1);
  if (existing.size + needed > KEY_BUDGET) throw new StoreError("storage_full");

  for (const [n, page] of pages.entries()) await cloud.set(pageKey(id, rev, n), page);
  for (const [n, part] of letterParts.entries()) await cloud.set(letterKey(id, rev, n), part);
  await cloud.set(metaKey(id), metaJson); // the switch-over: from here the new version is live

  // tidy-up may fail without harm: the museum is already complete
  try {
    const hint = parseJson<string[]>((await cloud.get(["idx"])).idx) ?? [];
    if (!hint.includes(id)) await cloud.set("idx", JSON.stringify([...hint, id]));
    if (validMeta(previous)) await cloud.remove(partKeys(id, previous));
  } catch {
    /* garbage collection will catch up */
  }
}

// one save at a time per museum; when saves pile up, only the newest state is written
const latest = new Map<string, LocalMuseum>();
const running = new Map<string, Promise<void>>();

export function saveMuseum(museum: LocalMuseum): Promise<void> {
  if (museum.broken) return Promise.reject(new StoreError("broken"));
  if (!ID.test(museum.id)) return Promise.reject(new StoreError("bad_id"));
  latest.set(museum.id, museum);
  const previous = running.get(museum.id) ?? Promise.resolve();
  const next = previous
    .catch(() => undefined)
    .then(async () => {
      const todo = latest.get(museum.id);
      if (!todo) return; // an earlier queued run already wrote the newest state
      latest.delete(museum.id);
      await writeMuseum(todo);
    });
  running.set(museum.id, next);
  void next.finally(() => running.get(museum.id) === next && running.delete(museum.id)).catch(() => undefined);
  return next;
}

export async function deleteLocalMuseum(id: string): Promise<void> {
  if (!ID.test(id)) return;
  latest.delete(id); // a pending save must not bring it back
  await running.get(id)?.catch(() => undefined);
  const meta = (await readMetas([id])).get(id) ?? null;
  await cloud.remove([metaKey(id)]); // gone from the list from here on
  if (validMeta(meta)) await cloud.remove(partKeys(id, meta)).catch(() => undefined);
  const hint = parseJson<string[]>((await cloud.get(["idx"])).idx) ?? [];
  if (hint.includes(id)) await cloud.set("idx", JSON.stringify(hint.filter((x) => x !== id))).catch(() => undefined);
}

/**
 * Remove parts of old revisions left by interrupted saves or by another device.
 * Never touches metas, the live revision, or anything younger than a day (a save may be running elsewhere).
 */
export async function collectGarbage(now = Date.now()): Promise<number> {
  const keys = await cloud.keys();
  const ids = [...new Set(keys.map((k) => PART_KEY.exec(k)?.[1]).filter((x): x is string => Boolean(x)))];
  const metas = await readMetas(ids);
  const stale = keys.filter((k) => {
    const match = PART_KEY.exec(k);
    if (!match) return false;
    const [, id, rev] = match;
    const live = metas.get(id);
    if (live && live.rev === rev) return false;
    return now - revTime(rev) > GC_GRACE_MS;
  });
  await cloud.remove(stale);
  return stale.length;
}
