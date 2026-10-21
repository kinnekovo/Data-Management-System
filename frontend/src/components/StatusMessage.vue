<script setup>
defineProps({ type: { type: String, default: 'info' }, message: { type: String, default: '' } })
</script>

<template>
  <p v-if="message" class="status-message" :class="type" role="status" aria-live="polite">
    {{ message }}
  </p>
</template>
