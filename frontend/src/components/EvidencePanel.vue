<script lang="ts">
import { defineComponent, type PropType } from "vue";

export default defineComponent({
  name: "EvidencePanel",
  props: {
    contradictions: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    facts: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
});
</script>

<template>
  <div class="evidence-panel">
    <h3 class="panel-title">CASE NOTES</h3>

    <div class="section" v-if="contradictions.length">
      <h4 class="section-title">CONTRADICTIONS ({{ contradictions.length }})</h4>
      <ul>
        <li v-for="(c, i) in contradictions" :key="i" class="contradiction">{{ c }}</li>
      </ul>
    </div>

    <div class="section">
      <h4 class="section-title">FACTS LOG</h4>
      <ul v-if="facts.length">
        <li v-for="(f, i) in facts" :key="i">{{ f }}</li>
      </ul>
      <p v-else class="empty">No facts recorded yet.</p>
    </div>
  </div>
</template>

<style scoped>
.evidence-panel {
  background: #16213e;
  border: 1px solid #555;
  padding: 1rem;
  overflow-y: auto;
  max-height: 100%;
}

.panel-title {
  color: #f39c12;
  font-size: 0.9rem;
  letter-spacing: 0.15em;
  margin-bottom: 0.75rem;
}

.section {
  margin-bottom: 1rem;
}

.section-title {
  font-size: 0.8rem;
  color: #e74c3c;
  margin-bottom: 0.4rem;
  letter-spacing: 0.1em;
}

ul {
  list-style: none;
  padding: 0;
}

li {
  font-size: 0.8rem;
  padding: 0.25rem 0;
  border-bottom: 1px solid #2c3e50;
}

.contradiction {
  color: #e74c3c;
}

.empty {
  font-size: 0.8rem;
  color: #555;
}
</style>
