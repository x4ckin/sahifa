import { createRouter, createWebHashHistory, type RouteRecordRaw } from "vue-router";

export const routes: RouteRecordRaw[] = [
  { path: "/", name: "home", component: () => import("./views/Home.vue") },
  { path: "/new/:id/media", name: "new-media", component: () => import("./views/NewMedia.vue") },
  { path: "/new/:id/decor", name: "new-decor", component: () => import("./views/NewDecor.vue") },
  { path: "/new/:id/review", name: "new-review", component: () => import("./views/NewReview.vue") },
  { path: "/gift/:id", name: "gift", component: () => import("./views/Gift.vue") },
  { path: "/order/:code", name: "order", component: () => import("./views/Order.vue") },
  { path: "/done/:id", name: "done", component: () => import("./views/Done.vue") },
  { path: "/museum/:id", name: "museum", component: () => import("./views/ServerMuseum.vue") },
  { path: "/local/:id", name: "local", component: () => import("./views/LocalMuseum.vue") },
  { path: "/m/:slug", name: "viewer", component: () => import("./views/Viewer.vue") },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

/** Telegram start_param → first screen (e.g. "m_<slug>" opens that gift). */
export function initialPath(startParam: string | null): string | null {
  const match = /^m_([A-Za-z0-9_-]{1,62})$/.exec(startParam ?? "");
  return match ? `/m/${match[1]}` : null;
}

export function makeRouter() {
  return createRouter({ history: createWebHashHistory(), routes });
}
