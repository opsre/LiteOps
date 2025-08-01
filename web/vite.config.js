import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8000,
    host: true,
    strictPort: true,
    cors: true,
    allowedHosts: [
      '0.0.0.0',
    ]
  }
})