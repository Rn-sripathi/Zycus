import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The production build is emitted straight into the backend package, so FastAPI
// serves the API and the UI from one origin as a single deployable unit.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
