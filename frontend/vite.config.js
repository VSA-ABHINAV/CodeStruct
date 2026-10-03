import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import process from 'node:process'
import { applicationVersion } from './version.config.js'

// https://vite.dev/config/
export default defineConfig({
  base: process.env.CODESTRUCT_FRONTEND_BASE || '/',
  define: { __CODESTRUCT_VERSION__: JSON.stringify(applicationVersion) },
  plugins: [react()],
  server: {
    watch: {
      ignored: ['**/bun.lock', '**/.git/**'],
    },
    proxy: {
      '/api': process.env.CODESTRUCT_BACKEND_URL || 'http://127.0.0.1:8000',
    },
  },
})
