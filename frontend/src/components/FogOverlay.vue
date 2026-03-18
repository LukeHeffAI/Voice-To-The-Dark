<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const fogRef = ref<HTMLElement>()
const hasSettled = ref(false)

function updateFog() {
  if (!fogRef.value) return
  const el = fogRef.value
  const onSettings = route.path.startsWith('/settings')

  el.classList.remove('settle', 'visible', 'evaporate')

  if (onSettings) {
    el.classList.add('evaporate')
  } else if (!hasSettled.value) {
    el.classList.add('settle')
    hasSettled.value = true
  } else {
    el.classList.add('visible')
  }
}

onMounted(updateFog)
watch(() => route.path, updateFog)
</script>

<template>
  <div ref="fogRef" class="fog" aria-hidden="true">
    <div class="fog-l3"></div>
  </div>
</template>
