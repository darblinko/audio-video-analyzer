import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The dev server proxies the REST API and the WebSocket to the FastAPI server, so the browser
// only talks to one origin. Override the target with AVA_API_URL when the API runs elsewhere.
const apiTarget = process.env.AVA_API_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
      '/ws': { target: apiTarget.replace(/^http/, 'ws'), ws: true },
    },
  },
});
