import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Django serves the built app: index.html for every /app/* URL (config/spa.py),
// and the JS/CSS bundles as static files from /static/spa/.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/static/spa/' : '/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../static/spa',
    emptyOutDir: true,
  },
  server: {
    // In development the app runs on Vite (http://localhost:5173/app/) and
    // everything that isn't the app or Vite's own files goes to Django: the
    // API and the classic pages the sidebar still links to.
    //
    // changeOrigin stays false so Django sees the browser's Host
    // (localhost:5173), which must match the Origin header for its CSRF check.
    proxy: {
      '^/(?!app(?:/|$)|@|src/|node_modules/)': {
        target: process.env.DJANGO_ORIGIN ?? 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
  },
}))
