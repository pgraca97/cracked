<script lang="ts">
import { defineComponent } from "vue";
import { getSocket } from "../composables/useSocket";
import { initAudioStream, onAudioChunk, stopAudioChunks, destroyAudioStream } from "../composables/useAudioStream";
import { startVAD, pauseVAD, destroyVAD } from "../composables/useVAD";
import DialogueBox from "./DialogueBox.vue";
import EvidencePanel from "./EvidencePanel.vue";
import MicButton from "./MicButton.vue";

interface DiegoFullResponse {
  dialogue: string;
  emotion: string;
  contradictions: string[];
  facts: string[];
  confession: boolean;
  turn: number;
  tts_enabled: boolean;
}

export default defineComponent({
  name: "GameScreen",
  components: { DialogueBox, EvidencePanel, MicButton },
  emits: ["verdict", "result"],

  data() {
    return {
      // State machine: listening | player_speaking | processing | diego_speaking | confession
      gameState: "listening" as string,
      // For MicButton compatibility (maps to old status values)
      status: "listening" as string,
      playerText: "",
      diegoDialogue: "...",
      diegoEmotion: "calm",
      // true when Diego's dialogue is being streamed token-by-token
      diegoStreaming: false,
      contradictions: [] as string[],
      facts: [] as string[],
      confession: false,
      turn: 0,
      secondsLeft: 600,
      timerInterval: null as ReturnType<typeof setInterval> | null,
      error: "",
      audioMuted: false,
      currentAudio: null as HTMLAudioElement | null,
      // Whether we're actively streaming audio chunks to backend
      streamingAudio: false,
      // Tracks whether we've received the first transcription delta for this utterance
      _receivedFirstDelta: false,
    };
  },

  mounted() {
    this.setupSocket();
    this.startTimer();
    this.initAudio();
  },

  beforeUnmount() {
    this.cleanup();
  },

  computed: {
    timerDisplay(): string {
      const s = Math.max(0, this.secondsLeft);
      const m = String(Math.floor(s / 60)).padStart(2, "0");
      const sec = String(s % 60).padStart(2, "0");
      return `${m}:${sec}`;
    },
  },

  methods: {
    setupSocket() {
      const socket = getSocket();
      socket.connect();

      // State machine transitions from backend
      socket.on("state_change", (state: string) => {
        this.gameState = state;
        // Map to MicButton-compatible status
        if (state === "listening") {
          this.status = "listening";
        } else if (state === "player_speaking") {
          this.status = "listening"; // mic is active
        } else if (state === "processing") {
          this.status = "thinking";
        } else if (state === "diego_speaking") {
          this.status = "thinking";
        } else if (state === "confession") {
          this.status = "listening";
          this.confession = true;
          pauseVAD();
        }
      });

      // Real-time transcription deltas — words appear as the player speaks
      socket.on("transcription_delta", (data: { text: string }) => {
        // Clear previous text on first delta of a new utterance
        if (!this._receivedFirstDelta) {
          this.playerText = "";
          this._receivedFirstDelta = true;
        }
        this.playerText += data.text;
      });

      // Final transcription (end of player utterance)
      socket.on("transcription_done", (data: { full_text: string }) => {
        this.playerText = data.full_text;
      });

      // Streaming Diego tokens — dialogue appears word by word
      socket.on("diego_token", (data: { token: string }) => {
        // Ignore stale tokens arriving after barge-in
        if (this.gameState === "player_speaking") return;

        if (!this.diegoStreaming) {
          // First token — clear the placeholder and switch to streaming mode
          this.diegoDialogue = "";
          this.diegoStreaming = true;
        }
        this.diegoDialogue += data.token;
      });

      // Full Diego response — update game state (evidence, emotion, etc.)
      socket.on("diego_done", (data: DiegoFullResponse) => {
        this.diegoStreaming = false;
        this.diegoDialogue = data.dialogue;
        this.diegoEmotion = data.emotion;
        this.contradictions = data.contradictions;
        this.facts = data.facts;
        this.confession = data.confession;
        this.turn = data.turn;

        if (data.confession) {
          pauseVAD();
        }
      });

      // Diego was interrupted by barge-in
      socket.on("diego_interrupted", (data: { partial_dialogue: string }) => {
        this.diegoStreaming = false;
        // Keep whatever Diego managed to say
        this.diegoDialogue = data.partial_dialogue;
        // Stop any playing audio
        if (this.currentAudio) {
          this.currentAudio.pause();
          this.currentAudio = null;
        }
      });

      // TTS audio (if enabled)
      socket.on("diego_audio", (data: ArrayBuffer) => {
        if (this.audioMuted) return;

        const blob = new Blob([data], { type: "audio/mpeg" });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        this.currentAudio = audio;

        audio.onended = () => {
          URL.revokeObjectURL(url);
          this.currentAudio = null;
        };

        audio.play().catch((err) => {
          console.error("Audio playback failed:", err);
          URL.revokeObjectURL(url);
          this.currentAudio = null;
        });
      });

      socket.on("error", (msg: string) => {
        this.error = msg;
        setTimeout(() => { this.error = ""; }, 5000);
      });

      socket.on("case_result", (result) => {
        this.$emit("result", result);
      });
    },

    async initAudio() {
      try {
        // Initialize AudioWorklet and get the shared MediaStream
        const stream = await initAudioStream();

        // Set up audio chunk forwarding (inactive until speech starts)
        onAudioChunk((chunk: ArrayBuffer) => {
          if (!this.streamingAudio) return;
          const socket = getSocket();
          socket.volatile.emit("audio_chunk", chunk);
        });

        // Set up VAD with the shared MediaStream
        await startVAD(stream, {
          onSpeechStart: () => {
            if (this.confession || this.secondsLeft <= 0) return;

            const socket = getSocket();

            // Barge-in: player speaks while Diego is responding
            if (this.gameState === "diego_speaking") {
              socket.emit("barge_in");
              if (this.currentAudio) {
                this.currentAudio.pause();
                this.currentAudio = null;
              }
              this.diegoStreaming = false;
            }

            // Don't clear playerText here — wait until we get actual transcription
            // content to avoid the "empty detective box" flash on false VAD triggers
            this.diegoStreaming = false;
            this._receivedFirstDelta = false;

            // Start streaming audio chunks
            this.streamingAudio = true;
            socket.emit("speech_start");
          },

          onSpeechEnd: () => {
            if (this.confession || this.secondsLeft <= 0) return;

            // Stop streaming audio chunks
            this.streamingAudio = false;

            const socket = getSocket();
            socket.emit("speech_end");
          },
        });
      } catch (err) {
        this.error = "Microphone access denied or audio initialization failed.";
        console.error("Audio init error:", err);
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
      stopAudioChunks();
      this.streamingAudio = false;
      this.$emit("verdict");
    },

    endInterrogation() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }
      pauseVAD();
      stopAudioChunks();
      this.streamingAudio = false;
      this.$emit("verdict");
    },

    cleanup() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
      }
      if (this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
      }
      stopAudioChunks();
      this.streamingAudio = false;
      destroyVAD();
      destroyAudioStream();
      const socket = getSocket();
      socket.off("state_change");
      socket.off("transcription_delta");
      socket.off("transcription_done");
      socket.off("diego_token");
      socket.off("diego_done");
      socket.off("diego_interrupted");
      socket.off("diego_audio");
      socket.off("error");
      socket.off("case_result");
      // Don't disconnect — VerdictScreen needs the same session & game state
    },

    toggleMute() {
      this.audioMuted = !this.audioMuted;
      if (this.audioMuted && this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
      }
    },
  },
});
</script>

