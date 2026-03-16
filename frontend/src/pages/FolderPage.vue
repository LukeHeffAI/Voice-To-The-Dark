<script setup lang="ts">
import { useRoute } from 'vue-router'
// Stub — full implementation in Milestone B
const route = useRoute()
</script>

<template>
  <div class="page-container">
    <router-link to="/" class="text-text-3 hover:text-text-2 text-[0.8rem] no-underline inline-block py-2">&larr; Back</router-link>
    <h1 class="font-serif text-2xl text-text-1 mb-4">Folder #{{ route.params.id }}</h1>
    <p class="text-text-3 text-sm">Full folder page coming in next update.</p>
  </div>
</template>
