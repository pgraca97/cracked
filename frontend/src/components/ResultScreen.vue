<script lang="ts">
import { defineComponent, type PropType } from "vue";

interface CaseResult {
  verdict: string;
  stars: number;
  contradictions: number;
  confession: boolean;
  time_seconds: number;
  summary: string;
}

export default defineComponent({
  name: "ResultScreen",
  props: {
    result: {
      type: Object as PropType<CaseResult>,
      required: true,
    },
  },
  emits: ["restart"],

  computed: {
    starCount(): number {
      return this.result.stars;
    },
    timeDisplay(): string {
      const m = Math.floor(this.result.time_seconds / 60);
      const s = Math.floor(this.result.time_seconds % 60);
      return `${m}m ${s}s`;
    },
  },
});
</script>

<template>
  <div class="result-screen">
    <div class="stars">
      <span v-if="starCount === 0" class="case-cold">CASE COLD</span>
      <img
        v-for="n in starCount"
        :key="n"
        src="/star.gif"
        alt="★"
        class="star-img"
      />
    </div>
    <p class="summary">{{ result.summary }}</p>

    <div class="stats">
      <div class="stat">
        <span class="stat-label">Verdict</span>
        <span class="stat-value">{{ result.verdict === "guilty" ? "GUILTY" : "NOT GUILTY" }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Contradictions</span>
        <span class="stat-value">{{ result.contradictions }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Confession</span>
        <span class="stat-value">{{ result.confession ? "YES" : "NO" }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Time</span>
        <span class="stat-value">{{ timeDisplay }}</span>
      </div>
    </div>

    <button class="restart-btn" @click="$emit('restart')">PLAY AGAIN</button>
  </div>
</template>

<style scoped>
.result-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 1.5rem;
  padding: 2rem;
}

.stars {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  justify-content: center;
  min-height: 80px;
}

.star-img {
  width: auto;
  height: 52px;
  image-rendering: pixelated;
}

.case-cold {
  font-size: 2rem;
  letter-spacing: 0.15em;
}

.summary {
  max-width: 500px;
  text-align: center;
  line-height: 1.6;
  color: #f39c12;
}

.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  max-width: 400px;
  width: 100%;
}

.stat {
  background: #16213e;
  padding: 0.75rem;
  text-align: center;
}

.stat-label {
  display: block;
  font-size: 0.7rem;
  color: #888;
  letter-spacing: 0.1em;
  margin-bottom: 0.25rem;
}

.stat-value {
  font-weight: bold;
  font-size: 1rem;
}

.restart-btn {
  font-family: inherit;
  font-size: 1rem;
  padding: 0.75rem 2rem;
  background: transparent;
  color: #e0e0e0;
  border: 1px solid #e0e0e0;
  letter-spacing: 0.1em;
}

.restart-btn:hover {
  background: #e0e0e0;
  color: #1a1a2e;
}

.restart-btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}
</style>
