<script setup lang="ts">
/** What a gift recipient sees (2D for now; the 3D museum and opening effects come with plan 3). */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

import { api, ApiError, type PublicMuseum } from "../api";

const { t } = useI18n();
const route = useRoute();
const slug = String(route.params.slug);
const gift = ref<PublicMuseum | null>(null);
const missing = ref(false);
const error = ref(false);
const now = ref(Date.now());
let ticker: ReturnType<typeof setInterval> | undefined;

onMounted(async () => {
  try {
    gift.value = await api.publicMuseum(slug);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) missing.value = true;
    else error.value = true;
  }
  if (gift.value?.state === "locked") ticker = setInterval(() => (now.value = Date.now()), 1000);
});
onBeforeUnmount(() => clearInterval(ticker));

const open = computed(() => (gift.value && (gift.value.state === "open" || gift.value.state === "draft") ? gift.value : null));
const locked = computed(() => (gift.value?.state === "locked" ? gift.value : null));
const countdown = computed(() => {
  if (!locked.value) return "";
  let left = Math.max(0, Math.floor((new Date(locked.value.open_at).getTime() - now.value) / 1000));
  const d = Math.floor(left / 86400);
  left %= 86400;
  const h = Math.floor(left / 3600);
  left %= 3600;
  return t("viewer.countdown", { d, h, m: Math.floor(left / 60), s: left % 60 });
});
const bot = import.meta.env.VITE_BOT_USERNAME ?? "";
const audioSrc = computed(() => open.value?.voice_url ?? open.value?.music_url ?? null);
</script>

<template>
  <main class="page viewer">
    <p v-if="!gift && !missing && !error" class="muted">{{ t("common.loading") }}</p>
    <p v-if="missing" class="center">{{ t("viewer.not_found") }}</p>
    <p v-if="error" class="error">{{ t("errors.network") }}</p>
    <p v-if="gift?.state === 'expired'" class="center">{{ t("viewer.expired") }}</p>

    <section v-if="locked" class="door locked">
      <h1>{{ locked.title }}</h1>
      <p v-if="locked.recipient_name">{{ t("viewer.for", { name: locked.recipient_name }) }}</p>
      <p class="muted">{{ t("viewer.opens_in") }}</p>
      <p class="count" data-countdown>{{ countdown }}</p>
    </section>

    <template v-if="open">
      <section class="door">
        <h1>{{ open.title }}</h1>
        <p v-if="open.recipient_name">{{ t("viewer.for", { name: open.recipient_name }) }}</p>
      </section>
      <audio v-if="audioSrc" :src="audioSrc" controls preload="none" />
      <p v-if="open.letter_text" class="letter">{{ open.letter_text }}</p>
      <div class="gallery">
        <figure v-for="item in open.media" :key="item.id">
          <img v-if="item.kind === 'image'" :src="item.url" loading="lazy" alt="" />
          <video v-else :src="item.url" :poster="item.thumb_url" controls playsinline preload="none" />
          <figcaption v-if="item.caption || item.taken_on">
            {{ item.caption }}<small v-if="item.taken_on"> · {{ item.taken_on }}</small>
          </figcaption>
        </figure>
      </div>
    </template>

    <a v-if="gift || missing" class="btn primary block own" data-create-own :href="`https://t.me/${bot}`" target="_blank" rel="noopener">
      🎁 {{ t("viewer.create_own") }}
    </a>
  </main>
</template>

<style scoped>
.center { text-align: center; margin-top: 30px; }
.door { text-align: center; padding: 22px 16px; border-radius: 18px; background: linear-gradient(#f3eee6 62%, #d9cbb6 62%); color: #5a4a3a; }
.door h1 { margin: 0; font-style: italic; font-size: 26px; }
.door p { margin: 6px 0 0; }
.locked { background: radial-gradient(ellipse at 50% 120%, #2a3a6e, #070914 70%); color: #fff; }
.locked .muted { color: #b8c7ee; }
.count { font-size: 20px; font-weight: 800; }
.letter { white-space: pre-wrap; font-family: Fraunces, Georgia, serif; font-style: italic; line-height: 1.55; }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
figure { margin: 0; background: var(--card); border: 6px solid #9c7446; border-radius: 4px; box-shadow: 0 6px 14px #0002; }
figure img, figure video { width: 100%; display: block; aspect-ratio: 4/5; object-fit: cover; background: #ddd; }
figcaption { font-size: 12px; padding: 5px 7px; color: var(--muted); }
audio { width: 100%; }
.own { text-align: center; text-decoration: none; }
</style>
