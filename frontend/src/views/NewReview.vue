<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useLocalMuseum } from "../account/useLocalMuseum";
import { api } from "../api";
import MainAction from "../components/MainAction.vue";
import StepHeader from "../components/StepHeader.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = String(route.params.id);
const { museum, loading, flush } = useLocalMuseum(id);
const images = computed(() => museum.value?.media.filter((m) => m.k === "image") ?? []);
const videos = computed(() => museum.value?.media.filter((m) => m.k === "video") ?? []);

async function gift() {
  await flush();
  await router.push(`/gift/${id}`);
}

async function saveAndExit() {
  await flush();
  await router.push("/");
}
</script>

<template>
  <main class="page">
    <StepHeader :step="3" :title="t('create.step_review')" />
    <p v-if="loading" class="muted">{{ t("common.loading") }}</p>
    <template v-else-if="museum">
      <section class="door">
        <h2>{{ museum.title }}</h2>
        <p v-if="museum.recipient">{{ t("viewer.for", { name: museum.recipient }) }}</p>
      </section>
      <p v-if="museum.letter" class="letter">{{ museum.letter }}</p>
      <div class="gallery" data-gallery>
        <figure v-for="(item, i) in images" :key="item.t + i">
          <img :src="api.tgMediaUrl(item.t)" loading="lazy" alt="" />
          <figcaption v-if="item.c || item.d">{{ item.c }}<small v-if="item.d"> · {{ item.d }}</small></figcaption>
        </figure>
        <figure v-for="(item, i) in videos" :key="item.t + 'v' + i">
          <video :src="api.tgMediaUrl(item.t)" controls preload="none" playsinline />
          <figcaption v-if="item.c">{{ item.c }}</figcaption>
        </figure>
      </div>
      <button class="btn block" @click="saveAndExit">{{ t("create.review_save") }}</button>
      <button class="btn primary block" data-gift @click="gift">{{ t("create.review_gift") }}</button>
      <MainAction :text="t('create.review_gift')" @click="gift" />
    </template>
  </main>
</template>

<style scoped>
.door { text-align: center; padding: 18px; border-radius: 18px; background: linear-gradient(#f3eee6 62%, #d9cbb6 62%); color: #5a4a3a; }
.door h2 { margin: 0; font-style: italic; }
.door p { margin: 6px 0 0; }
.letter { white-space: pre-wrap; font-family: Fraunces, Georgia, serif; font-style: italic; line-height: 1.5; }
.gallery { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
figure { margin: 0; background: var(--card); border: 6px solid #9c7446; border-radius: 4px; }
figure img, figure video { width: 100%; display: block; aspect-ratio: 4/5; object-fit: cover; background: #ddd; }
figcaption { font-size: 12px; padding: 4px 6px; color: var(--muted); }
</style>
