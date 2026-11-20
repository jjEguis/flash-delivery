import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/design-browser',
  fullyParallel: true,
  workers: process.env.CI ? 2 : 4,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure' },
  webServer: {
    command: 'npx vite --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174/preview.html',
    reuseExistingServer: false,
    timeout: 20000,
  },
});
