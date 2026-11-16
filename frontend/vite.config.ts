import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/design-dist/' : '/',
  server: { proxy: { '/api/': process.env.FRONTEND_API_UPSTREAM || 'http://127.0.0.1:8080' } },
  build: {
    outDir: 'design-dist',
    rolldownOptions: { input: { live: fileURLToPath(new URL('./index.html', import.meta.url)), preview: fileURLToPath(new URL('./preview.html', import.meta.url)), geo: fileURLToPath(new URL('./geo.html', import.meta.url)) } },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/design/**/*.test.{ts,tsx}'],
    setupFiles: ['tests/design/setup.ts'],
  },
}));
