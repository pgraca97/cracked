// Singleton sound manager - controls all game SFX with a global mute toggle.
// Sounds are preloaded once and reused across components.

type SoundName = "typewriterTick" | "pianoHit" | "tickingLoop" | "ambientHum";

interface LoopingSound {
  audio: HTMLAudioElement;
  playing: boolean;
}

const SOUND_FILES: Record<SoundName, string> = {
  typewriterTick: "/sounds/typewriter-tick.wav",
  pianoHit: "/sounds/dramatic-piano-hit.wav",
  tickingLoop: "/sounds/ticking-loop.wav",
  ambientHum: "/sounds/police-station-hum.wav",
};

// Volumes per sound (tweak to taste)
const VOLUMES: Record<SoundName, number> = {
  typewriterTick: 0.18,
  pianoHit: 0.7,
  tickingLoop: 0.5,
  ambientHum: 0.15,
};

let muted = false;
const loops: Partial<Record<SoundName, LoopingSound>> = {};

// Preloaded buffers for one-shot sounds
let tickPool: HTMLAudioElement[] = [];
const TICK_POOL_SIZE = 4;
let pianoHitPool: HTMLAudioElement | null = null;

function preload() {
  // Pool multiple tick elements so rapid typewriter doesn't clip
  for (let i = 0; i < TICK_POOL_SIZE; i++) {
    const a = new Audio(SOUND_FILES.typewriterTick);
    a.volume = VOLUMES.typewriterTick;
    a.preload = "auto";
    tickPool.push(a);
  }
  // Preload the piano hit so it plays instantly on contradiction
  pianoHitPool = new Audio(SOUND_FILES.pianoHit);
  pianoHitPool.volume = VOLUMES.pianoHit;
  pianoHitPool.preload = "auto";
}

// Also pre-buffer loop files so they're ready the moment the game screen mounts
function preloadLoops() {
  for (const name of ["ambientHum", "tickingLoop"] as SoundName[]) {
    if (loops[name]) continue;
    const a = new Audio(SOUND_FILES[name]);
    a.loop = true;
    a.volume = VOLUMES[name];
    a.preload = "auto";
    loops[name] = { audio: a, playing: false };
  }
}

let preloaded = false;
function ensurePreloaded() {
  if (!preloaded) {
    preloaded = true;
    preload();
  }
}

// Call this early (e.g. TitleScreen mounted) to buffer all audio before gameplay
export function preloadSounds() {
  ensurePreloaded();
  preloadLoops();
}

let tickIndex = 0;

// Play the typewriter tick once - caller is responsible for throttling frequency
export function playTick() {
  if (muted) return;
  ensurePreloaded();
  const a = tickPool[tickIndex % TICK_POOL_SIZE];
  tickIndex++;
  if (!a) return;
  a.currentTime = 0;
  a.volume = VOLUMES.typewriterTick;
  a.play().catch(() => { });
}

// Play a one-shot sound (piano hit) - uses preloaded audio for instant playback
export function playOneShot(name: SoundName) {
  if (muted) return;
  ensurePreloaded();
  if (name === "pianoHit" && pianoHitPool) {
    pianoHitPool.currentTime = 0;
    pianoHitPool.volume = VOLUMES.pianoHit;
    pianoHitPool.play().catch(() => { });
    return;
  }
  const a = new Audio(SOUND_FILES[name]);
  a.volume = VOLUMES[name];
  a.play().catch(() => { });
}

// Start a looping sound
export function startLoop(name: SoundName) {
  ensurePreloaded();
  const existing = loops[name];
  if (existing?.playing) return; // already playing

  const a = existing?.audio ?? new Audio(SOUND_FILES[name]);
  a.loop = true;
  a.volume = VOLUMES[name];
  loops[name] = { audio: a, playing: true };

  if (!muted) {
    a.play().catch(() => { });
  }
}

// Stop a looping sound
export function stopLoop(name: SoundName) {
  const entry = loops[name];
  if (!entry) return;
  entry.audio.pause();
  entry.audio.currentTime = 0;
  entry.playing = false;
}

// Stop all loops (cleanup on screen exit)
export function stopAllLoops() {
  for (const name of Object.keys(loops) as SoundName[]) {
    stopLoop(name);
  }
}

// Mute / unmute everything
export function setMuted(m: boolean) {
  muted = m;
  for (const entry of Object.values(loops)) {
    if (!entry) continue;
    if (m) {
      entry.audio.pause();
    } else if (entry.playing) {
      entry.audio.play().catch(() => { });
    }
  }
}

export function isMuted(): boolean {
  return muted;
}
