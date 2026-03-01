// Captures raw PCM audio from the microphone via AudioWorklet.
// Exposes the MediaStream so VAD can share the same mic.

let audioContext: AudioContext | null = null;
let mediaStream: MediaStream | null = null;
let workletNode: AudioWorkletNode | null = null;
let sourceNode: MediaStreamAudioSourceNode | null = null;
let chunkCallback: ((chunk: ArrayBuffer) => void) | null = null;

export async function initAudioStream(): Promise<MediaStream> {
  if (mediaStream) return mediaStream;

  // Get mic access — 16kHz mono to match Voxtral's expected format
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: 16000,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });

  // AudioContext at 16kHz so the worklet receives 16kHz samples directly
  audioContext = new AudioContext({ sampleRate: 16000 });

  // Register the PCM worklet processor
  await audioContext.audioWorklet.addModule("/pcm-worklet.js");

  // Connect: mic → worklet
  sourceNode = audioContext.createMediaStreamSource(mediaStream);
  workletNode = new AudioWorkletNode(audioContext, "pcm-processor");

  // Receive Int16 PCM chunks from the worklet
  workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
    if (chunkCallback) {
      chunkCallback(e.data);
    }
  };

  sourceNode.connect(workletNode);
  // AudioWorklet processes data as long as it has an input connection — no need to connect
  // to destination. NOT connecting avoids hearing our own mic audio (feedback).

  return mediaStream;
}

export function onAudioChunk(callback: (chunk: ArrayBuffer) => void): void {
  chunkCallback = callback;
}

export function stopAudioChunks(): void {
  chunkCallback = null;
}

export function destroyAudioStream(): void {
  chunkCallback = null;

  if (workletNode) {
    workletNode.port.postMessage("stop");
    workletNode.disconnect();
    workletNode = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
}
