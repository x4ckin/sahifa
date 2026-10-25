import { createRouter, createWebHashHistory, type RouteRecordRaw } from "vue-router";

export const routes: RouteRecordRaw[] = [
  { path: "/", name: "home", component: () => import("./views/Home.vue") },
  { path: "/new/:id/media", name: "new-media", component: () => import("./views/NewMedia.vue") },
  { path: "/new/:id/decor", name: "new-decor", component: () => import("./views/NewDecor.vue") },
  { path: "/new/:id/review", name: "new-review", component: () => import("./views/NewReview.vue") },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

export function makeRouter() {
  return createRouter({ history: createWebHashHistory(), routes });
}
