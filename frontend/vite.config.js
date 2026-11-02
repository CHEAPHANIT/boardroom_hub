import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The dev server forwards every /api call to the Flask API on port 5000.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true }
    }
  }
})
