<script lang="ts">
import { defineComponent } from "vue";
import { playTick } from "../composables/useSounds";

export default defineComponent({
  name: "DialogueBox",
  props: {
    speaker: { type: String, required: true },
    text: { type: String, required: true },
    instant: { type: Boolean, default: false },
    speed: { type: Number, default: 25 },
    portrait: { type: String, default: "" },
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
        if (this.instant) {
          this.displayedText = newText;
        } else {
          this.startTypewriter(newText);
        }
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
      let charCount = 0;
      // Don't tick for the "..." loading placeholder - only real dialogue
      const shouldTick = text.length > 3;
      const tick = () => {
        if (i < text.length) {
          this.displayedText += text[i];
          if (shouldTick && text[i] !== " ") {
            charCount++;
            if (charCount % 5 === 1) playTick();
          }
          i++;
          this.typewriterTimer = setTimeout(tick, this.speed);
        }
      };
      tick();
    },
  },
});
</script>

<template>
  <div class="dialogue-box">
    <img v-if="portrait" :src="portrait" alt="" class="portrait" aria-hidden="true" />
    <div class="dialogue-content">
      <div class="speaker">{{ speaker }}</div>
      <div class="text">{{ displayedText }}<span class="cursor">_</span></div>
    </div>
  </div>
</template>

<style scoped>
.dialogue-box {
  --accent: #aaa;
  background: #16213e;
  border: 3px solid var(--accent);
  border-radius: 4px;
  box-shadow:
    0 0 0 1px #0d1526,
    inset 0 0 0 1px rgba(255, 255, 255, 0.04);
  padding: 1rem;
  min-height: 80px;
  font-family: inherit;
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  image-rendering: pixelated;
}

.portrait {
  width: 48px;
  height: 48px;
  image-rendering: pixelated;
  flex-shrink: 0;
  align-self: center;
}

.dialogue-content {
  flex: 1;
  min-width: 0;
}

.speaker {
  color: var(--accent);
  font-weight: 700;
  font-size: 0.85rem;
  margin-bottom: 0.4rem;
  letter-spacing: 0.1em;
}

.text {
  line-height: 1.6;
  font-size: 1rem;
}

.cursor {
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .cursor {
    animation: none;
  }
}
</style>
