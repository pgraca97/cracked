<script lang="ts">
import { defineComponent } from "vue";

export default defineComponent({
  name: "TitleScreen",
  emits: ["start"],
});
</script>

<template>
  <div class="title-screen">
    <h1 class="title">THE STAR DIAMOND HEIST</h1>
    <div class="briefing">
      <p class="label">CASE FILE #2026-0301</p>
      <p>
        Last night, the Star Diamond was stolen from the Municipal Museum during
        a charity gala. The alarm on the display case was deactivated by someone
        with internal access. The diamond, valued at &euro;2 million, disappeared
        between 9:00 PM and 11:00 PM.
      </p>
      <p>
        Your suspect: <strong>DIEGO FONSECA</strong>, 34, museum security guard
        for 3 years. He was the last person seen near the diamond room.
      </p>
      <ul>
        <li>The display case alarm was disabled using security guard Andr&eacute; Lopes' access code</li>
        <li>Andr&eacute; Lopes ended his shift at 9:00 PM and joined the gala as a guest</li>
        <li>A security camera in the north corridor captured movement at 9:25 PM (blurry image)</li>
        <li>The diamond was reported missing at 11:30 PM by the cleaning crew</li>
        <li>Staff lockers have not been searched (warrant pending)</li>
        <li>Diego's shift ended at 11:00 PM. He was seen leaving the parking lot at 11:20 PM</li>
      </ul>
      <p class="instruction">You have 10 minutes. Find the truth.</p>
    </div>
    <button class="start-btn" @click="$emit('start')">BEGIN INTERROGATION</button>
  </div>
</template>

<style scoped>
.title-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
  gap: 1.5rem;
}

.title {
  font-size: 2rem;
  color: #e74c3c;
  text-align: center;
  letter-spacing: 0.15em;
}

.briefing {
  max-width: 640px;
  background: #16213e;
  border: 1px solid #e74c3c;
  padding: 1.5rem;
  line-height: 1.6;
}

.briefing .label {
  color: #e74c3c;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.briefing p {
  margin-bottom: 0.75rem;
}

.briefing ul {
  margin: 0.75rem 0;
  padding-left: 1.5rem;
}

.briefing li {
  margin-bottom: 0.35rem;
}

.instruction {
  color: #f39c12;
  font-weight: bold;
  text-align: center;
}

.start-btn {
  font-family: "Courier New", monospace;
  font-size: 1.1rem;
  padding: 0.75rem 2rem;
  background: #e74c3c;
  color: #fff;
  border: none;
  cursor: pointer;
  letter-spacing: 0.1em;
}

.start-btn:hover {
  background: #c0392b;
}
</style>
