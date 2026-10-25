<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api, ApiError, type MuseumFull } from "../api";
import QrCard from "../components/QrCard.vue";
import { errorText } from "../i18n";
import { tg } from "../telegram";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);
const museum = ref<MuseumFull | null>(null);
const bot = ref(import.meta.env.VITE_BOT_USERNAME ?? "");
const error = ref("");
const copied = ref(false);

onMounted(async () => {
  try {
    const [m, me] = await Promise.all([api.getMuseum(id), api.getMe()]);
    museum.value = m;
    bot.value = me.bot_username || bot.value;
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  }
});

/** The gift link: opens the museum through the bot (works without a registered Mini App short name). */
const link = computed(() => (museum.value && bot.value ? `https://t.me/${bot.value}?start=m_${museum.value.slug}` : ""));

async function copy() {
  await navigator.clipboard?.writeText(link.value).catch(() => undefined);
  copied.value = true;
}
</script>

<template>
  <main class="page done">
    <div class="party">🎉</div>
    <h2>{{ t("done.title") }}</h2>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="link">
      <QrCard :link="link" />
      <button class="link" data-link @click="copy">{{ link }}</button>
      <small v-if="copied" class="muted">{{ t("common.copied") }}</small>
      <div class="row">
        <button class="btn primary grow" @click="tg.share(link, t('done.share_text'))">{{ t("done.send") }}</button>
        <button class="btn grow" @click="router.push(`/m/${museum?.slug}`)">{{ t("done.open") }}</button>
      </div>
      <button class="btn block" @click="router.push(`/museum/${id}`)">{{ t("home.mine") }}</button>
    </template>
  </main>
</template>

<style scoped>
.done { align-items: center; text-align: center; }
.party { font-size: 40px; }
h2 { margin: 0; }
.link { font-family: ui-monospace, monospace; font-size: 13px; background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 9px 10px; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.row { width: 100%; }
.grow { flex: 1; }
</style>
