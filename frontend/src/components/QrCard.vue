<script setup lang="ts">
/** Plain QR for now; the heart-shaped QR arrives with plan 3. `qrcode` is loaded only when shown. */
import { ref, watchEffect } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ link: string }>();
const { t } = useI18n();
const dataUrl = ref("");

watchEffect(async () => {
  if (!props.link) return;
  const QRCode = await import("qrcode");
  dataUrl.value = await QRCode.toDataURL(props.link, { width: 480, margin: 1, color: { dark: "#2a211c", light: "#ffffff" } });
});
</script>

<template>
  <div class="qr">
    <img v-if="dataUrl" :src="dataUrl" alt="QR" />
    <a v-if="dataUrl" class="btn" :href="dataUrl" download="sahifa-qr.png">{{ t("done.qr") }}</a>
  </div>
</template>

<style scoped>
.qr { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.qr img { width: 180px; height: 180px; border-radius: 12px; background: #fff; padding: 6px; }
.qr a { text-decoration: none; }
</style>
