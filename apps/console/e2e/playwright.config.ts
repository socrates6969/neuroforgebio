// CI-ONLY Playwright config for the console (BUILD-GUIDE 3.8). No browsers on the dev PC.
// Starts the one-process platform stack (e2e/stack.py: pgserver + API + worker) and the console server
// (e2e/serve.mjs: dist + mock IdP + /v1 proxy). Run: pnpm --filter @nf/console test:e2e after a build.
import { defineConfig, devices } from '@playwright/test';
import { delimiter, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));

const ROOT = resolve(HERE, '..', '..', '..');
const TENANT = '5e2e0000-0000-4000-8000-000000000001';
const PYTHONPATH = [
  'services/workers/runner',
  'services/workers/steps/nf_steps',
  'tools/synth',
].map((p) => resolve(ROOT, p));

export default defineConfig({
  testDir: '.',
  timeout: 10 * 60 * 1000,
  expect: { timeout: 15_000 },
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // uvicorn is not in uv.lock (the platform has no ASGI server dependency yet): pinned here.
      command:
        process.env.NF_E2E_STACK_CMD ??
        'uv run --locked --with uvicorn==0.35.0 python apps/console/e2e/stack.py',
      cwd: ROOT,
      url: 'http://127.0.0.1:8710/v1/health',
      timeout: 5 * 60 * 1000,
      reuseExistingServer: false,
      env: {
        PYTHONPATH: PYTHONPATH.join(delimiter),
        NF_E2E_TENANT: TENANT,
        NF_E2E_ISSUER: 'http://127.0.0.1:4173/mock-idp',
        OMP_NUM_THREADS: '1',
      },
    },
    {
      command: 'node e2e/serve.mjs',
      cwd: resolve(HERE, '..'),
      url: 'http://127.0.0.1:4173/',
      reuseExistingServer: false,
      env: { MOCK_IDP_TEST_MINT: '1', NF_E2E_TENANT: TENANT, PORT: '4173' },
    },
  ],
});
