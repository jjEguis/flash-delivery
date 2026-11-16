import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests/geo-production',workers:1,retries:0,reporter:'list',
  use:{baseURL:'http://127.0.0.1:4176',trace:'retain-on-failure'},
  webServer:{command:'python3 server.py',env:{PORT:'4176',API_UPSTREAM:'http://127.0.0.1:1',OUTPUTS_FILE:'/not-provisioned/outputs.json'},
    url:'http://127.0.0.1:4176',reuseExistingServer:false,timeout:15000},
});
