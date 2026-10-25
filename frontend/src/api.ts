/** The only module that talks to the Sahifa backend. Shapes mirror backend/sahifa/api/*. */
import { tg } from "./telegram";

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public code: string, public status: number) {
    super(code);
  }
}

export type Product = "museum" | "reactivate" | "room" | "slots";
export type PayMethod = "stars" | "card";

export interface Me {
  id: number;
  first_name: string;
  lang: string;
  is_free: boolean;
  slots: { used: number; total: number | null };
  bot_username: string;
}
export type Prices = Record<Product, { uzs: number; stars: number }>;
export interface Limits { rooms: number; images: number; videos: number }
export interface MediaOut {
  id: number;
  kind: "image" | "video";
  url: string;
  thumb_url: string;
  caption: string | null;
  taken_on: string | null;
  position: number;
}
export interface MuseumSettings {
  title: string;
  recipient_name: string | null;
  theme: string;
  mascot: string;
  opening_style: string;
  letter_text: string | null;
  music_id: string | null;
  music_url: string | null;
  voice_url: string | null;
  open_at: string | null;
  rooms: number;
}
export interface MuseumSummary {
  id: number;
  slug: string;
  title: string;
  status: "draft" | "active" | "expired";
  template: string | null;
  expires_at: string | null;
  cover_thumb: string | null;
  counts: { image: number; video: number };
  limits: Limits;
}
export interface MuseumFull extends MuseumSummary, MuseumSettings {
  paid_at: string | null;
  locked: boolean;
  media: MediaOut[];
}
export interface OrderOut {
  code: string;
  status: "pending" | "awaiting_review" | "paid" | "rejected" | "cancelled" | "refunded";
  product: Product;
  method: PayMethod | "free";
  museum_id: number | null;
  amount_uzs: number;
  amount_stars: number;
  reject_reason: string | null;
  invoice_link?: string;
  cards?: { number: string; holder: string }[];
  comment?: string;
}
export type PublicMuseum =
  | { state: "expired" }
  | { state: "locked"; open_at: string; opening_style: string; recipient_name: string | null; title: string }
  | ({ state: "open" | "draft"; slug: string; media: MediaOut[] } & MuseumSettings);
export interface ImportBody {
  settings: Partial<Omit<MuseumSettings, "music_url" | "voice_url" | "rooms" | "recipient_name">> & {
    recipient_name?: string;
  };
  media: { token: string; caption?: string; taken_on?: string }[];
  voice_token?: string;
  music_token?: string;
}

function headers(json: boolean): Record<string, string> {
  const h: Record<string, string> = { "X-Telegram-Init-Data": tg.initData() };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: init.method ?? "GET",
      headers: headers(init.body !== undefined),
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError("network", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data?.error ?? "unknown", response.status);
  return data as T;
}

/** multipart upload with progress (fetch cannot report upload progress) */
function upload<T>(path: string, form: FormData, onProgress?: (p: number) => void, method = "POST"): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, `${BASE}${path}`);
    for (const [k, v] of Object.entries(headers(false))) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let data: any = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* empty body */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
      else reject(new ApiError(data?.error ?? "unknown", xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("network", 0));
    xhr.send(form);
  });
}

function fileForm(file: File, fields: Record<string, string | undefined> = {}): FormData {
  const form = new FormData();
  form.append("file", file, file.name);
  for (const [k, v] of Object.entries(fields)) if (v !== undefined && v !== "") form.append(k, v);
  return form;
}

export const api = {
  getMe: () => request<Me>("/api/me"),
  getPrices: () => request<Prices>("/api/prices"),
  listMuseums: () => request<MuseumSummary[]>("/api/museums"),
  getMuseum: (id: number) => request<MuseumFull>(`/api/museums/${id}`),
  patchMuseum: (id: number, changes: Record<string, unknown>) =>
    request<MuseumFull>(`/api/museums/${id}`, { method: "PATCH", body: changes }),
  deleteMuseum: (id: number) => request<{ ok: true }>(`/api/museums/${id}`, { method: "DELETE" }),
  uploadServerMedia: (id: number, file: File, meta: { caption?: string; taken_on?: string }, onProgress?: (p: number) => void) =>
    upload<MediaOut>(`/api/museums/${id}/media`, fileForm(file, meta), onProgress),
  deleteServerMedia: (id: number, mediaId: number) =>
    request<{ ok: true }>(`/api/museums/${id}/media/${mediaId}`, { method: "DELETE" }),
  importMuseum: (body: ImportBody) => request<MuseumFull>("/api/museums/import", { method: "POST", body }),
  createOrder: (product: Product, museumId: number | null, method: PayMethod) =>
    request<OrderOut>("/api/orders", { method: "POST", body: { product, museum_id: museumId, method } }),
  getOrder: (code: string) => request<OrderOut>(`/api/orders/${code}`),
  uploadReceipt: (code: string, file: File, onProgress?: (p: number) => void) =>
    upload<OrderOut>(`/api/orders/${code}/receipt`, fileForm(file), onProgress),
  createTransfer: (id: number) => request<{ link: string; expires_at: string }>(`/api/museums/${id}/transfer`, { method: "POST" }),
  cancelTransfer: (id: number) => request<{ ok: true }>(`/api/museums/${id}/transfer`, { method: "DELETE" }),
  publicMuseum: (slug: string) => request<PublicMuseum>(`/api/public/m/${encodeURIComponent(slug)}`),
  uploadTgMedia: (file: File, purpose: "media" | "voice" | "music", onProgress?: (p: number) => void) =>
    upload<{ token: string; kind: "image" | "video" | "audio" }>("/api/tg-media", fileForm(file, { purpose }), onProgress),
  tgMediaUrl: (token: string) => `${BASE}/api/tg-media/${token}`,
};
