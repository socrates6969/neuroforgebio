// Quality gate (BUILD-GUIDE 1.9), also runs in CI (.github/workflows/web-quality.yml).
// Runnable locally too, with Chromium already installed (`npx playwright install` only if missing
// -- ask before installing browsers on the shared dev machine, see WEB-PLAN.md rule 5): build both
// themes first (`pnpm run build`), then `pnpm run test:e2e`. Kept to workers: 1 / fullyParallel:
// false so it doesn't compete for RAM with other heavy jobs; get a slot from bci-queen before running.
// A strict CSP (script-src 'self') is sent by scripts/serve.mjs, so CSP violations fail tests too.
// snapshotPathTemplate includes {platform} (lead-approved 2026-09-27): pixel snapshots don't
// byte-match across OSes even on the same Chromium build (font hinting/anti-aliasing differ), so
// each platform gets its own path and a CI run on a different OS never compares against, or
// overwrites, another OS's baseline. Text-only pins (homepage-pin.spec.ts) also land under the
// platform segment for consistency, though their content itself is OS-independent.
import { defineConfig, devices } from '@playwright/test';

const PORTS = { clinical: 4411, cosmos: 4412 } as const;

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: 'disabled' } },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate:
    '{testDir}/__snapshots__/{projectName}/{platform}/{testFilePath}/{arg}{ext}',
  use: { ...devices['Desktop Chrome'], trace: 'retain-on-failure' },
  projects: (['clinical', 'cosmos'] as const).map((theme) => ({
    name: theme,
    use: { baseURL: `http://127.0.0.1:${PORTS[theme]}` },
    metadata: { theme },
  })),
  webServer: (['clinical', 'cosmos'] as const).map((theme) => ({
    command: `node scripts/serve.mjs dist/${theme} ${PORTS[theme]}`,
    url: `http://127.0.0.1:${PORTS[theme]}/`,
    reuseExistingServer: false,
    timeout: 30_000,
  })),
});
