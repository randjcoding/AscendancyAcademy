import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = 'http://127.0.0.1:8030'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/print': backend,
      '/static': backend,
      '/documents/inline': backend,
      '/documents/download': backend,
      '/teacher/read-pages': backend,
    },
  },
})
