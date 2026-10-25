<script setup lang="ts">
/** A destructive action that needs a second, explicit tap. */
import { ref } from "vue";
import { useI18n } from "vue-i18n";

defineProps<{ label: string; note?: string }>();
const emit = defineEmits<{ confirm: [] }>();
const { t } = useI18n();
const asking = ref(false);
</script>

<template>
  <div class="confirm">
    <button v-if="!asking" class="btn block danger" data-delete @click="asking = true">{{ label }}</button>
    <div v-else class="card ask">
      <p>{{ t("common.confirm_delete") }}</p>
      <p v-if="note" class="muted">{{ note }}</p>
      <div class="row">
        <button class="btn grow" @click="asking = false">{{ t("common.cancel") }}</button>
        <button class="btn grow danger-fill" data-delete-confirm @click="emit('confirm')">{{ label }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.danger { color: var(--rose); }
.danger-fill { background: var(--rose); color: #fff; border-color: var(--rose); }
.ask p { margin: 0 0 8px; }
.grow { flex: 1; }
</style>
