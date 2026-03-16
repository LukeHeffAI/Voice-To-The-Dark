<script setup lang="ts">
withDefaults(defineProps<{ size?: 'sm' | 'lg' }>(), { size: 'sm' })
</script>

<template>
  <span class="spinner" :class="{ 'spinner-lg': size === 'lg' }"></span>
</template>
