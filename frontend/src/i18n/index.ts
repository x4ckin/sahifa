import { createI18n } from "vue-i18n";

import ru from "./ru";
import uz from "./uz";

export type Locale = "uz" | "ru";

export function pickLocale(languageCode: string | undefined): Locale {
  return languageCode === "ru" ? "ru" : "uz";
}

export const i18n = createI18n({
  legacy: false,
  locale: "uz",
  fallbackLocale: "uz",
  messages: { uz, ru },
});

export function setupI18n(languageCode?: string) {
  i18n.global.locale.value = pickLocale(languageCode);
  return i18n;
}

/** Backend error code → message in the current language. */
export function errorText(code: string): string {
  const key = `errors.${code}`;
  return i18n.global.te(key) ? i18n.global.t(key) : i18n.global.t("errors.unknown");
}
