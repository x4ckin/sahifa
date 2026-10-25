/**
 * The only module that talks to the Telegram WebApp SDK.
 * Every call works without the SDK too (a gift link opened in a normal browser).
 */

type Callback<T> = (error: unknown, result?: T) => void;

interface WebApp {
  initData: string;
  initDataUnsafe: { user?: TgUser; start_param?: string };
  colorScheme?: "light" | "dark";
  ready?: () => void;
  expand?: () => void;
  MainButton?: {
    setText(text: string): WebApp["MainButton"];
    show(): WebApp["MainButton"];
    hide(): WebApp["MainButton"];
    onClick(fn: () => void): void;
    offClick(fn: () => void): void;
  };
  BackButton?: { show(): void; hide(): void; onClick(fn: () => void): void; offClick(fn: () => void): void };
  HapticFeedback?: {
    impactOccurred(style: "light" | "medium"): void;
    notificationOccurred(type: "success" | "error" | "warning"): void;
  };
  CloudStorage?: {
    setItem(key: string, value: string, cb: Callback<boolean>): void;
    getItems(keys: string[], cb: Callback<Record<string, string>>): void;
    removeItems(keys: string[], cb: Callback<boolean>): void;
    getKeys(cb: Callback<string[]>): void;
  };
  openInvoice?: (url: string, cb: (status: InvoiceStatus) => void) => void;
  openTelegramLink?: (url: string) => void;
  openLink?: (url: string) => void;
  isVersionAtLeast?: (version: string) => boolean;
}

export interface TgUser {
  id: number;
  first_name: string;
  username?: string;
  language_code?: string;
}

export type InvoiceStatus = "paid" | "cancelled" | "failed" | "pending";

function wa(): WebApp | null {
  const app = (window as unknown as { Telegram?: { WebApp?: WebApp } }).Telegram?.WebApp;
  // the SDK script defines WebApp even in a browser; real Telegram always passes initData
  return app && app.initData ? app : null;
}

const noop = () => {};

export const tg = {
  available: (): boolean => wa() !== null,
  initData: (): string => wa()?.initData ?? "",
  user: (): TgUser | null => wa()?.initDataUnsafe.user ?? null,
  startParam: (): string | null => wa()?.initDataUnsafe.start_param ?? null,
  colorScheme: (): "light" | "dark" | null => wa()?.colorScheme ?? null,

  ready(): void {
    wa()?.ready?.();
    wa()?.expand?.();
  },

  haptic(kind: "light" | "success" | "error"): void {
    const h = wa()?.HapticFeedback;
    if (!h) return;
    if (kind === "light") h.impactOccurred("light");
    else h.notificationOccurred(kind);
  },

  /** Shows Telegram's bottom button; returns a cleanup. Without the SDK views render their own button. */
  mainButton(text: string, onClick: () => void): () => void {
    const button = wa()?.MainButton;
    if (!button) return noop;
    button.setText(text);
    button.show();
    button.onClick(onClick);
    return () => {
      button.offClick(onClick);
      button.hide();
    };
  },

  backButton(onClick: () => void): () => void {
    const button = wa()?.BackButton;
    if (!button) return noop;
    button.show();
    button.onClick(onClick);
    return () => {
      button.offClick(onClick);
      button.hide();
    };
  },

  openInvoice(url: string): Promise<InvoiceStatus> {
    const app = wa();
    if (!app?.openInvoice) return Promise.resolve("failed");
    return new Promise((resolve) => app.openInvoice!(url, resolve));
  },

  openTelegramLink(url: string): void {
    const app = wa();
    if (app?.openTelegramLink) app.openTelegramLink(url);
    else window.open(url, "_blank");
  },

  openLink(url: string): void {
    const app = wa();
    if (app?.openLink) app.openLink(url);
    else window.open(url, "_blank");
  },

  share(url: string, text: string): void {
    const share = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
    tg.openTelegramLink(share);
  },
};

const PREFIX = "sahifa:";

const CLOUD_TIMEOUT_MS = 10_000;

function viaSdk<T>(call: (cb: Callback<T>) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    // a callback that never comes (app backgrounded, request dropped) must not hang saves forever
    const timer = setTimeout(() => reject(new Error("timeout")), CLOUD_TIMEOUT_MS);
    const done = (error: unknown, result?: T) => {
      clearTimeout(timer);
      if (error) reject(new Error(String(error)));
      else resolve(result as T);
    };
    try {
      call(done);
    } catch (e) {
      done(e instanceof Error ? e.message : e);
    }
  });
}

/** CloudStorage needs Bot API 6.9; older clients expose the object but every call throws. */
function cloudStorage() {
  const app = wa();
  if (!app?.CloudStorage) return null;
  if (app.isVersionAtLeast && !app.isVersionAtLeast("6.9")) return null;
  return app.CloudStorage;
}

/** Telegram CloudStorage (per user, per bot); localStorage stands in outside Telegram. */
export const cloud = {
  async get(keys: string[]): Promise<Record<string, string>> {
    const storage = cloudStorage();
    if (storage) return viaSdk((cb) => storage.getItems(keys, cb));
    return Object.fromEntries(keys.map((k) => [k, localStorage.getItem(PREFIX + k) ?? ""]));
  },

  async set(key: string, value: string): Promise<void> {
    const storage = cloudStorage();
    if (storage) {
      await viaSdk<boolean>((cb) => storage.setItem(key, value, cb));
      return;
    }
    localStorage.setItem(PREFIX + key, value);
  },

  async remove(keys: string[]): Promise<void> {
    if (keys.length === 0) return;
    const storage = cloudStorage();
    if (storage) {
      await viaSdk<boolean>((cb) => storage.removeItems(keys, cb));
      return;
    }
    keys.forEach((k) => localStorage.removeItem(PREFIX + k));
  },

  async keys(): Promise<string[]> {
    const storage = cloudStorage();
    if (storage) return viaSdk((cb) => storage.getKeys(cb));
    return Object.keys(localStorage)
      .filter((k) => k.startsWith(PREFIX))
      .map((k) => k.slice(PREFIX.length));
  },
};
