<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { tg } from "./telegram";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const inTelegram = tg.available();
let cleanup = () => {};

function goBack() {
  if (window.history.length > 1) router.back();
  else void router.push("/");
}

// every screen but home gets Telegram's own back button (Android's hardware back follows it)
watch(
  () => route.path,
  (path) => {
    cleanup();
    cleanup = path === "/" ? () => {} : tg.backButton(goBack);
  },
  { immediate: true },
);
onBeforeUnmount(() => cleanup());
</script>

<template>
  <div data-app>
    <button v-if="!inTelegram && route.path !== '/'" class="back" data-back @click="goBack">← {{ t("common.back") }}</button>
    <RouterView />
  </div>
</template>

<style scoped>
.back { border: 0; background: none; color: var(--muted); font-weight: 700; padding: 12px 16px 0; cursor: pointer; }
</style>
