<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api, ApiError, type MuseumFull, type PayMethod, type Prices } from "../api";
import { MASCOTS, OPENINGS, THEMES } from "../catalog";
import ConfirmButton from "../components/ConfirmButton.vue";
import QrCard from "../components/QrCard.vue";
import { money, shortDate } from "../format";
import { errorText } from "../i18n";
import { payForProduct } from "../payment";
import { tg } from "../telegram";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = Number(route.params.id);

const museum = ref<MuseumFull | null>(null);
const prices = ref<Prices | null>(null);
const bot = ref(import.meta.env.VITE_BOT_USERNAME ?? "");
const error = ref("");
const busy = ref(false);
const method = ref<PayMethod>("stars");
const transferLink = ref("");
const uploading = ref<string>("");

async function load() {
  try {
    const [m, me, p] = await Promise.all([api.getMuseum(id), api.getMe(), api.getPrices()]);
    museum.value = m;
    bot.value = me.bot_username || bot.value;
    prices.value = p;
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  }
}
onMounted(load);

const giftLink = computed(() => (museum.value && bot.value ? `https://t.me/${bot.value}?start=m_${museum.value.slug}` : ""));
const statusText = computed(() => {
  const m = museum.value;
  if (!m) return "";
  if (m.status === "active" && m.expires_at) return t("museum.status_active", { date: shortDate(m.expires_at) });
  return m.status === "expired" ? t("museum.status_expired") : t("museum.status_draft");
});
const label = (items: readonly { key: string; i18nKey: string }[], key: string | null | undefined) => {
  const item = items.find((x) => x.key === key);
  return item ? t(item.i18nKey) : "—";
};
const imageCount = computed(() => museum.value?.media.filter((m) => m.kind === "image").length ?? 0);
const videoCount = computed(() => (museum.value?.media.length ?? 0) - imageCount.value);

async function run(task: () => Promise<void>) {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await task();
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  } finally {
    busy.value = false;
  }
}

function buy(product: "room" | "reactivate") {
  return run(async () => {
    const outcome = await payForProduct(product, id, method.value);
    if (outcome.kind === "card") await router.push(`/order/${outcome.code}`);
    else if (outcome.kind === "paid") {
      tg.haptic("success");
      await load();
    }
  });
}

async function addMedia(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";
  await run(async () => {
    for (const [n, file] of files.entries()) {
      uploading.value = `${n + 1}/${files.length}`;
      await api.uploadServerMedia(id, file, {});
    }
    uploading.value = "";
    await load();
  });
  uploading.value = "";
}

function removeMedia(mediaId: number) {
  return run(async () => {
    await api.deleteServerMedia(id, mediaId);
    await load();
  });
}

function startTransfer() {
  return run(async () => {
    transferLink.value = (await api.createTransfer(id)).link;
  });
}

function cancelTransfer() {
  return run(async () => {
    await api.cancelTransfer(id);
    transferLink.value = "";
  });
}

function remove() {
  return run(async () => {
    await api.deleteMuseum(id);
    await router.push("/");
  });
}
</script>

<template>
  <main class="page">
    <p v-if="!museum && !error" class="muted">{{ t("common.loading") }}</p>
    <template v-if="museum">
      <h2>{{ museum.title }}</h2>
      <p class="muted">{{ statusText }}</p>

      <template v-if="museum.status === 'active' && giftLink">
        <QrCard :link="giftLink" />
        <div class="row">
          <button class="btn primary grow" @click="tg.share(giftLink, t('done.share_text'))">{{ t("done.send") }}</button>
          <button class="btn grow" @click="router.push(`/m/${museum.slug}`)">{{ t("done.open") }}</button>
        </div>
      </template>

      <section class="card settings">
        <p class="note">{{ t("museum.locked_note") }}</p>
        <div><span class="muted">{{ t("create.recipient") }}</span> {{ museum.recipient_name || "—" }}</div>
        <div><span class="muted">{{ t("create.theme") }}</span> {{ label(THEMES, museum.theme) }}</div>
        <div><span class="muted">{{ t("create.opening") }}</span> {{ label(OPENINGS, museum.opening_style) }}</div>
        <div><span class="muted">{{ t("create.mascot") }}</span> {{ label(MASCOTS, museum.mascot) }}</div>
      </section>

      <div class="h3">
        {{ t("create.step_media") }}
        <small>📷 {{ imageCount }}/{{ museum.limits.images }} · 🎬 {{ videoCount }}/{{ museum.limits.videos }}</small>
      </div>
      <div class="grid">
        <div v-for="item in museum.media" :key="item.id" class="tile">
          <img :src="item.thumb_url" loading="lazy" alt="" />
          <button class="x" :aria-label="t('common.delete')" @click="removeMedia(item.id)">✕</button>
        </div>
      </div>
      <label class="btn block center">
        {{ uploading ? `${t("common.loading")} ${uploading}` : t("museum.add_media") }}
        <input type="file" accept="image/*,video/*" multiple hidden :disabled="busy" @change="addMedia" />
      </label>

      <div class="row methods">
        <button class="btn grow" :class="{ primary: method === 'stars' }" @click="method = 'stars'">⭐ Stars</button>
        <button class="btn grow" :class="{ primary: method === 'card' }" @click="method = 'card'">💳 {{ t("gift.card") }}</button>
      </div>
      <button v-if="museum.status === 'active'" class="btn block" :disabled="busy" @click="buy('room')">
        {{ t("museum.add_room", { price: money(prices?.room.uzs ?? 3000) }) }}
      </button>
      <button class="btn block" :disabled="busy" @click="buy('reactivate')">
        {{ t("museum.reactivate") }} — {{ money(prices?.reactivate.uzs ?? 15000) }} {{ t("common.som") }}
      </button>

      <section class="card">
        <button v-if="!transferLink" class="btn block" data-transfer :disabled="busy" @click="startTransfer">
          {{ t("museum.transfer") }}
        </button>
        <template v-else>
          <p class="muted">{{ t("museum.transfer_note") }}</p>
          <button class="link" data-transfer-link @click="tg.share(transferLink, museum.title)">{{ transferLink }}</button>
          <button class="btn block" data-transfer-cancel :disabled="busy" @click="cancelTransfer">{{ t("museum.transfer_cancel") }}</button>
        </template>
      </section>

      <ConfirmButton :label="t('common.delete')" @confirm="remove" />
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </main>
</template>

<style scoped>
.settings div { padding: 3px 0; display: flex; justify-content: space-between; gap: 8px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.tile { position: relative; aspect-ratio: 1; border-radius: 10px; overflow: hidden; background: var(--line); }
.tile img { width: 100%; height: 100%; object-fit: cover; }
.x { position: absolute; right: 3px; top: 3px; border: 0; border-radius: 50%; width: 22px; height: 22px; background: #0007; color: #fff; cursor: pointer; }
.center { text-align: center; }
.grow { flex: 1; }
.link { font-family: ui-monospace, monospace; font-size: 12px; background: var(--paper); border: 1px dashed var(--line); border-radius: 10px; padding: 9px; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: 8px; cursor: pointer; }
</style>