<template>
  <div class="game-screen">
    <div class="game-center">

      <!-- Main dialogue box -->
      <div class="main-box">
        <div class="main-box-header">
          <span class="timer" :class="{ urgent: secondsLeft <= 60 }">{{ timerDisplay }}</span>
          <span class="case-title">CASE: THE MUSEUM THEFT</span>
        </div>
        <div class="main-box-body" aria-live="polite">
          <div class="player-dialogue" v-if="playerText">
            <DialogueBox speaker="DETECTIVE (YOU)" :text="playerText" :instant="true" />
          </div>
          <div class="diego-dialogue">
            <DialogueBox
              :speaker="'DIOGO FONSECA — [' + diegoEmotion.toUpperCase() + ']'"
              :text="diegoDialogue"
              :streaming="diegoStreaming"
              :speed="25"
            />
          </div>
          <div class="confession-banner" v-if="confession" role="alert">DIOGO HAS CONFESSED!</div>
          <div class="error-msg" v-if="error" role="alert">{{ error }}</div>
        </div>
      </div>

      <!-- Evidence panels -->
      <div class="evidence-row">
        <EvidencePanel class="evidence-half" :facts="facts" :contradictions="[]" mode="facts" />
        <EvidencePanel class="evidence-half" :facts="[]" :contradictions="contradictions" mode="contradictions" />
      </div>

      <!-- Controls row -->
      <div class="controls-row">
        <MicButton :status="status" />
        <div class="action-buttons">
          <button class="mute-btn" @click="toggleMute" :aria-label="audioMuted ? 'Unmute voice' : 'Mute voice'">
            {{ audioMuted ? 'VOICE OFF' : 'VOICE ON' }}
          </button>
          <button class="end-btn" @click="endInterrogation" aria-label="End interrogation">END INTERROGATION</button>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.game-screen {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem 1rem;
}

