// Playwright configuration

import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30000,
  expect: {
    timeout: 5000
  },
  reporter: 'list',
  use: {
    baseURL: 'https://api.example.com/v1',
    trace: 'on-first-retry'
  }
});
