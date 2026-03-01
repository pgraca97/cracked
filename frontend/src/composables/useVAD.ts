import { MicVAD } from "@ricky0123/vad-web";

let vadInstance: MicVAD | null = null;

// Starts VAD with an external MediaStream (shared with AudioWorklet).
// Fires onSpeechStart/onSpeechEnd callbacks — no longer sends audio data.
export async function startVAD(
  stream: MediaStream,
  callbacks: {
    onSpeechStart: () => void;
    onSpeechEnd: () => void;
  }
): Promise<void> {
  if (vadInstance) {
    vadInstance.start();
    return;
  }

  vadInstance = await MicVAD.new({
    getStream: () => Promise.resolve(stream),
    baseAssetPath: "/",
    onnxWASMBasePath: "/",
    positiveSpeechThreshold: 0.8,
    negativeSpeechThreshold: 0.3,
    minSpeechMs: 500,
    redemptionMs: 1500,
    onSpeechStart() {
      callbacks.onSpeechStart();
    },
    onSpeechEnd() {
      // We don't need the audio buffer anymore — AudioWorklet streams it directly
      callbacks.onSpeechEnd();
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