.game-center {
  width: 100%;
  max-width: 960px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Main dialogue box — pixel frame */
.main-box {
  border: 14px solid transparent;
  border-image-source: url('/frame.webp');
  border-image-slice: 24;
  border-image-repeat: stretch;
  background: #16213e;
  image-rendering: pixelated;
}

.main-box-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #2c3e50;
}

.timer {
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.timer.urgent {
  color: #e74c3c;
}

.case-title {
  font-size: 0.85rem;
  color: #999;
  letter-spacing: 0.1em;
}

.main-box-body {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 200px;
}

/* Detective = blue accent, Diego = red accent */
.player-dialogue :deep(.speaker) {
  color: #5dade2;
}

.player-dialogue :deep(.dialogue-box) {
  border-color: #5dade2;
}

/* Evidence panels */
.evidence-row {
  display: flex;
  gap: 1rem;
}

.evidence-half {
  flex: 1;
  height: 180px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #444 transparent;
}

.evidence-half::-webkit-scrollbar {
  width: 4px;
}

.evidence-half::-webkit-scrollbar-track {
  background: transparent;
}

.evidence-half::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 2px;
}

.evidence-half::-webkit-scrollbar-thumb:hover {
  background: #666;
}

/* Controls row */
.controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 0.75rem;
}

.end-btn {
  font-family: inherit;
  font-size: 0.85rem;
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

.mute-btn {
  font-family: inherit;
  font-size: 0.85rem;
  padding: 0.4rem 1rem;
  background: transparent;
  color: #999;
  border: 1px solid #999;
  cursor: pointer;
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.mute-btn:hover {
  background: #999;
  color: #1a1a2e;
}

/* Focus visible — WCAG 2.2 */
.end-btn:focus-visible,
.mute-btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.confession-banner {
  background: #e74c3c;
  color: #fff;
  text-align: center;
  padding: 0.5rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.error-msg {
  color: #e74c3c;
  font-size: 0.85rem;
  padding: 0.5rem;
  background: rgba(231, 76, 60, 0.1);
  border: 1px solid #e74c3c;
}

@media (prefers-reduced-motion: reduce) {
  .confession-banner {
    animation: none;
  }
}
</style>
