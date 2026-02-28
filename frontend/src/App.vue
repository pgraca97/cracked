<script lang="ts">
import { defineComponent } from "vue";
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
      this.caseResult = null;
      this.currentScreen = "title";
    },
  },
});
</script>

<template>
  <TitleScreen v-if="currentScreen === 'title'" @start="startGame" />
  <GameScreen
    v-else-if="currentScreen === 'game'"
    @verdict="showVerdict"
    @result="showResult"
  />
  <VerdictScreen
    v-else-if="currentScreen === 'verdict'"
    @result="showResult"
  />
  <ResultScreen
    v-else-if="currentScreen === 'result'"
    :result="caseResult!"
    @restart="restart"
  />
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: "Courier New", monospace;
  min-height: 100vh;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>
