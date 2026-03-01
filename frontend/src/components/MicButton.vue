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
        case "confession":
          return "CONFESSION RECORDED";
        default:
          return "...";
      }
    },
    isListening(): boolean {
      return this.status === "listening";
    },
    isProcessing(): boolean {
      return this.status === "transcribing" || this.status === "thinking";
    },
    isConfession(): boolean {
      return this.status === "confession";
    },
  },
});
</script>

<template>
  <div class="mic-status" role="status" aria-live="polite" :class="{ listening: isListening, processing: isProcessing, confessed: isConfession }">
    <span class="mic-label">{{ label }}</span>
  </div>
</template>

<style scoped>
.mic-status {
  display: flex;
  align-items: center;
  padding: 0.4rem 1rem;
  background: transparent;
  border: 1px solid #888;
  font-family: inherit;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
  color: #888;
}

.mic-status.listening {
  border-color: #2ecc71;
  color: #2ecc71;
}

.mic-status.processing {
  border-color: #e0e0e0;
  color: #e0e0e0;
}

.mic-status.confessed {
  border-color: #f39c12;
  color: #f39c12;
}
</style>
