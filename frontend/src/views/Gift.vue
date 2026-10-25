<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { roomsNeeded } from "../account/rooms";
import type { LocalMuseum } from "../account/store";
import { useLocalMuseum } from "../account/useLocalMuseum";
import { api, ApiError, type ImportBody, type PayMethod, type Prices } from "../api";
import MainAction from "../components/MainAction.vue";
import { money } from "../format";
import { errorText } from "../i18n";
import { waitForOrder } from "../payment";
import { tg } from "../telegram";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = String(route.params.id);
const { museum, loading, flush } = useLocalMuseum(id);

const prices = ref<Prices | null>(null);
const method = ref<PayMethod>("stars");
const busy = ref("");
const error = ref("");

onMounted(async () => {
  try {
    prices.value = await api.getPrices();
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  }
});

const rooms = computed(() => {
  const media = museum.value?.media ?? [];
  const images = media.filter((m) => m.k === "image").length;
  try {
    return roomsNeeded(images, media.length - images);
  } catch {
    return 10;
  }
});
const totalUzs = computed(() => (prices.value ? prices.value.museum.uzs + rooms.value * prices.value.room.uzs : 0));
const totalStars = computed(() => (prices.value ? prices.value.museum.stars + rooms.value * prices.value.room.stars : 0));

function importBody(m: LocalMuseum): ImportBody {
  return {
    settings: {
      title: m.title,
      recipient_name: m.recipient || undefined,
      theme: m.theme,
      mascot: m.mascot,
      opening_style: m.opening,
      letter_text: m.letter || undefined,
      music_id: m.music_id,
      open_at: m.open_at && new Date(m.open_at).getTime() > Date.now() ? m.open_at : undefined,
    },
    media: m.media.map((x) => ({ token: x.t, caption: x.c || undefined, taken_on: x.d || undefined })),
    voice_token: m.voice,
    music_token: m.music,
  };
}

async function markPaid(serverId: number) {
  if (!museum.value) return;
  museum.value.gift = { draft: serverId, state: "paid" };
  await flush();
  tg.haptic("success");
  await router.push(`/done/${serverId}`);
}

async function pay() {
  const m = museum.value;
  if (!m || busy.value) return;
  if (m.gift?.state === "paid") {
    await router.push(`/museum/${m.gift.draft}`);
    return;
  }
  error.value = "";
  busy.value = t("gift.preparing");
  try {
    if (m.gift?.state === "draft") {
      // an earlier, unpaid attempt: start clean so only one payment can ever be open
      await api.deleteMuseum(m.gift.draft).catch((e) => {
        if (!(e instanceof ApiError && e.status === 404)) throw e;
      });
      m.gift = undefined;
    }
    const draft = await api.importMuseum(importBody(m));
    m.gift = { draft: draft.id, state: "draft" };
    await flush();

    const order = await api.createOrder("museum", draft.id, method.value);
    if (order.status === "paid") return await markPaid(draft.id); // free users
    if (method.value === "card" || !order.invoice_link) {
      await router.push(`/order/${order.code}?local=${id}`);
      return;
    }
    const status = await tg.openInvoice(order.invoice_link);
    if (status === "cancelled" || status === "failed") return;
    busy.value = t("gift.waiting");
    const final = await waitForOrder(order.code);
    if (final.status === "paid") await markPaid(draft.id);
    else error.value = errorText(final.status === "pending" ? "telegram_unavailable" : "unknown");
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  } finally {
    busy.value = "";
  }
}
</script>

<template>
  <main class="page">
    <h2>{{ t("gift.title") }}</h2>
    <p v-if="loading" class="muted">{{ t("common.loading") }}</p>
    <template v-else-if="museum">
      <section class="sum card">
        <div><span>{{ t("gift.museum_line") }}</span><span>{{ money(prices?.museum.uzs ?? 0) }}</span></div>
        <div v-if="rooms > 0">
          <span>{{ t("gift.rooms_line", { n: rooms }) }}</span><span>{{ money(rooms * (prices?.room.uzs ?? 0)) }}</span>
        </div>
        <div class="tot" data-total><span>{{ t("gift.total") }}</span><span>{{ money(totalUzs) }} {{ t("common.som") }}</span></div>
      </section>

      <button class="pay" :class="{ sel: method === 'stars' }" data-method="stars" @click="method = 'stars'">
        <i>⭐</i>
        <span>{{ t("gift.stars") }}<small>{{ t("gift.stars_hint", { n: totalStars }) }}</small></span>
      </button>
      <button class="pay" :class="{ sel: method === 'card' }" data-method="card" @click="method = 'card'">
        <i>💳</i>
        <span>{{ t("gift.card") }}<small>{{ t("gift.card_hint") }}</small></span>
      </button>

      <p class="note">{{ t("gift.note") }}</p>
      <p v-if="busy" class="muted">{{ busy }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn primary block" data-pay :disabled="!!busy || !prices" @click="pay">
        {{ method === "stars" ? t("gift.pay_stars", { n: totalStars }) : t("gift.pay_card") }}
      </button>
      <MainAction
        :text="method === 'stars' ? t('gift.pay_stars', { n: totalStars }) : t('gift.pay_card')"
        :disabled="!!busy || !prices"
        @click="pay"
      />
    </template>
  </main>
</template>

<style scoped>
.sum div { display: flex; justify-content: space-between; padding: 3px 0; font-size: 15px; }
.sum .tot { border-top: 1px dashed var(--line); margin-top: 6px; padding-top: 8px; font-weight: 800; font-size: 17px; }
.pay { display: flex; gap: 12px; align-items: center; text-align: left; background: var(--card); border: 2px solid var(--line); border-radius: 14px; padding: 12px; font-weight: 800; cursor: pointer; }
.pay.sel { border-color: var(--rose); }
.pay i { font-style: normal; font-size: 26px; }
.pay small { display: block; color: var(--muted); font-weight: 600; }
</style>
