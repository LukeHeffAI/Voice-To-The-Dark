<script setup lang="ts">
import { useRoute } from 'vue-router'
// Stub — full implementation in Milestone C
const route = useRoute()
</script>

<template>
  <div class="page-container">
    <router-link :to="`/story/${route.params.id}`" class="text-text-3 hover:text-text-2 text-[0.8rem] no-underline inline-block py-2">&larr; Back to story</router-link>
    <h1 class="font-serif text-2xl text-text-1 mb-4">Reader</h1>
    <p class="text-text-3 text-sm">Full reader page coming in next update.</p>
  </div>
</template>
