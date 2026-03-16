<script setup lang="ts">
import { onMounted, ref } from 'vue'

const fogEl = ref<HTMLElement>()

onMounted(() => {
  // Settle animation on mount
  if (fogEl.value) {
    fogEl.value.classList.add('settle')
    fogEl.value.addEventListener(
      'animationend',
      () => {
        fogEl.value?.classList.remove('settle')
        fogEl.value?.classList.add('visible')
      },
      { once: true },
    )
  }
})
</script>

<template>
  <!-- Film grain overlay -->
  <div class="grain" aria-hidden="true" />
  <!-- Vignette -->
  <div class="vignette" aria-hidden="true" />
  <!-- Drifting fog -->
  <div ref="fogEl" class="fog" aria-hidden="true">
    <div class="fog-l3" />
  </div>
</template>

<style scoped>
.grain {
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  opacity: 0.03;
  pointer-events: none;
  z-index: 10000;
}

.vignette {
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(0, 0, 0, 0.35) 100%);
  pointer-events: none;
  z-index: 9999;
}

.fog {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 2;
  overflow: hidden;
  clip-path: inset(0);
  opacity: 0;
}
.fog.visible {
  opacity: 1;
}

.fog::before,
.fog::after,
.fog-l3 {
  position: absolute;
  bottom: -12%;
  left: -150%;
  width: 1000%;
  height: 200%;
  filter: blur(35px);
  will-change: transform;
}
.fog::before,
.fog::after {
  content: '';
}

/* Layer 1 */
.fog::before {
  background: radial-gradient(ellipse 18% 55% at 5% 100%, rgba(195, 192, 215, 0.17) 0%, transparent 70%),
    radial-gradient(ellipse 22% 52% at 22% 100%, rgba(178, 174, 200, 0.14) 0%, transparent 65%),
    radial-gradient(ellipse 18% 48% at 40% 100%, rgba(188, 184, 210, 0.13) 0%, transparent 62%),
    radial-gradient(ellipse 22% 55% at 58% 100%, rgba(175, 172, 196, 0.16) 0%, transparent 68%),
    radial-gradient(ellipse 18% 50% at 75% 100%, rgba(165, 162, 186, 0.12) 0%, transparent 63%),
    radial-gradient(ellipse 22% 52% at 92% 100%, rgba(182, 178, 205, 0.15) 0%, transparent 66%);
  animation: fog-drift-1 18s ease-in-out infinite alternate;
}

/* Layer 2 */
.fog::after {
  background: radial-gradient(ellipse 20% 50% at 12% 95%, rgba(196, 192, 216, 0.09) 0%, transparent 62%),
    radial-gradient(ellipse 22% 54% at 30% 100%, rgba(182, 178, 205, 0.11) 0%, transparent 67%),
    radial-gradient(ellipse 20% 48% at 49% 95%, rgba(195, 190, 214, 0.08) 0%, transparent 62%),
    radial-gradient(ellipse 22% 52% at 67% 100%, rgba(178, 174, 200, 0.1) 0%, transparent 65%),
    radial-gradient(ellipse 20% 50% at 85% 95%, rgba(190, 186, 210, 0.09) 0%, transparent 63%);
  animation: fog-drift-2 12s ease-in-out infinite alternate;
}

/* Layer 3 */
.fog-l3 {
  height: 350%;
  filter: blur(42px);
  background: radial-gradient(ellipse 20% 46% at 8% 92%, rgba(200, 196, 218, 0.14) 0%, transparent 63%),
    radial-gradient(ellipse 18% 50% at 28% 100%, rgba(185, 182, 206, 0.12) 0%, transparent 60%),
    radial-gradient(ellipse 20% 44% at 48% 92%, rgba(192, 188, 212, 0.13) 0%, transparent 61%),
    radial-gradient(ellipse 18% 48% at 68% 100%, rgba(180, 176, 202, 0.12) 0%, transparent 62%),
    radial-gradient(ellipse 20% 46% at 88% 92%, rgba(196, 192, 215, 0.14) 0%, transparent 63%);
  animation: fog-drift-3 7s ease-in-out infinite alternate;
}

@keyframes fog-drift-1 {
  0% { opacity: 1; transform: translate(0, 0); }
  25% { opacity: 0.6; transform: translate(-50vw, -1.3vh); }
  50% { opacity: 0.4; transform: translate(-100vw, -2vh); }
  75% { opacity: 0.6; transform: translate(-50vw, -0.9vh); }
  100% { opacity: 1; transform: translate(0, 0); }
}

@keyframes fog-drift-2 {
  0% { opacity: 0.3; transform: translate(0, 0); }
  25% { opacity: 0.75; transform: translate(32vw, 1.4vh); }
  50% { opacity: 0.8; transform: translate(64vw, 2vh); }
  75% { opacity: 0.75; transform: translate(32vw, 0.9vh); }
  100% { opacity: 0.3; transform: translate(0, 0); }
}

@keyframes fog-drift-3 {
  0% { opacity: 0.75; transform: translate(0, 0); }
  25% { opacity: 0.2; transform: translate(-30vw, -1.1vh); }
  50% { opacity: 0.75; transform: translate(-20vw, -0.7vh); }
  75% { opacity: 0.2; transform: translate(10vw, 0.3vh); }
  100% { opacity: 0.75; transform: translate(0, 0); }
}

.fog.settle {
  animation: fog-settle 3.5s ease-out forwards;
}

@keyframes fog-settle {
  0% { opacity: 0; transform: translateY(8vh); }
  100% { opacity: 1; transform: translateY(0); }
}
</style>
