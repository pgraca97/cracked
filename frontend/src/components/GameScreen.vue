<script lang="ts">
import { defineComponent } from "vue";
import { getSocket } from "../composables/useSocket";
import { startVAD, pauseVAD, resumeVAD, destroyVAD, float32ToWav } from "../composables/useVAD";
import DialogueBox from "./DialogueBox.vue";
import EvidencePanel from "./EvidencePanel.vue";
import TimerBar from "./TimerBar.vue";
import MicButton from "./MicButton.vue";

interface DiegoResponse {
  dialogue: string;
  emotion: string;
  contradictions: string[];
  facts: string[];
  confession: boolean;
  turn: number;
}

export default defineComponent({
  name: "GameScreen",
  components: { DialogueBox, EvidencePanel, TimerBar, MicButton },
  emits: ["verdict", "result"],

  data() {
    return {
      status: "listening" as string,
      playerText: "",
      diegoDialogue: "...",
      diegoEmotion: "calm",
      contradictions: [] as string[],
      facts: [] as string[],
      confession: false,
      turn: 0,
      secondsLeft: 600,
      timerInterval: null as ReturnType<typeof setInterval> | null,
      error: "",
      statusTimeout: null as ReturnType<typeof setTimeout> | null,
    };
  },

  mounted() {
    this.setupSocket();
    this.startTimer();
    this.initVAD();
  },

  beforeUnmount() {
    this.cleanup();
  },

  methods: {
    setupSocket() {
      const socket = getSocket();
      socket.connect();

      socket.on("status", (s: string) => {
        this.status = s;

        // Clear any pending safety timeout
        if (this.statusTimeout) {
          clearTimeout(this.statusTimeout);
          this.statusTimeout = null;
        }

        // Pause VAD while backend is processing, resume when listening
        if (s === "listening") {
          if (!this.confession) resumeVAD();
        } else {
          pauseVAD();
          // Safety net: if stuck in transcribing/thinking for 35s, recover
          this.statusTimeout = setTimeout(() => {
            if (this.status !== "listening") {
              this.status = "listening";
              this.error = "Response timed out — try again.";
              setTimeout(() => { this.error = ""; }, 4000);
              if (!this.confession) resumeVAD();
            }
          }, 35000);
        }
      });

      socket.on("player_text", (text: string) => {
        this.playerText = text;
      });

      socket.on("diego_response", (data: DiegoResponse) => {
        this.diegoDialogue = data.dialogue;
        this.diegoEmotion = data.emotion;
        this.contradictions = data.contradictions;
        this.facts = data.facts;
        this.confession = data.confession;
        this.turn = data.turn;

        // Stop capturing audio once Diego confesses
        if (data.confession) {
          pauseVAD();
        }
      });

      socket.on("error", (msg: string) => {
        this.error = msg;
        // Clear error after a few seconds
        setTimeout(() => {
          this.error = "";
        }, 5000);
      });

      socket.on("case_result", (result) => {
        this.$emit("result", result);
      });
    },

    async initVAD() {
      try {
        await startVAD((audio: Float32Array) => {
          // Don't send audio if game is over (confession or time up)
          if (this.confession || this.secondsLeft <= 0) return;

          // Skip clips shorter than ~0.8s at 16kHz — likely noise, not speech
          const MIN_SAMPLES = 16000 * 0.8;
          if (audio.length < MIN_SAMPLES) return;

          const wav = float32ToWav(audio);
          const socket = getSocket();
          socket.emit("player_audio", wav);
        });
      } catch (err) {
        this.error = "Microphone access denied or VAD failed to initialize.";
        console.error("VAD init error:", err);
      }
    },

    startTimer() {
      this.timerInterval = setInterval(() => {
        this.secondsLeft--;
        if (this.secondsLeft <= 0) {
          this.timeUp();
        }
      }, 1000);
    },

    timeUp() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }
      pauseVAD();
      this.$emit("verdict");
    },

    endInterrogation() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }
      pauseVAD();
      this.$emit("verdict");
    },

    cleanup() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
      }
      if (this.statusTimeout) {
        clearTimeout(this.statusTimeout);
      }
      destroyVAD();
      const socket = getSocket();
      socket.off("status");
      socket.off("player_text");
      socket.off("diego_response");
      socket.off("error");
      socket.off("case_result");
      // Don't disconnect — VerdictScreen needs the same session & game state
    },
  },
});
</script>

<template>
  <div class="game-screen">
    <!-- Top bar: timer + end button -->
    <div class="top-bar">
      <TimerBar :seconds-left="secondsLeft" />
      <button class="end-btn" @click="endInterrogation">END INTERROGATION</button>
    </div>

    <!-- Main area: dialogue + evidence -->
    <div class="main-area">
      <div class="dialogue-area">
        <!-- Player's transcribed text -->
        <div class="player-bubble" v-if="playerText">
          <DialogueBox speaker="DETECTIVE (YOU)" :text="playerText" />
        </div>

        <!-- Diego's response -->
        <div class="diego-bubble">
          <DialogueBox
            :speaker="'DIEGO FONSECA — [' + diegoEmotion.toUpperCase() + ']'"
            :text="diegoDialogue"
          />
        </div>

        <!-- Mic status -->
        <MicButton :status="status" />

        <!-- Confession banner -->
        <div class="confession-banner" v-if="confession">
          DIEGO HAS CONFESSED!
        </div>

        <!-- Error display -->
        <div class="error" v-if="error">{{ error }}</div>
      </div>

      <div class="evidence-area">
        <EvidencePanel :contradictions="contradictions" :facts="facts" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-screen {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: 1rem;
  gap: 1rem;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.top-bar > *:first-child {
  flex: 1;
}

.end-btn {
  font-family: "Courier New", monospace;
  font-size: 0.8rem;
  padding: 0.4rem 1rem;
  background: transparent;
  color: #e74c3c;
  border: 1px solid #e74c3c;
  cursor: pointer;
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.end-btn:hover {
  background: #e74c3c;
  color: #fff;
}

.main-area {
  display: flex;
  gap: 1rem;
  flex: 1;
}

.dialogue-area {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.evidence-area {
  flex: 1;
  min-width: 250px;
}

.confession-banner {
  background: #e74c3c;
  color: #fff;
  text-align: center;
  padding: 0.5rem;
  font-weight: bold;
  letter-spacing: 0.15em;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.error {
  color: #e74c3c;
  font-size: 0.85rem;
  padding: 0.5rem;
  background: rgba(231, 76, 60, 0.1);
  border: 1px solid #e74c3c;
}
</style>
