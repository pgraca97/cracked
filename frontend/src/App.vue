<script lang="ts">
import { defineComponent } from "vue";
import { getSocket } from "./composables/useSocket";
import TitleScreen from "./components/TitleScreen.vue";
import GameScreen from "./components/GameScreen.vue";
import VerdictScreen from "./components/VerdictScreen.vue";
import ResultScreen from "./components/ResultScreen.vue";

type Screen = "title" | "game" | "verdict" | "result";

interface CaseResult {
  verdict: string;
  stars: number;
  contradictions: number;
  confession: boolean;
  time_seconds: number;
  summary: string;
}

export default defineComponent({
  name: "App",
  components: { TitleScreen, GameScreen, VerdictScreen, ResultScreen },

  data() {
    return {
      currentScreen: "title" as Screen,
      caseResult: null as CaseResult | null,
    };
  },

  methods: {
    startGame() {
      this.currentScreen = "game";
    },
    showVerdict() {
      this.currentScreen = "verdict";
    },
    showResult(result: CaseResult) {
      this.caseResult = result;
      this.currentScreen = "result";
    },
    restart() {
      // Disconnect so a new sid + fresh GameEngine is created on reconnect
      getSocket().disconnect();
      this.caseResult = null;
      this.currentScreen = "title";
    },
  },
});
</script>

<template>
  <Transition name="fade" mode="out-in">
    <TitleScreen v-if="currentScreen === 'title'" key="title" @start="startGame" />
    <GameScreen
      v-else-if="currentScreen === 'game'"
      key="game"
      @verdict="showVerdict"
      @quit="restart"
    />
    <VerdictScreen
      v-else-if="currentScreen === 'verdict'"
      key="verdict"
      @result="showResult"
    />
    <ResultScreen
      v-else-if="currentScreen === 'result'"
      key="result"
      :result="caseResult!"
      @restart="restart"
    />
  </Transition>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  scrollbar-width: thin;
  scrollbar-color: #444 #1a1a2e;
}

html::-webkit-scrollbar {
  width: 6px;
}

html::-webkit-scrollbar-track {
  background: #1a1a2e;
}

html::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 3px;
}

html::-webkit-scrollbar-thumb:hover {
  background: #666;
}

body {
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: 'Pixelify Sans', 'Courier New', monospace;
  min-height: 100vh;
  cursor: url('/cursor/pointer_a.png') 4 2, default;
}

/* Pixel cursors - global overrides */
a,
button,
[role="button"],
input[type="submit"],
label[for],
select,
.clickable {
  cursor: url('/cursor/hand_point.png') 10 4, pointer;
}

button:disabled,
.disabled {
  cursor: url('/cursor/disabled.png') 16 16, not-allowed;
}

.cursor-wait,
.cursor-wait * {
  cursor: url('/cursor/busy_hourglass.png') 16 16, wait !important;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Screen transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active {
    transition: none;
  }
}
</style>
