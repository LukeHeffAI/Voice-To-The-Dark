<script setup lang="ts">
import { usePlayerStore } from '../stores/player'

const player = usePlayerStore()

const bars = [
  { d: '1.2s', h1: '18%', h2: '68%', h3: '35%', h4: '82%', h5: '50%' },
  { d: '0.85s', h1: '55%', h2: '22%', h3: '78%', h4: '15%', h5: '60%' },
  { d: '1.4s', h1: '38%', h2: '88%', h3: '20%', h4: '65%', h5: '42%' },
  { d: '0.65s', h1: '72%', h2: '30%', h3: '92%', h4: '48%', h5: '80%' },
  { d: '1.1s', h1: '48%', h2: '95%', h3: '28%', h4: '72%', h5: '35%' },
  { d: '0.75s', h1: '82%', h2: '42%', h3: '68%', h4: '22%', h5: '55%' },
  { d: '1.3s', h1: '28%', h2: '78%', h3: '52%', h4: '88%', h5: '18%' },
  { d: '0.55s', h1: '62%', h2: '18%', h3: '82%', h4: '38%', h5: '72%' },
  { d: '0.95s', h1: '42%', h2: '72%', h3: '15%', h4: '58%', h5: '85%' },
  { d: '0.7s', h1: '52%', h2: '12%', h3: '72%', h4: '32%', h5: '65%' },
  { d: '1.15s', h1: '22%', h2: '62%', h3: '42%', h4: '85%', h5: '28%' },
]
</script>

<template>
  <div class="artwork">
    <div class="eq-viz" :class="{ paused: !player.isPlaying }" aria-hidden="true">
      <div
        v-for="(bar, i) in bars"
        :key="i"
        class="eq-bar"
        :class="{ glitch: i === 3 || i === 8 }"
        :style="{
          '--d': bar.d,
          '--h1': bar.h1,
          '--h2': bar.h2,
          '--h3': bar.h3,
          '--h4': bar.h4,
          '--h5': bar.h5,
        }"
      />
    </div>
  </div>
</template>

<style scoped>
.artwork {
  width: 280px;
  height: 280px;
  border-radius: 16px;
  background:
    radial-gradient(ellipse at 30% 40%, rgba(160, 32, 32, 0.12) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 60%, rgba(40, 10, 40, 0.2) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 50%, #0c0808 0%, #060410 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  box-shadow:
    0 24px 80px rgba(0, 0, 0, 0.7),
    0 0 0 1px rgba(255, 255, 255, 0.04);
}
.artwork::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 50%, transparent 30%, rgba(0, 0, 0, 0.5) 100%);
}

.eq-viz {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 2.5px;
  height: 90px;
  width: 120px;
  padding-bottom: 4px;
}

.eq-bar {
  flex: 1;
  min-height: 3px;
  border-radius: 1px;
  background: linear-gradient(to top, var(--color-accent), rgba(160, 32, 32, 0.25));
  box-shadow: 0 0 8px rgba(160, 32, 32, 0.15);
  animation: eq-pulse var(--d, 1s) steps(8, end) infinite;
}

.eq-bar.glitch {
  animation:
    eq-pulse var(--d, 1s) steps(8, end) infinite,
    eq-glitch 6s ease-in-out infinite;
}

.eq-viz.paused .eq-bar {
  animation-play-state: paused;
}

@keyframes eq-pulse {
  0%,
  100% {
    height: var(--h1);
    opacity: 0.65;
  }
  20% {
    height: var(--h2);
    opacity: 0.85;
  }
  40% {
    height: var(--h3);
    opacity: 0.55;
  }
  60% {
    height: var(--h4);
    opacity: 0.9;
  }
  80% {
    height: var(--h5, var(--h2));
    opacity: 0.7;
  }
}

@keyframes eq-glitch {
  0%,
  92%,
  100% {
    filter: brightness(1);
  }
  93% {
    filter: brightness(2.5);
    opacity: 0.3;
  }
  94% {
    filter: brightness(0.3);
  }
  95% {
    filter: brightness(1.8);
    opacity: 1;
  }
}

.eq-viz::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 128 128' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  opacity: 0.14;
  mix-blend-mode: overlay;
  pointer-events: none;
  animation: eq-static 0.12s steps(2) infinite;
}

.eq-viz.paused::after {
  animation-play-state: paused;
}

@keyframes eq-static {
  0% {
    transform: translate(0, 0);
  }
  100% {
    transform: translate(-5%, -8%);
  }
}
</style>
