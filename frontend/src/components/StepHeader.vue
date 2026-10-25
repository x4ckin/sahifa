<script setup lang="ts">
defineProps<{ step: 1 | 2 | 3; title: string }>();
</script>

<template>
  <div class="steps" aria-hidden="true">
    <i v-for="n in 3" :key="n" :class="{ on: n <= step }" />
  </div>
  <h2 class="step-title">{{ title }}</h2>
</template>

<style scoped>
.steps { display: flex; gap: 6px; }
.steps i { flex: 1; height: 5px; border-radius: 4px; background: var(--line); }
.steps i.on { background: var(--rose); }
.step-title { margin: 4px 0 0; font-size: 22px; }
</style>
