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
    mode: {
      type: String as PropType<"facts" | "contradictions" | "both">,
      default: "both",
    },
  },
});
</script>

<template>
  <div class="evidence-panel">
    <template v-if="mode === 'facts' || mode === 'both'">
      <h3 class="panel-title">CASE NOTES</h3>
      <ul v-if="facts.length">
        <li v-for="(f, i) in facts" :key="i">{{ f }}</li>
      </ul>
      <p v-else class="empty">No facts recorded yet.</p>
    </template>

    <template v-if="mode === 'contradictions' || mode === 'both'">
      <h3 class="panel-title contradictions-title">
        CONTRADICTIONS<span v-if="contradictions.length"> ({{ contradictions.length }})</span>
      </h3>
      <ul v-if="contradictions.length">
        <li v-for="(c, i) in contradictions" :key="i" class="contradiction">{{ c }}</li>
      </ul>
      <p v-else class="empty">None caught yet.</p>
    </template>
  </div>
</template>

<style scoped>
.evidence-panel {
  background: #16213e;
  border: 1px solid #555;
  padding: 0 1rem 1rem 1rem;
  height: 100%;
}

.panel-title {
  position: sticky;
  top: 0;
  background: #16213e;
  color: #f39c12;
  font-size: 0.9rem;
  letter-spacing: 0.15em;
  padding: 1rem 0 0.5rem 0;

  z-index: 1;
}

.contradictions-title {
  color: #e74c3c;
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

li:last-child {
  border-bottom: none;
}

.contradiction {
  color: #e74c3c;
}

.empty {
  font-size: 0.8rem;
  color: #888;
}
</style>
