import { createRouter, createWebHashHistory, type RouteRecordRaw } from "vue-router";

export const routes: RouteRecordRaw[] = [
  { path: "/", name: "home", component: () => import("./views/Home.vue") },
];

export function makeRouter() {
  return createRouter({ history: createWebHashHistory(), routes });
}
