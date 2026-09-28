import type { Page, Request, TestInfo } from '@playwright/test';

export const PAGES = [
  '/',
  '/platform/',
  '/governance/',
  '/sdks/',
  '/security/',
  '/pricing/',
  '/law-tracker/',
  '/playground/',
  '/interface/',
  '/arena/',
  '/research/',
  '/research/somatosensory-closed-loop/',
  '/docs/',
  '/docs/api/',
  '/docs/changelog/',
  '/docs/python-sdk/',
  '/docs/c-abi/',
  '/docs/quickstart/file-ingest/',
  '/docs/quickstart/lineage-export/',
  '/docs/quickstart/pipeline-run/',
  '/docs/quickstart/streaming/',
  '/legal/privacy/',
  '/legal/terms/',
  '/legal/cookies/',
  '/legal/company/',
  '/no/security/',
  '/no/legal/privacy/',
  '/no/legal/terms/',
  '/no/legal/cookies/',
  '/no/legal/company/',
  '/investors/',
  '/no/platform/',
  '/no/governance/',
  '/no/sdks/',
  '/no/pricing/',
  '/gallery/',
  '/404.html',
];
export const WIDTHS = [360, 768, 1440] as const;
export const THIRD_PARTY =
  /jsdelivr|googleapis|gstatic|cdnjs|unpkg|googletagmanager|google-analytics/i;

export const themeOf = (info: TestInfo) => info.project.name as 'clinical' | 'cosmos';

/** Collects every request; `three` = JS responses whose body contains a three.js signature. */
export function recordNetwork(page: Page) {
  const log: { url: string; t: number; three: boolean }[] = [];
  const external: string[] = [];
  const t0 = Date.now();
  page.on('request', (r: Request) => {
    const u = new URL(r.url());
    if (u.hostname !== '127.0.0.1' && u.protocol.startsWith('http')) external.push(r.url());
  });
  page.on('response', async (res) => {
    const url = res.url();
    let three = false;
    if (url.endsWith('.js')) {
      try {
        three = /WebGLRenderer|BufferGeometry/.test(await res.text());
      } catch {
        /* body unavailable */
      }
    }
    log.push({ url, t: Date.now() - t0, three });
  });
  return { log, external };
}

/** Fails the test on uncaught errors and console errors (incl. CSP violations). */
export function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`console: ${m.text()}`);
  });
  return errors;
}
