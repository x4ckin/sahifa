import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { setupI18n } from "./i18n";
import { initialPath, makeRouter } from "./router";
import "./styles.css";
import { tg } from "./telegram";

tg.ready();
const scheme = tg.colorScheme();
if (scheme) document.documentElement.dataset.theme = scheme;

const router = makeRouter();
const start = initialPath(tg.startParam());
if (start && (location.hash === "" || location.hash === "#/")) void router.replace(start);

createApp(App)
  .use(createPinia())
  .use(setupI18n(tg.user()?.language_code))
  .use(router)
  .mount("#app");
