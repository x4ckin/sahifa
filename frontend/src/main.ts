import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { setupI18n } from "./i18n";
import { makeRouter } from "./router";
import "./styles.css";
import { tg } from "./telegram";

tg.ready();
const scheme = tg.colorScheme();
if (scheme) document.documentElement.dataset.theme = scheme;

createApp(App)
  .use(createPinia())
  .use(setupI18n(tg.user()?.language_code))
  .use(makeRouter())
  .mount("#app");
