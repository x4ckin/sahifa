<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { useLocalMuseum } from "../account/useLocalMuseum";
import { api, ApiError } from "../api";
import { MASCOTS, OPENINGS, THEMES } from "../catalog";
import MainAction from "../components/MainAction.vue";
import OptionPicker from "../components/OptionPicker.vue";
import StepHeader from "../components/StepHeader.vue";
import { errorText } from "../i18n";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const id = String(route.params.id);
const { museum, loading, error, changed, flush } = useLocalMuseum(id);

const MAX_OPEN_DAYS = 120;
const dateError = ref("");
const audioBusy = ref<"" | "voice" | "music">("");
const recording = ref(false);
let recorder: MediaRecorder | null = null;
const canRecord = typeof window !== "undefined" && "MediaRecorder" in window;

/** "2026-11-20" → that day's local midnight as ISO with the local offset (the date part stays the same). */
function localMidnightIso(date: string): string {
  const offset = -new Date(`${date}T00:00`).getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hh = String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0");
  const mm = String(Math.abs(offset) % 60).padStart(2, "0");
  return `${date}T00:00:00${sign}${hh}:${mm}`;
}

const openDate = computed(() => museum.value?.open_at?.slice(0, 10) ?? "");

function setOpenDate(event: Event) {
  if (!museum.value) return;
  const value = (event.target as HTMLInputElement).value;
  if (!value) {
    museum.value.open_at = undefined;
    dateError.value = "";
    changed();
    return;
  }
  const at = new Date(localMidnightIso(value)).getTime();
  const now = Date.now();
  if (at <= now || at > now + MAX_OPEN_DAYS * 86_400_000) {
    dateError.value = t("create.open_at_bad");
    return;
  }
  dateError.value = "";
  museum.value.open_at = localMidnightIso(value);
  changed();
}

async function uploadAudio(file: File, purpose: "voice" | "music") {
  if (!museum.value) return;
  audioBusy.value = purpose;
  try {
    const { token } = await api.uploadTgMedia(file, purpose);
    museum.value[purpose] = token;
    if (purpose === "music") museum.value.music_id = undefined;
    changed();
  } catch (e) {
    error.value = errorText(e instanceof ApiError ? e.code : "unknown");
  } finally {
    audioBusy.value = "";
  }
}

function pickAudio(event: Event, purpose: "voice" | "music") {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (file) void uploadAudio(file, purpose);
}

async function toggleRecording() {
  if (recording.value) {
    recorder?.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks: Blob[] = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = () => {
      recording.value = false;
      stream.getTracks().forEach((track) => track.stop());
      const type = recorder?.mimeType || "audio/webm";
      void uploadAudio(new File(chunks, `voice.${type.includes("mp4") ? "m4a" : "webm"}`, { type }), "voice");
    };
    recorder.start();
    recording.value = true;
  } catch {
    error.value = errorText("unknown");
  }
}

function clearMusic() {
  if (!museum.value) return;
  museum.value.music = undefined;
  museum.value.music_id = undefined;
  changed();
}

onBeforeUnmount(() => {
  if (recording.value) recorder?.stop();
});

async function next() {
  await flush();
  await router.push(`/new/${id}/review`);
}
</script>

<template>
  <main class="page">
    <StepHeader :step="2" :title="t('create.step_decor')" />
    <p v-if="loading" class="muted">{{ t("common.loading") }}</p>
    <template v-else-if="museum">
      <label class="field">
        {{ t("create.recipient") }}
        <input v-model="museum.recipient" maxlength="60" data-recipient @input="changed" />
      </label>
      <label class="field">
        {{ t("create.museum_title") }}
        <input v-model="museum.title" maxlength="80" required data-title @input="changed" />
      </label>

      <div class="h3">{{ t("create.theme") }}</div>
      <OptionPicker v-model="museum.theme" :items="THEMES" @update:model-value="changed" />
      <div class="h3">{{ t("create.opening") }}</div>
      <OptionPicker v-model="museum.opening" :items="OPENINGS" :columns="4" @update:model-value="changed" />
      <div class="h3">{{ t("create.mascot") }}</div>
      <OptionPicker v-model="museum.mascot" :items="MASCOTS" :columns="5" @update:model-value="changed" />

      <div class="h3">{{ t("create.music") }}</div>
      <div class="row">
        <button class="btn" :class="{ primary: !museum.music }" @click="clearMusic">{{ t("create.music_none") }}</button>
        <label class="btn" :class="{ primary: museum.music }">
          {{ audioBusy === "music" ? t("common.loading") : t("create.music_own") }}{{ museum.music ? " ✓" : "" }}
          <input type="file" accept="audio/*" hidden @change="pickAudio($event, 'music')" />
        </label>
      </div>

      <div class="h3">{{ t("create.voice") }}{{ museum.voice ? " ✓" : "" }}</div>
      <div class="row">
        <button v-if="canRecord" class="btn" :disabled="audioBusy === 'voice'" @click="toggleRecording">
          {{ recording ? t("create.voice_stop") : t("create.voice_record") }}
        </button>
        <label class="btn">
          {{ audioBusy === "voice" ? t("common.loading") : t("create.voice_file") }}
          <input type="file" accept="audio/*" hidden @change="pickAudio($event, 'voice')" />
        </label>
      </div>

      <label class="field">
        {{ t("create.letter") }}
        <textarea v-model="museum.letter" maxlength="3000" rows="5" data-letter @input="changed" />
      </label>
      <label class="field">
        {{ t("create.open_at") }}
        <input type="date" :value="openDate" data-open-at @change="setOpenDate" />
      </label>
      <p class="muted small">{{ t("create.open_at_hint") }}</p>
      <p v-if="dateError" class="error">{{ dateError }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <MainAction :text="t('common.next')" :disabled="!museum.title.trim() || audioBusy !== ''" @click="next" />
    </template>
  </main>
</template>

<style scoped>
.small { font-size: 12px; margin: -8px 0 0; }
label.btn { display: inline-flex; align-items: center; }
</style>
