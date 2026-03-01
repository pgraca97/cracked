// AudioWorklet processor: captures raw PCM from the mic and sends Int16 chunks to the main thread.
// Runs in the audio rendering thread — must be lightweight (no allocations in process()).

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Buffer samples until we have enough for a chunk (~30ms at 16kHz = 480 samples)
    this._buffer = new Float32Array(480);
    this._writeIndex = 0;
    this._active = true;

    this.port.onmessage = (e) => {
      if (e.data === "stop") {
        this._active = false;
      }
    };
  }

  process(inputs) {
    if (!this._active) return false;

    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0]; // mono channel

    for (let i = 0; i < samples.length; i++) {
      this._buffer[this._writeIndex++] = samples[i];

      if (this._writeIndex >= this._buffer.length) {
        // Convert Float32 [-1, 1] to Int16 PCM (s16le) — matches Voxtral's expected format
        const pcm = new Int16Array(this._buffer.length);
        for (let j = 0; j < this._buffer.length; j++) {
          const s = Math.max(-1, Math.min(1, this._buffer[j]));
          pcm[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(pcm.buffer, [pcm.buffer]);
        this._buffer = new Float32Array(480);
        this._writeIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
