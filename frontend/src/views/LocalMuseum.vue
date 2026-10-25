<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { deleteLocalMuseum, loadMuseum, type LocalMuseum } from "../account/store";
import { api } from "../api";
import ConfirmButton from "../components/ConfirmButton.vue";
import { errorText } from "../i18n";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = String(route.params.id);
const museum = ref<LocalMuseum | null>(null);
const loading = ref(true);
const error = ref("");

onMounted(async () => {
  museum.value = await loadMuseum(id).catch(() => null);
  loading.value = false;
  if (!museum.value) error.value = errorText("not_found");
});

const images = computed(() => museum.value?.media.filter((m) => m.k === "image") ?? []);

async function gift() {
  const g = museum.value?.gift;
  await router.push(g?.state === "paid" ? `/museum/${g.draft}` : `/gift/${id}`);
}

async function remove() {
  try {
    await deleteLocalMuseum(id);
    await router.push("/");
  } catch {
    error.value = errorText("unknown");
  }
}
</script>

<template>
  <main class="page">
    <p v-if="loading" class="muted">{{ t("common.loading") }}</p>
    <template v-else-if="museum">
      <h2>{{ museum.title }}</h2>
      <p class="muted">{{ t("home.counts", { img: images.length, vid: museum.media.length - images.length }) }}</p>
      <p v-if="museum.broken" class="error">{{ t("home.badge_broken") }}</p>
      <div class="strip">
        <img v-for="(item, i) in images.slice(0, 8)" :key="item.t + i" :src="api.tgMediaUrl(item.t)" loading="lazy" alt="" />
      </div>
      <button v-if="!museum.broken" class="btn block" @click="router.push(`/new/${id}/media`)">{{ t("museum.edit") }}</button>
      <button v-if="!museum.broken" class="btn primary block" data-gift @click="gift">
        {{ museum.gift?.state === "paid" ? t("home.badge_gift") : t("create.review_gift") }}
      </button>
      <ConfirmButton :label="t('common.delete')" :note="t('museum.delete_local_note')" @confirm="remove" />
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </main>
</template>

<style scoped>
.strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.strip img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 10px; background: var(--line); }
</style>
