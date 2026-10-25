<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { roomsNeeded } from "../account/rooms";
import type { LocalMuseum } from "../account/store";
import { useLocalMuseum } from "../account/useLocalMuseum";
import { api, ApiError, type ImportBody, type MuseumFull, type PayMethod, type Prices } from "../api";
import MainAction from "../components/MainAction.vue";
import { money } from "../format";
import { errorText } from "../i18n";
import { waitForOrder } from "../payment";
import { tg } from "../telegram";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = String(route.params.id);
const { museum, loading, save } = useLocalMuseum(id);

const prices = ref<Prices | null>(null);
const method = ref<PayMethod>("stars");
const busy = ref("");
const error = ref("");
let alive = true;
onBeforeUnmount(() => (alive = false));

onMounted(async () => {
  try {
    prices.value = await api.getPrices();
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  }
});

const rooms = computed<number | null>(() => {
  const media = museum.value?.media ?? [];
  const images = media.filter((m) => m.k === "image").length;
  try {
    return roomsNeeded(images, media.length - images);
  } catch {
    return null; // over the limit: the server would refuse the import
  }
});
const totalUzs = computed(() => (prices.value && rooms.value !== null ? prices.value.museum.uzs + rooms.value * prices.value.room.uzs : 0));
const totalStars = computed(() => (prices.value && rooms.value !== null ? prices.value.museum.stars + rooms.value * prices.value.room.stars : 0));

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

/** Small stable fingerprint of what would be imported: tells "same gift again" from "changed gift". */
function fingerprint(body: ImportBody): string {
  const text = JSON.stringify(body);
  let h = 5381;
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

async function markPaid(serverId: number) {
  const m = museum.value!;
  m.gift = { ...(m.gift ?? {}), draft: serverId, state: "paid" };
  try {
    await save();
  } catch {
    /* Home heals this from the server state; never block the user on it */
  }
  tg.haptic("success");
  if (alive) await router.push(`/done/${serverId}`);
}

async function serverCopy(draftId: number): Promise<MuseumFull | null> {
  try {
    return await api.getMuseum(draftId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** Reuse, resume or replace an earlier attempt. Returns the draft id to pay for, or null if handled. */
async function previousAttempt(m: LocalMuseum, hash: string): Promise<number | null | "fresh"> {
  if (!m.gift) return "fresh";
  const server = await serverCopy(m.gift.draft);
  if (!server) return "fresh";
  if (server.status !== "draft") {
    await markPaid(server.id); // paid earlier but the app closed before it could remember
    return null;
  }
  const order = m.gift.order ? await api.getOrder(m.gift.order).catch(() => null) : null;
  if (order?.status === "paid") {
    await markPaid(server.id);
    return null;
  }
  const cardInFlight =
    order?.method === "card" && ["pending", "awaiting_review", "reviewing", "rejected"].includes(order.status);
  if (cardInFlight) {
    // money may already be on its way: never start over, finish this payment
    await router.push(`/order/${order!.code}?local=${id}`);
    return null;
  }
  if (m.gift.hash === hash) return server.id;
  // the server refuses anything paid or in review; a draft that is already gone is fine
  await api.deleteMuseum(server.id, { onlyDraft: true }).catch((e) => {
    if (!(e instanceof ApiError && e.status === 404)) throw e;
  });
  return "fresh";
}

async function pay() {
  const m = museum.value;
  if (!m || busy.value || rooms.value === null) return;
  if (m.gift?.state === "paid") {
    await router.push(`/museum/${m.gift.draft}`);
    return;
  }
  error.value = "";
  busy.value = t("gift.preparing");
  try {
    const body = importBody(m);
    const hash = fingerprint(body);
    const previous = await previousAttempt(m, hash);
    if (previous === null) return;

    let draftId = previous;
    if (previous === "fresh") {
      const draft = await api.importMuseum(body);
      draftId = draft.id;
      m.gift = { draft: draft.id, state: "draft", hash };
      await save(); // without this link we could not find the draft again: stop before any payment
    }
    const order = await api.createOrder("museum", draftId as number, method.value);
    m.gift = { ...m.gift!, order: order.code };
    await save();

    if (order.status === "paid") return await markPaid(draftId as number); // free users
    if (method.value === "card" || !order.invoice_link) {
      await router.push(`/order/${order.code}?local=${id}`);
      return;
    }
    const status = await tg.openInvoice(order.invoice_link);
    if (status === "cancelled") return;
    if (status === "failed") {
      error.value = errorText("unknown");
      return;
    }
    busy.value = t("gift.waiting");
    const final = await waitForOrder(order.code, () => alive);
    if (final?.status === "paid") await markPaid(draftId as number);
    else if (alive) error.value = errorText("telegram_unavailable"); // the next visit finds the payment
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : e instanceof Error ? e.message : "unknown");
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
        <div v-if="rooms">
          <span>{{ t("gift.rooms_line", { n: rooms }) }}</span><span>{{ money(rooms * (prices?.room.uzs ?? 0)) }}</span>
        </div>
        <div class="tot" data-total><span>{{ t("gift.total") }}</span><span>{{ money(totalUzs) }} {{ t("common.som") }}</span></div>
      </section>
      <p v-if="rooms === null" class="error">{{ errorText("media_full") }}</p>

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
      <button class="btn primary block" data-pay :disabled="!!busy || !prices || rooms === null" @click="pay">
        {{ method === "stars" ? t("gift.pay_stars", { n: totalStars }) : t("gift.pay_card") }}
      </button>
      <MainAction
        :text="method === 'stars' ? t('gift.pay_stars', { n: totalStars }) : t('gift.pay_card')"
        :disabled="!!busy || !prices || rooms === null"
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
