import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import { viteStaticCopy } from 'vite-plugin-static-copy'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    viteStaticCopy({
      targets: [
        {
          src: 'node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js',
          dest: './',
        },
        {
          src: 'node_modules/@ricky0123/vad-web/dist/silero_vad_v5.onnx',
          dest: './',
        },
        {
          src: 'node_modules/@ricky0123/vad-web/dist/silero_vad_legacy.onnx',
          dest: './',
        },
        {
          src: 'node_modules/onnxruntime-web/dist/*.wasm',
          dest: './',
        },
        {
          src: 'node_modules/onnxruntime-web/dist/*.mjs',
          dest: './',
        },
      ],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  // Required headers for SharedArrayBuffer (used by ONNX WASM threads)
  server: {
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "credentialless",
    },
  },
})
