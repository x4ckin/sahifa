<script setup lang="ts">
import { useI18n } from "vue-i18n";

import type { CatalogItem } from "../catalog";

defineProps<{ items: readonly CatalogItem[]; modelValue: string; columns?: number }>();
const emit = defineEmits<{ "update:modelValue": [key: string] }>();
const { t } = useI18n();
</script>

<template>
  <div class="picker" :style="{ gridTemplateColumns: `repeat(${columns ?? 3}, 1fr)` }">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="opt"
      :class="{ sel: item.key === modelValue }"
      :data-option="item.key"
      :aria-pressed="item.key === modelValue"
      @click="emit('update:modelValue', item.key)"
    >
      <i>{{ item.emoji }}</i>{{ t(item.i18nKey) }}
    </button>
  </div>
</template>

<style scoped>
.picker { display: grid; gap: 6px; }
.opt { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 8px 4px; font-size: 12px; font-weight: 700; cursor: pointer; }
.opt i { display: block; font-style: normal; font-size: 22px; }
.opt.sel { border: 2px solid var(--rose); }
</style>
