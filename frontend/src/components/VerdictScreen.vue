<script lang="ts">
import { defineComponent } from "vue";
import { getSocket } from "../composables/useSocket";

export default defineComponent({
  name: "VerdictScreen",
  emits: ["result"],

  data() {
    return {
      submitted: false,
    };
  },

  mounted() {
    const socket = getSocket();
    socket.on("case_result", (result) => {
      this.$emit("result", result);
    });
  },

  beforeUnmount() {
    const socket = getSocket();
    socket.off("case_result");
  },

  methods: {
    submit(verdict: "guilty" | "not_guilty") {
      this.submitted = true;
      const socket = getSocket();
      socket.emit("submit_verdict", { verdict });
    },
  },
});
</script>

<template>
  <div class="verdict-screen">
    <h1>DELIVER YOUR VERDICT</h1>
    <p class="prompt">Based on your interrogation, is Diego Fonseca guilty of stealing the Star Diamond?</p>

    <div class="buttons" v-if="!submitted">
      <button class="verdict-btn guilty" @click="submit('guilty')">GUILTY</button>
      <button class="verdict-btn not-guilty" @click="submit('not_guilty')">NOT GUILTY</button>
    </div>
    <p v-else class="waiting">Calculating result...</p>
  </div>
</template>

<style scoped>
.verdict-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 1.5rem;
  padding: 2rem;
}

h1 {
  color: #e74c3c;
  letter-spacing: 0.15em;
}

.prompt {
  max-width: 500px;
  text-align: center;
  line-height: 1.6;
}

.buttons {
  display: flex;
  gap: 2rem;
}

.verdict-btn {
  font-family: "Courier New", monospace;
  font-size: 1.2rem;
  padding: 1rem 2.5rem;
  border: 2px solid;
  cursor: pointer;
  letter-spacing: 0.1em;
  background: transparent;
}

.verdict-btn.guilty {
  color: #e74c3c;
  border-color: #e74c3c;
}

.verdict-btn.guilty:hover {
  background: #e74c3c;
  color: #fff;
}

.verdict-btn.not-guilty {
  color: #27ae60;
  border-color: #27ae60;
}

.verdict-btn.not-guilty:hover {
  background: #27ae60;
  color: #fff;
}

.waiting {
  color: #f39c12;
}
</style>
