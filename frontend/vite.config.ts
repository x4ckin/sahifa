/// <reference types="vitest/config" />
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  // GitHub Pages serves the app under /<repo>/; relative paths also work from a plain folder
  base: process.env.VITE_BASE ?? "./",
  plugins: [vue()],
  build: { target: "es2020", sourcemap: false },
  test: { environment: "happy-dom", include: ["tests/**/*.spec.ts"] },
});
