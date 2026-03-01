import { MicVAD } from "@ricky0123/vad-web";

let vadInstance: MicVAD | null = null;

// Starts VAD. Calls onSpeechEnd with a WAV blob when the user stops talking.
export async function startVAD(
  onSpeechEnd: (audio: Float32Array) => void
): Promise<void> {
  if (vadInstance) {
    vadInstance.start();
    return;
  }

  vadInstance = await MicVAD.new({
    baseAssetPath: "/",
    onnxWASMBasePath: "/",
    // Raise speech threshold so desk knocks, dog barks, vacuum, etc. don't trigger
    positiveSpeechThreshold: 0.8,
    negativeSpeechThreshold: 0.3,
    // Discard audio shorter than ~0.5s — allows short follow-ups like "Are you sure?"
    // while still filtering out coughs and knocks
    minSpeechMs: 500,
    // Wait 1.5s of silence before deciding speech ended — users ask long multi-clause questions
    redemptionMs: 1500,
    onSpeechEnd(audio: Float32Array) {
      onSpeechEnd(audio);
    },
  });

  vadInstance.start();
}

export function pauseVAD(): void {
  vadInstance?.pause();
}

export function resumeVAD(): void {
  vadInstance?.start();
}

export function destroyVAD(): void {
  vadInstance?.destroy();
  vadInstance = null;
}

// Encode Float32Array (PCM samples at 16kHz from VAD) into a WAV ArrayBuffer
export function float32ToWav(samples: Float32Array, sampleRate = 16000): ArrayBuffer {
  const numChannels = 1;
  const bytesPerSample = 2; // 16-bit
  const dataLength = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataLength);
  const view = new DataView(buffer);

  // RIFF header
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataLength, true);
  writeString(view, 8, "WAVE");

  // fmt chunk
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * numChannels * bytesPerSample, true);
  view.setUint16(32, numChannels * bytesPerSample, true);
  view.setUint16(34, bytesPerSample * 8, true);

  // data chunk
  writeString(view, 36, "data");
  view.setUint32(40, dataLength, true);

  // PCM samples — clamp to [-1, 1] and convert to 16-bit int
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const raw: number = samples[i] as number;
    const s = Math.max(-1, Math.min(1, raw));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return buffer;
}

function writeString(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}
