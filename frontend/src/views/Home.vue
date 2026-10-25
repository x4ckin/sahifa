<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { collectGarbage, listMuseums, newMuseum, saveMuseum, type LocalMuseum } from "../account/store";
import { api, ApiError, type Me, type MuseumSummary, type Prices } from "../api";
import { TEMPLATES, TEMPLATE_DEFAULTS, type TemplateKey } from "../catalog";
import { errorText } from "../i18n";
import { daysLeft, money } from "../format";
import { tg } from "../telegram";

const { t } = useI18n();
const router = useRouter();

const locals = ref<LocalMuseum[]>([]);
const servers = ref<MuseumSummary[]>([]);
const me = ref<Me | null>(null);
const prices = ref<Prices | null>(null);
const error = ref("");
const busy = ref(false);

interface Row {
  key: string;
  title: string;
  subtitle: string;
  badge: string;
  tone: "free" | "gift" | "muted";
  to: string;
}

const rows = computed<Row[]>(() => {
  const byId = new Map(servers.value.map((m) => [m.id, m]));
  const linked = new Set<number>();
  const list: Row[] = locals.value.map((m) => {
    const img = m.media.filter((x) => x.k === "image").length;
    const counts = t("home.counts", { img, vid: m.media.length - img });
    const gifted = m.gift?.state === "paid" ? byId.get(m.gift.draft) : undefined;
    if (m.gift) linked.add(m.gift.draft);
    if (m.broken) return { key: m.id, title: m.title, subtitle: "", badge: t("home.badge_broken"), tone: "muted", to: `/local/${m.id}` };
    if (!gifted) return { key: m.id, title: m.title, subtitle: counts, badge: t("home.badge_free"), tone: "free", to: `/local/${m.id}` };
    const expired = gifted.status === "expired";
    return {
      key: m.id,
      title: m.title,
      subtitle: expired ? t("home.badge_expired") : t("common.days_left", { n: daysLeft(gifted.expires_at) }),
      badge: t("home.badge_gift"),
      tone: expired ? "muted" : "gift",
      to: `/museum/${gifted.id}`,
    };
  });
  // museums handed over to this user have no local copy
  for (const m of servers.value) {
    if (linked.has(m.id) || m.status === "draft") continue;
    list.push({
      key: `s${m.id}`,
      title: m.title,
      subtitle: m.status === "expired" ? t("home.badge_expired") : t("common.days_left", { n: daysLeft(m.expires_at) }),
      badge: t("home.badge_received"),
      tone: "gift",
      to: `/museum/${m.id}`,
    });
  }
  return list;
});

const total = computed(() => me.value?.slots.total ?? 10);
const unlimited = computed(() => me.value !== null && me.value.slots.total === null);
const full = computed(() => !unlimited.value && locals.value.length >= total.value);

onMounted(async () => {
  locals.value = await listMuseums().catch(() => []);
  try {
    [me.value, servers.value, prices.value] = await Promise.all([api.getMe(), api.listMuseums(), api.getPrices()]);
  } catch (e) {
    if (tg.available()) error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  }
  void collectGarbage().catch(() => 0);
});

async function start(template: TemplateKey) {
  if (full.value || busy.value) return;
  busy.value = true;
  const letterKey = TEMPLATE_DEFAULTS[template].letterKey;
  const museum = newMuseum(template, { title: t("create.default_title"), letter: letterKey ? t(letterKey) : "" });
  try {
    await saveMuseum(museum);
    tg.haptic("light");
    await router.push(`/new/${museum.id}/media`);
  } catch {
    error.value = errorText("unknown");
  } finally {
    busy.value = false;
  }
}

async function buySlots(method: "card" | "stars") {
  try {
    const order = await api.createOrder("slots", null, method);
    if (method === "card" || !order.invoice_link) {
      await router.push(`/order/${order.code}`);
      return;
    }
    if ((await tg.openInvoice(order.invoice_link)) === "paid") me.value = await api.getMe();
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  }
}
</script>

<template>
  <main class="page">
    <section class="hero">
      <span class="sparkle">🎁</span>
      <h1>{{ t("home.hero_title") }}</h1>
      <p>{{ t("home.hero_text") }}</p>
      <button v-if="!full" class="hero-btn" data-new :disabled="busy" @click="start('blank')">{{ t("home.new") }}</button>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="!full">
      <div class="h3">{{ t("home.templates") }}</div>
      <div class="chips">
        <button v-for="tpl in TEMPLATES" :key="tpl.key" class="chip" :data-template="tpl.key" :disabled="busy" @click="start(tpl.key)">
          <i>{{ tpl.emoji }}</i>{{ t(tpl.i18nKey) }}
        </button>
      </div>
    </template>
    <div v-else class="card full">
      <p>{{ t("home.slots_full", { used: locals.length, total }) }}</p>
      <button class="btn primary block" data-buy-slots-card @click="buySlots('card')">
        {{ t("home.buy_slots_card", { price: money(prices?.slots.uzs ?? 5000) }) }}
      </button>
      <button class="btn block" data-buy-slots-stars @click="buySlots('stars')">
        {{ t("home.buy_slots_stars", { n: prices?.slots.stars ?? 25 }) }}
      </button>
    </div>

    <div class="h3">
      {{ t("home.mine") }}
      <small data-counter>{{ locals.length }} / {{ unlimited ? "∞" : total }}</small>
    </div>
    <p v-if="rows.length === 0" class="muted">{{ t("home.empty") }}</p>
    <RouterLink v-for="row in rows" :key="row.key" :to="row.to" class="mcard" data-museum>
      <div class="thumb" />
      <div class="info">
        <b>{{ row.title }}</b>
        <small>{{ row.subtitle }}</small>
      </div>
      <span class="badge" :class="row.tone">{{ row.badge }}</span>
    </RouterLink>
  </main>
</template>

<style scoped>
.hero { background: linear-gradient(150deg, #3a2433, #7a3b4f 55%, #c96b6b); color: #fff; border-radius: 20px; padding: 18px; position: relative; overflow: hidden; }
.hero h1 { margin: 0 0 6px; font-size: 24px; line-height: 1.15; }
.hero p { margin: 0 0 14px; opacity: 0.85; font-size: 14px; }
.hero-btn { background: #fff; color: #7a3b4f; font-weight: 800; padding: 10px 16px; border-radius: 12px; border: 0; cursor: pointer; }
.sparkle { position: absolute; right: 14px; top: 10px; font-size: 40px; }
.chips { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; }
.chip { flex: 0 0 auto; background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 10px 12px; font-size: 13px; font-weight: 700; cursor: pointer; }
.chip i { display: block; font-style: normal; font-size: 22px; }
.full { display: flex; flex-direction: column; gap: 8px; }
.full p { margin: 0; }
.mcard { display: flex; gap: 12px; align-items: center; background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 10px; color: inherit; text-decoration: none; }
.thumb { width: 52px; height: 52px; border-radius: 12px; background: linear-gradient(135deg, #f6b7a6, #8fb8de); flex: 0 0 auto; }
.info { display: flex; flex-direction: column; min-width: 0; }
.info b { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.info small { color: var(--muted); font-size: 12px; }
.badge { font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 20px; margin-left: auto; white-space: nowrap; }
.badge.free { background: var(--ok-soft); color: var(--ok); }
.badge.gift { background: var(--rose-soft); color: var(--rose); }
.badge.muted { background: var(--line); color: var(--muted); }
</style>
