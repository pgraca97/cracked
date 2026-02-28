<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "MicButton",
  props: {
    status: {
      type: String,
      required: true,
    },
  },
  computed: {
    label(): string {
      switch (this.status) {
        case "listening":
          return "LISTENING...";
        case "transcribing":
          return "TRANSCRIBING...";
        case "thinking":
          return "DIEGO IS THINKING...";
        default:
          return "...";
      }
    },
    isListening(): boolean {
      return this.status === "listening";
    },
  },
});
</script>

<template>
  <div class="mic-button" :class="{ active: isListening }">
    <div class="mic-icon">&#127908;</div>
    <span class="mic-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.mic-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #2c3e50;
  border: 1px solid #555;
  font-family: "Courier New", monospace;
  color: #888;
}

.mic-button.active {
  border-color: #e74c3c;
  color: #e74c3c;
}

.mic-icon {
  font-size: 1.2rem;
}

.mic-label {
  font-size: 0.8rem;
  letter-spacing: 0.1em;
}
</style>
