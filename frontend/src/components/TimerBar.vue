<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "TimerBar",
  props: {
    secondsLeft: {
      type: Number,
      required: true,
    },
  },
  computed: {
    minutes(): string {
      const m = Math.floor(Math.max(0, this.secondsLeft) / 60);
      return String(m).padStart(2, "0");
    },
    seconds(): string {
      const s = Math.floor(Math.max(0, this.secondsLeft) % 60);
      return String(s).padStart(2, "0");
    },
    percent(): number {
      return Math.max(0, (this.secondsLeft / 600) * 100);
    },
    urgent(): boolean {
      return this.secondsLeft <= 60;
    },
  },
});
</script>

<template>
  <div class="timer-bar">
    <div class="timer-track">
      <div class="timer-fill" :class="{ urgent }" :style="{ width: percent + '%' }"></div>
    </div>
    <span class="timer-text" :class="{ urgent }">{{ minutes }}:{{ seconds }}</span>
  </div>
</template>

<style scoped>
.timer-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.timer-track {
  flex: 1;
  height: 8px;
  background: #2c3e50;
  border-radius: 4px;
  overflow: hidden;
}

.timer-fill {
  height: 100%;
  background: #27ae60;
  transition: width 1s linear;
}

.timer-fill.urgent {
  background: #e74c3c;
}

.timer-text {
  font-size: 1.1rem;
  font-weight: bold;
  min-width: 4rem;
  text-align: right;
}

.timer-text.urgent {
  color: #e74c3c;
}
</style>
