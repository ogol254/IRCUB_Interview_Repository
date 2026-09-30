import {defineConfig,devices} from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',use:{baseURL:'http://localhost:5173',trace:'retain-on-failure'},projects:[{name:'tablet-chromium',use:{...devices['iPad Pro 11'],browserName:'chromium'}}],reporter:'list'});
