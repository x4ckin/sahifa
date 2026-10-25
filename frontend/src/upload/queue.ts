import { ref, type Ref } from "vue";

import { ApiError } from "../api";

export interface UploadResult {
  token: string;
  kind: string;
}

export interface QueueItem {
  id: string;
  file: File;
  state: "waiting" | "uploading" | "done" | "error";
  progress: number;
  error?: string;
  result?: UploadResult;
  delivered?: boolean;
}

type Send = (file: File, onProgress: (p: number) => void) => Promise<UploadResult>;

/**
 * Uploads files with limited parallelism. A failed file never stops the others; it can be retried.
 * `onDone` sees finished files in the order they were added, so the gallery keeps the user's order.
 */
export function createQueue(send: Send, concurrency = 2, onDone?: (item: QueueItem) => void) {
  const items: Ref<QueueItem[]> = ref([]);
  let counter = 0;
  let waiters: (() => void)[] = [];

  const busy = () => items.value.some((i) => i.state === "waiting" || i.state === "uploading");

  /** Hand finished items to onDone in add order; failed items never block the ones after them. */
  function deliver() {
    for (const item of items.value) {
      if (item.state === "waiting" || item.state === "uploading") break;
      if (item.state === "done" && !item.delivered) {
        item.delivered = true;
        onDone?.(item);
      }
    }
  }

  function pump() {
    const running = items.value.filter((i) => i.state === "uploading").length;
    const next = items.value.filter((i) => i.state === "waiting").slice(0, Math.max(concurrency - running, 0));
    for (const item of next) void run(item);
    if (!busy()) {
      const done = waiters;
      waiters = [];
      done.forEach((resolve) => resolve());
    }
  }

  async function run(item: QueueItem) {
    item.state = "uploading";
    item.progress = 0;
    try {
      item.result = await send(item.file, (p) => (item.progress = p));
      item.state = "done";
      item.progress = 1;
    } catch (e) {
      item.state = "error";
      item.error = e instanceof ApiError ? e.code : "unknown";
    }
    deliver();
    pump();
  }

  return {
    items,
    add(files: File[]) {
      for (const file of files) {
        items.value.push({ id: `u${++counter}`, file, state: "waiting", progress: 0 });
      }
      pump();
    },
    retry(id: string) {
      const item = items.value.find((i) => i.id === id);
      if (item?.state !== "error") return;
      item.state = "waiting";
      item.error = undefined;
      pump();
    },
    remove(id: string) {
      items.value = items.value.filter((i) => i.id !== id || i.state === "uploading");
      deliver();
      pump();
    },
    /** Resolves when nothing is waiting or uploading. */
    idle(): Promise<void> {
      if (!busy()) return Promise.resolve();
      return new Promise((resolve) => waiters.push(resolve));
    },
  };
}
