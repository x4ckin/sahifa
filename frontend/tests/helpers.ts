import { flushPromises, mount } from "@vue/test-utils";
import type { Component } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";

import { setupI18n } from "../src/i18n";

const Stub = { template: "<div />" };

/** Mount a view with i18n and a router that knows every app route (as stubs). */
export async function mountView(component: Component, path = "/", routePath = "/") {
  const router = createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: routePath, component },
      { path: "/:pathMatch(.*)*", component: Stub },
    ],
  });
  await router.push(path);
  const wrapper = mount({ template: "<RouterView />" }, { global: { plugins: [setupI18n("uz"), router] } });
  await flushPromises();
  return { wrapper, router };
}
