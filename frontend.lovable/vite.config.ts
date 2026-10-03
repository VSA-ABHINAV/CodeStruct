import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  base: process.env.CODESTRUCT_FRONTEND_BASE || '/',
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { host: '127.0.0.1', port: 5173, proxy: {
    '/api/v1': process.env.CODESTRUCT_BACKEND_URL || 'http://127.0.0.1:8000',
  } },
});
