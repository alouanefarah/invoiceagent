<template>
  <span class="badge" :class="status">
    <span v-if="status === 'processing'" class="pulse">●</span>
    {{ label }}
  </span>
</template>

<script setup>
const props = defineProps({ status: String })
const labels = { pending: 'En attente', processing: 'En cours', validated: 'Validée', anomaly: 'Anomalie' }
const label = labels[props.status] || props.status
</script>
