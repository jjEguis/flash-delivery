import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  base: './',
  server: { proxy: { '/api': 'http://127.0.0.1:8080' } },
  build: {
    outDir: 'design-dist',
    rolldownOptions: { input: { preview: fileURLToPath(new URL('./preview.html', import.meta.url)), geo: fileURLToPath(new URL('./geo.html', import.meta.url)) } },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/design/**/*.test.{ts,tsx}'],
    setupFiles: ['tests/design/setup.ts'],
  },
});
