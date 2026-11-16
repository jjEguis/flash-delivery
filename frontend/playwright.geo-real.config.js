import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests/geo-real',workers:1,retries:0,timeout:90000,reporter:'list',
  use:{baseURL:'http://127.0.0.1:8080',trace:'off',screenshot:'off',video:'off'},
});
