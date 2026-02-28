<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "DialogueBox",
  props: {
    speaker: { type: String, required: true },
    text: { type: String, required: true },
  },

  data() {
    return {
      displayedText: "",
      typewriterTimer: null as ReturnType<typeof setTimeout> | null,
    };
  },

  watch: {
    text: {
      immediate: true,
      handler(newText: string) {
        this.startTypewriter(newText);
      },
    },
  },

  beforeUnmount() {
    this.clearTypewriter();
  },

  methods: {
    clearTypewriter() {
      if (this.typewriterTimer !== null) {
        clearTimeout(this.typewriterTimer);
        this.typewriterTimer = null;
      }
    },

    startTypewriter(text: string) {
      this.clearTypewriter();
      this.displayedText = "";
      let i = 0;
      const tick = () => {
        if (i < text.length) {
          this.displayedText += text[i];
          i++;
          this.typewriterTimer = setTimeout(tick, 25);
        }
      };
      tick();
    },
  },
});
</script>

<template>
  <div class="dialogue-box">
    <div class="speaker">{{ speaker }}</div>
    <div class="text">{{ displayedText }}<span class="cursor">_</span></div>
  </div>
</template>

<style scoped>
.dialogue-box {
  background: #16213e;
  border: 1px solid #e74c3c;
  padding: 1rem;
  min-height: 80px;
}

.speaker {
  color: #e74c3c;
  font-weight: bold;
  font-size: 0.85rem;
  margin-bottom: 0.4rem;
  letter-spacing: 0.1em;
}

.text {
  line-height: 1.5;
  font-size: 0.95rem;
}

.cursor {
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}
</style>
