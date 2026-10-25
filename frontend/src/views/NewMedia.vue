<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { MAX_IMAGES, MAX_VIDEOS, roomsNeeded } from "../account/rooms";
import { useLocalMuseum } from "../account/useLocalMuseum";
import { api } from "../api";
import MainAction from "../components/MainAction.vue";
import StepHeader from "../components/StepHeader.vue";
import { errorText } from "../i18n";
import { tg } from "../telegram";
import { createQueue } from "../upload/queue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = String(route.params.id);
const { museum, loading, error, changed, flush } = useLocalMuseum(id);

const limitMessage = ref("");
const editing = ref<number | null>(null);

const queue = createQueue(
  (file, onProgress) => api.uploadTgMedia(file, "media", onProgress),
  2,
  (item) => {
    if (!museum.value || !item.result) return;
    museum.value.media.push({ t: item.result.token, k: item.result.kind === "video" ? "video" : "image" });
    changed();
  },
);

const kindOf = (f: File): "image" | "video" => (f.type.startsWith("video") ? "video" : "image");
const pending = computed(() => queue.items.value.filter((i) => i.state === "waiting" || i.state === "uploading"));
const failed = computed(() => queue.items.value.filter((i) => i.state === "error"));
const images = computed(() => (museum.value?.media.filter((m) => m.k === "image").length ?? 0));
const videos = computed(() => (museum.value?.media.length ?? 0) - images.value);
const rooms = computed(() => {
  try {
    return roomsNeeded(images.value, videos.value);
  } catch {
    return 10;
  }
});
const needsStart = computed(() => failed.value.some((i) => i.error === "start_bot"));

function pick(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  input.value = "";
  let img = images.value + pending.value.filter((i) => kindOf(i.file) === "image").length;
  let vid = videos.value + pending.value.filter((i) => kindOf(i.file) === "video").length;
  const accepted: File[] = [];
  for (const file of files) {
    if (kindOf(file) === "image" ? img < MAX_IMAGES : vid < MAX_VIDEOS) {
      accepted.push(file);
      if (kindOf(file) === "image") img++;
      else vid++;
    }
  }
  limitMessage.value = accepted.length < files.length ? t("create.limit_reached", { maxImg: MAX_IMAGES, maxVid: MAX_VIDEOS }) : "";
  if (accepted.length) queue.add(accepted);
}

function move(index: number, delta: -1 | 1) {
  const list = museum.value?.media;
  const target = index + delta;
  if (!list || target < 0 || target >= list.length) return;
  [list[index], list[target]] = [list[target], list[index]];
  tg.haptic("light");
  changed();
}

function remove(index: number) {
  museum.value?.media.splice(index, 1);
  editing.value = null;
  changed();
}

function openBot() {
  tg.openTelegramLink(`https://t.me/${import.meta.env.VITE_BOT_USERNAME ?? ""}?start=files`);
}

async function next() {
  await flush();
  await router.push(`/new/${id}/decor`);
}
</script>

<template>
  <main class="page">
    <StepHeader :step="1" :title="t('create.step_media')" />
    <p v-if="loading" class="muted">{{ t("common.loading") }}</p>
    <template v-else-if="museum">
      <div class="counter muted" data-counter>
        <span>{{ t("create.counter", { img: images, maxImg: MAX_IMAGES, vid: videos, maxVid: MAX_VIDEOS }) }}</span>
        <span v-if="pending.length">{{ t("create.uploading", { n: pending.length }) }}</span>
      </div>
      <p v-if="rooms > 0" class="rooms">{{ t("create.rooms_needed", { n: rooms }) }}</p>
      <p v-if="limitMessage" class="error">{{ limitMessage }}</p>
      <div v-if="needsStart" class="note">
        {{ errorText("start_bot") }}
        <button class="btn block" @click="openBot">Telegram →</button>
      </div>

      <div class="grid">
        <div v-for="(item, i) in museum.media" :key="item.t + i" class="tile" :class="{ sel: editing === i }">
          <button class="thumb" @click="editing = editing === i ? null : i">
            <img v-if="item.k === 'image'" :src="api.tgMediaUrl(item.t)" loading="lazy" alt="" />
            <span v-else class="video">▶</span>
            <span v-if="i === 0" class="star" :title="t('create.cover')">★</span>
            <span v-if="item.c" class="has-caption">✎</span>
          </button>
          <div class="tools">
            <button data-move-up :disabled="i === 0" @click="move(i, -1)">↑</button>
            <button data-move-down :disabled="i === museum.media.length - 1" @click="move(i, 1)">↓</button>
          </div>
        </div>
        <div v-for="item in pending" :key="item.id" class="tile uploading">
          <div class="bar"><i :style="{ width: `${Math.round(item.progress * 100)}%` }" /></div>
        </div>
        <div v-for="item in failed" :key="item.id" class="tile failed">
          <small>{{ errorText(item.error ?? "unknown") }}</small>
          <button @click="queue.retry(item.id)">{{ t("common.retry") }}</button>
          <button @click="queue.remove(item.id)">✕</button>
        </div>
        <label class="tile add">
          +
          <input type="file" accept="image/*,video/*" multiple data-media-input hidden @change="pick" />
        </label>
      </div>

      <div v-if="editing !== null && museum.media[editing]" class="card editor">
        <label class="field">
          {{ t("create.caption") }}
          <input v-model="museum.media[editing].c" maxlength="200" :placeholder="t('create.caption_ph')" @input="changed" />
        </label>
        <label class="field">
          {{ t("create.taken_on") }}
          <input v-model="museum.media[editing].d" maxlength="32" placeholder="2021" @input="changed" />
        </label>
        <button class="btn" @click="remove(editing)">{{ t("common.delete") }}</button>
      </div>

      <p class="note">{{ t("create.stored_note") }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <MainAction :text="t('common.next')" :disabled="museum.media.length === 0 || pending.length > 0" @click="next" />
    </template>
  </main>
</template>

<style scoped>
.counter { display: flex; justify-content: space-between; font-size: 13px; }
.rooms { margin: 0; font-size: 13px; font-weight: 700; color: var(--gold); }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.tile { position: relative; aspect-ratio: 1; border-radius: 10px; overflow: hidden; background: var(--card); border: 1px solid var(--line); display: flex; flex-direction: column; }
.tile.sel { outline: 2px solid var(--rose); }
.thumb { flex: 1; border: 0; padding: 0; background: linear-gradient(135deg, #f6b7a6, #8fb8de); position: relative; cursor: pointer; }
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.video { font-size: 26px; color: #fff; }
.star { position: absolute; left: 5px; top: 3px; color: #fff; text-shadow: 0 0 4px #0008; }
.has-caption { position: absolute; right: 5px; top: 3px; color: #fff; text-shadow: 0 0 4px #0008; }
.tools { display: flex; }
.tools button { flex: 1; border: 0; background: var(--card); padding: 3px; cursor: pointer; }
.tools button:disabled { opacity: 0.3; }
.uploading { justify-content: flex-end; padding: 8px; }
.bar { height: 6px; border-radius: 3px; background: var(--line); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--rose); transition: width 0.2s; }
.failed { padding: 6px; gap: 4px; justify-content: center; font-size: 11px; text-align: center; }
.failed button { border: 1px solid var(--line); background: var(--paper); border-radius: 8px; cursor: pointer; }
.add { align-items: center; justify-content: center; font-size: 30px; color: var(--muted); border-style: dashed; cursor: pointer; }
.editor { display: flex; flex-direction: column; gap: 8px; }
</style>
