<script setup lang="ts">
/** The screen's primary action: Telegram's bottom MainButton inside Telegram, a normal button elsewhere. */
import { onBeforeUnmount, watch } from "vue";

import { tg } from "../telegram";

const props = defineProps<{ text: string; disabled?: boolean }>();
const emit = defineEmits<{ click: [] }>();
const inTelegram = tg.available();
let cleanup = () => {};

function onClick() {
  if (!props.disabled) emit("click");
}

watch(
  () => [props.text, props.disabled] as const,
  ([text, disabled]) => {
    cleanup();
    cleanup = disabled ? () => {} : tg.mainButton(text, onClick);
  },
  { immediate: true },
);
onBeforeUnmount(() => cleanup());
</script>

<template>
  <button v-if="!inTelegram" class="btn primary block main-action" :disabled="disabled" @click="onClick">{{ text }}</button>
</template>

<style scoped>
.main-action { position: sticky; bottom: 12px; margin-top: 8px; }
</style>
