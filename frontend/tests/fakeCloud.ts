/**
 * A CloudStorage that behaves like Telegram's: key format, 4096-byte values, 1024 keys,
 * callbacks after a delay. Two instances can share one `store` to play two devices.
 */
type Cb<T> = (error: unknown, result?: T) => void;

export interface FakeCloud {
  store: Map<string, string>;
  install(): void;
  setFailOn(predicate: ((key: string) => boolean) | null): void;
}

const KEY = /^[A-Za-z0-9_-]{1,128}$/;
const bytes = (s: string) => new TextEncoder().encode(s).length;

export function makeFakeCloud(store = new Map<string, string>(), delayMs = 2): FakeCloud {
  let failOn: ((key: string) => boolean) | null = null;
  const later = (fn: () => void) => setTimeout(fn, delayMs);
  const api = {
    setItem(key: string, value: string, cb: Cb<boolean>) {
      later(() => {
        if (!KEY.test(key)) return cb("KEY_INVALID");
        if (bytes(value) > 4096) return cb("VALUE_TOO_LONG");
        if (!store.has(key) && store.size >= 1024) return cb("STORAGE_KEY_CLOUD_LIMIT");
        if (failOn?.(key)) return cb("NETWORK");
        store.set(key, value);
        cb(null, true);
      });
    },
    getItems(keys: string[], cb: Cb<Record<string, string>>) {
      later(() => cb(null, Object.fromEntries(keys.map((k) => [k, store.get(k) ?? ""]))));
    },
    removeItems(keys: string[], cb: Cb<boolean>) {
      later(() => {
        keys.forEach((k) => store.delete(k));
        cb(null, true);
      });
    },
    getKeys(cb: Cb<string[]>) {
      later(() => cb(null, [...store.keys()]));
    },
  };
  return {
    store,
    install() {
      (window as any).Telegram = {
        WebApp: { initData: "x=1&hash=y", initDataUnsafe: {}, isVersionAtLeast: () => true, CloudStorage: api },
      };
    },
    setFailOn(p) {
      failOn = p;
    },
  };
}
