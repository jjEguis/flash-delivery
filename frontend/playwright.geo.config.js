import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./tests/geo-browser', fullyParallel:true, workers:process.env.CI?2:4,
  retries:0, reporter:'list', use:{baseURL:'http://127.0.0.1:5175',trace:'retain-on-failure'},
  webServer:{command:'npx vite --host 127.0.0.1 --port 5175 --strictPort',
    env:{VITE_GEO_SIMULATOR:'true',FRONTEND_API_UPSTREAM:'http://127.0.0.1:1'},url:'http://127.0.0.1:5175/geo.html',reuseExistingServer:false,timeout:20000},
});
