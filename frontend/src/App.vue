<script setup lang="ts">
</script>

<template>
  <div class="min-h-screen bg-bg text-white font-sans">
    <!-- Page content changes; app shell persists -->
    <RouterView />

    <!-- Persistent audio element (survives navigation) -->
    <audio ref="audioEl" />
  </div>
</template>
