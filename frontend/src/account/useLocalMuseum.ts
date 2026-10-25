import { onBeforeUnmount, ref } from "vue";

import { errorText } from "../i18n";
import { loadMuseum, saveMuseum, type LocalMuseum } from "./store";

const SAVE_DEBOUNCE_MS = 600;

/** Load a free museum and save it shortly after every change (and when the screen closes). */
export function useLocalMuseum(id: string) {
  const museum = ref<LocalMuseum | null>(null);
  const loading = ref(true);
  const error = ref("");
  let timer: ReturnType<typeof setTimeout> | undefined;

  const ready = loadMuseum(id)
    .then((m) => (museum.value = m))
    .catch(() => (error.value = errorText("unknown")))
    .finally(() => (loading.value = false));

  async function flush(): Promise<void> {
    clearTimeout(timer);
    timer = undefined;
    const current = museum.value;
    if (!current || current.broken) return;
    try {
      await saveMuseum(JSON.parse(JSON.stringify(current)) as LocalMuseum);
      error.value = "";
    } catch (e) {
      error.value = errorText(e instanceof Error ? e.message : "unknown");
    }
  }

  /** Save now and throw on failure — for steps that must not continue without a stored state. */
  async function save(): Promise<void> {
    clearTimeout(timer);
    timer = undefined;
    if (!museum.value || museum.value.broken) throw new Error("broken");
    await saveMuseum(JSON.parse(JSON.stringify(museum.value)) as LocalMuseum);
  }

  function changed(): void {
    clearTimeout(timer);
    timer = setTimeout(() => void flush(), SAVE_DEBOUNCE_MS);
  }

  onBeforeUnmount(() => {
    if (timer !== undefined) void flush();
  });

  return { museum, loading, error, ready, changed, flush, save };
}
