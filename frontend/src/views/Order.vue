<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { loadMuseum, saveMuseum } from "../account/store";
import { api, ApiError, type OrderOut } from "../api";
import { money } from "../format";
import { errorText } from "../i18n";
import { tg } from "../telegram";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const code = String(route.params.code);
const localId = typeof route.query.local === "string" ? route.query.local : null;

const order = ref<OrderOut | null>(null);
const error = ref("");
const progress = ref<number | null>(null);
const copied = ref("");
let timer: ReturnType<typeof setTimeout> | undefined;
let alive = true;
let failures = 0;

const inReview = computed(() => order.value?.status === "awaiting_review" || order.value?.status === "reviewing");

async function finishPaid(o: OrderOut) {
  try {
    if (localId && o.product === "museum" && o.museum_id !== null) {
      const m = await loadMuseum(localId);
      // only the copy this order was made for; a stale screen must not re-link it to another museum
      if (m && !m.broken && (!m.gift || m.gift.draft === o.museum_id)) {
        m.gift = { ...(m.gift ?? {}), draft: o.museum_id, state: "paid" };
        await saveMuseum(m);
      }
    }
  } catch {
    /* Home heals the local copy from the server state */
  }
  tg.haptic("success");
  if (!alive) return;
  if (o.product === "museum" && o.museum_id !== null) await router.push(`/done/${o.museum_id}`);
  else if (o.museum_id !== null) await router.push(`/museum/${o.museum_id}`);
  else await router.push("/");
}

function schedule(ms: number) {
  clearTimeout(timer);
  if (alive) timer = setTimeout(() => void refresh(), ms);
}

async function refresh() {
  try {
    order.value = await api.getOrder(code);
    failures = 0;
    error.value = "";
  } catch (e) {
    failures++;
    if (!order.value) error.value = errorText(e instanceof ApiError ? e.code : "unknown");
    schedule(Math.min(3000 * 2 ** (failures - 1), 30_000)); // keep trying: a network blip must not end the wait
    return;
  }
  if (order.value.status === "paid") return finishPaid(order.value);
  if (["pending", "awaiting_review", "reviewing"].includes(order.value.status)) schedule(3000);
}

onMounted(refresh);
onBeforeUnmount(() => {
  alive = false;
  clearTimeout(timer);
});

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    copied.value = text;
    tg.haptic("light");
  } catch {
    copied.value = "";
  }
}

async function sendReceipt(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  error.value = "";
  progress.value = 0;
  try {
    order.value = await api.uploadReceipt(code, file, (p) => (progress.value = p));
    schedule(3000);
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  } finally {
    progress.value = null;
  }
}

const reasonText = (r: string | null) => t(`order.reason.${r && ["amount", "unreadable", "notfound"].includes(r) ? r : "other"}`);
</script>

<template>
  <main class="page">
    <h2>{{ t("order.title") }}</h2>
    <p v-if="!order && !error" class="muted">{{ t("common.loading") }}</p>
    <template v-if="order">
      <p v-if="inReview" class="note">{{ t("order.reviewing") }}</p>
      <p v-if="order.status === 'rejected'" class="error">{{ t("order.rejected", { reason: reasonText(order.reject_reason) }) }}</p>

      <template v-if="!inReview && order.status !== 'paid'">
        <section class="card">
          <div class="muted">{{ t("order.step1") }}</div>
          <div class="amount">{{ money(order.amount_uzs) }} {{ t("common.som") }}</div>
          <p v-if="!order.cards?.length" class="error">{{ t("order.no_cards") }}</p>
          <button v-for="c in order.cards ?? []" :key="c.number" class="cardno" @click="copy(c.number.replace(/\s/g, ''))">
            <b>{{ c.number }}</b><small>{{ c.holder }}</small>
            <span>{{ copied === c.number.replace(/\s/g, "") ? t("common.copied") : t("common.copy") }}</span>
          </button>
        </section>
        <section class="card">
          <div class="muted">{{ t("order.step2") }}</div>
          <button class="cardno" @click="copy(order.code)">
            <b>{{ order.code }}</b><span>{{ copied === order.code ? t("common.copied") : t("common.copy") }}</span>
          </button>
        </section>
        <section class="card">
          <div class="muted">{{ t("order.step3") }}</div>
          <label class="btn primary block upload">
            {{ progress !== null ? `${Math.round(progress * 100)}%` : order.status === "rejected" ? t("order.resend") : t("order.send_receipt") }}
            <input type="file" accept="image/*" hidden data-receipt :disabled="progress !== null" @change="sendReceipt" />
          </label>
        </section>
      </template>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </main>
</template>

<style scoped>
.amount { font-size: 26px; font-weight: 800; margin: 4px 0 8px; }
.cardno { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; border: 1px dashed var(--line); background: var(--paper); border-radius: 12px; padding: 10px 12px; margin-top: 6px; cursor: pointer; }
.cardno b { font-family: ui-monospace, monospace; font-size: 16px; }
.cardno small { color: var(--muted); }
.cardno span { margin-left: auto; color: var(--rose); font-weight: 700; font-size: 13px; }
.upload { display: block; text-align: center; margin-top: 8px; }
</style>
