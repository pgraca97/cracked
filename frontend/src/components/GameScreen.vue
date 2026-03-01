<script lang="ts">
import { defineComponent } from "vue";
import { getSocket } from "../composables/useSocket";
import { startVAD, pauseVAD, resumeVAD, destroyVAD, float32ToWav } from "../composables/useVAD";
import { playOneShot, startLoop, stopAllLoops, setMuted } from "../composables/useSounds";
import DialogueBox from "./DialogueBox.vue";
import EvidencePanel from "./EvidencePanel.vue";
import MicButton from "./MicButton.vue";

interface DiegoResponse {
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
  emits: ["verdict", "quit"],

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
      audioMuted: false,
      currentAudio: null as HTMLAudioElement | null,
      pendingDialogue: null as DiegoResponse | null,
      audioFallbackTimer: null as ReturnType<typeof setTimeout> | null,
      confessionTimer: null as ReturnType<typeof setTimeout> | null,
      typewriterSpeed: 25,
    };
  },

  mounted() {
    this.setupSocket();
    this.startTimer();
    this.initVAD();
    startLoop("ambientHum");
  },

  beforeUnmount() {
    this.cleanup();
  },

  watch: {
    secondsLeft(val: number) {
      if (val === 60) {
        startLoop("tickingLoop");
      }
    },
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
          // Safety net: if stuck in transcribing/thinking for 60s, recover
          this.statusTimeout = setTimeout(() => {
            if (this.status !== "listening") {
              this.status = "listening";
              this.error = "Response timed out - try again.";
              setTimeout(() => { this.error = ""; }, 4000);
              if (!this.confession) resumeVAD();
            }
          }, 60000);
        }
      });

      socket.on("player_text", (text: string) => {
        this.playerText = text;
      });

      socket.on("diego_response", (data: DiegoResponse) => {
        // Fire piano hit immediately - before state update to beat Vue's render cycle
        if (data.contradictions.length > this.contradictions.length) {
          playOneShot("pianoHit");
        }

        // Update game state immediately (evidence panel, emotion label, etc.)
        this.diegoEmotion = data.emotion;
        this.contradictions = data.contradictions;
        this.facts = data.facts;
        this.confession = data.confession;
        this.turn = data.turn;

        if (data.confession) {
          pauseVAD();
          // Auto-advance to verdict after a delay so the player can read the confession
          this.confessionTimer = setTimeout(() => {
            this.endInterrogation();
          }, 6000);
        }

        // Stop any audio from the previous turn
        if (this.currentAudio) {
          this.currentAudio.pause();
          this.currentAudio = null;
        }

        if (!data.tts_enabled || this.audioMuted) {
          // TTS is off or muted - show text immediately, no waiting
          this.typewriterSpeed = 25;
          this.diegoDialogue = data.dialogue;
        } else {
          // Clear old dialogue while we wait for audio - shows "..." as a loading state
          this.diegoDialogue = "...";
          // Hold the dialogue text - wait for audio to arrive so we can sync them
          this.pendingDialogue = data;
          this.audioFallbackTimer = setTimeout(() => {
            // Audio didn't arrive in time (TTS failed) - show text anyway
            if (this.pendingDialogue) {
              this.typewriterSpeed = 25;
              this.diegoDialogue = this.pendingDialogue.dialogue;
              this.pendingDialogue = null;
            }
          }, 8000);
        }
      });

      socket.on("diego_audio", (data: ArrayBuffer) => {
        // Cancel the fallback timer - audio arrived
        if (this.audioFallbackTimer) {
          clearTimeout(this.audioFallbackTimer);
          this.audioFallbackTimer = null;
        }

        const blob = new Blob([data], { type: "audio/mpeg" });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        this.currentAudio = audio;

        audio.onended = () => {
          URL.revokeObjectURL(url);
          this.currentAudio = null;
        };

        // Wait for audio metadata to load so we know the duration
        audio.onloadedmetadata = () => {
          // Match typewriter speed to audio duration
          if (this.pendingDialogue && audio.duration > 0) {
            const charCount = this.pendingDialogue.dialogue.length;
            // Leave a small buffer so typewriter finishes just before audio ends
            this.typewriterSpeed = Math.max(10, Math.floor((audio.duration * 950) / charCount));
          }

          // Start both at the same time
          if (this.pendingDialogue) {
            this.diegoDialogue = this.pendingDialogue.dialogue;
            this.pendingDialogue = null;
          }

          if (!this.audioMuted) {
            audio.play().catch((err) => {
              console.error("Audio playback failed:", err);
              URL.revokeObjectURL(url);
              this.currentAudio = null;
            });
          }
        };

        // If metadata fails to load, show text anyway
        audio.onerror = () => {
          console.error("Audio load failed");
          URL.revokeObjectURL(url);
          this.currentAudio = null;
          if (this.pendingDialogue) {
            this.typewriterSpeed = 25;
            this.diegoDialogue = this.pendingDialogue.dialogue;
            this.pendingDialogue = null;
          }
        };
      });

      socket.on("error", (msg: string) => {
        this.error = msg;
        // Clear error after a few seconds
        setTimeout(() => {
          this.error = "";
        }, 5000);
      });

    },

    async initVAD() {
      try {
        await startVAD((audio: Float32Array) => {
          // Don't send audio if game is over (confession or time up)
          if (this.confession || this.secondsLeft <= 0) return;

          // Skip clips shorter than ~0.8s at 16kHz - likely noise, not speech
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

    quitGame() {
      this.cleanup();
      getSocket().disconnect();
      this.$emit("quit");
    },

    cleanup() {
      if (this.timerInterval) {
        clearInterval(this.timerInterval);
      }
      if (this.statusTimeout) {
        clearTimeout(this.statusTimeout);
      }
      if (this.audioFallbackTimer) {
        clearTimeout(this.audioFallbackTimer);
      }
      if (this.confessionTimer) {
        clearTimeout(this.confessionTimer);
      }
      if (this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
      }
      stopAllLoops();
      destroyVAD();
      const socket = getSocket();
      socket.off("status");
      socket.off("player_text");
      socket.off("diego_response");
      socket.off("diego_audio");
      socket.off("error");
      // Don't disconnect - VerdictScreen needs the same session & game state
    },

    toggleMute() {
      this.audioMuted = !this.audioMuted;
      setMuted(this.audioMuted);
      // Stop any currently playing TTS audio when muting
      if (this.audioMuted && this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
      }
    },
  },
});
</script>

<template>
  <div class="game-screen" :class="{ 'cursor-wait': status === 'transcribing' || status === 'thinking' }">
    <div class="game-center">

      <!-- Main dialogue box -->
      <div class="main-box">
        <div class="main-box-header">
          <span class="timer" :class="{ urgent: secondsLeft <= 60 }">{{ timerDisplay }}</span>
          <span class="case-title">CASE: THE MUSEUM THEFT</span>
          <button class="quit-btn" @click="quitGame" aria-label="Abandon case and return to title">QUIT</button>
        </div>
        <div class="main-box-body" aria-live="polite">
          <div class="player-dialogue">
            <DialogueBox
              speaker="DETECTIVE (YOU)"
              :text="playerText || '...'"
              :instant="true"
              portrait="/detective.png"
            />
          </div>
          <div class="diego-dialogue">
            <DialogueBox
              speaker="DIEGO FONSECA"
              :text="diegoDialogue"
              :speed="typewriterSpeed"
              portrait="/diego.png"
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
          <button class="mute-btn" @click="toggleMute" :aria-label="audioMuted ? 'Unmute audio' : 'Mute audio'">
            {{ audioMuted ? 'AUDIO OFF' : 'AUDIO ON' }}
          </button>
          <button
            class="end-btn"
            :disabled="contradictions.length < 1"
            @click="endInterrogation"
            aria-label="End interrogation"
          >END INTERROGATION</button>
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

/* Main dialogue box - pixel frame */
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

.quit-btn {
  font-family: inherit;
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  background: transparent;
  color: #555;
  border: 1px solid #555;
  letter-spacing: 0.1em;
}

.quit-btn:hover {
  color: #999;
  border-color: #999;
}

.quit-btn:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.main-box-body {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 200px;
}

/* Accent colours - border + speaker name always match */
.player-dialogue :deep(.dialogue-box) {
  --accent: #5dade2;
}

.diego-dialogue :deep(.dialogue-box) {
  --accent: #f0c040;
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
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.end-btn:disabled {
  opacity: 0.3;
}

.end-btn:hover:not(:disabled) {
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
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.mute-btn:hover {
  background: #999;
  color: #1a1a2e;
}

/* Focus visible - WCAG 2.2 */
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
