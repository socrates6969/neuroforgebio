// CI-ONLY end-to-end acceptance for BUILD-GUIDE 3.8: upload a synthetic fixture, run a pipeline, open
// the lineage and see raw -> recording -> run -> artifact. Also: zero CSP violations, same-origin
// requests only, no cookies or web storage.
import { expect, test } from '@playwright/test';
import { FIXTURE_EDF, seed, signIn, watchCsp } from './util';

test('upload -> run -> lineage shows raw_file -> recording -> run -> artifact', async ({
  page,
  request,
}) => {
  const s = await seed(request);
  const cspViolations = await watchCsp(page);
  const foreign: string[] = [];
  page.on('request', (r) => {
    if (new URL(r.url()).origin !== 'http://127.0.0.1:4173') foreign.push(r.url());
  });

  await signIn(page, 'scientist');

  // projects -> project -> dataset (in-app navigation: a reload would end the in-memory session)
  await page.getByRole('link', { name: s.projectName }).click();
  await page.getByRole('link', { name: s.datasetName }).click();
  await page.getByText(`Subject ${s.subjectLabel}`).click();
  await page.getByLabel(/Upload a recording file/).setInputFiles(FIXTURE_EDF);
  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByText(/Upload converted: 1 recording/)).toBeVisible({ timeout: 180_000 });

  // recording viewer (pyramid window read, canvas plot)
  await page.getByRole('link', { name: /Open recording/ }).click();
  await expect(page.getByRole('heading', { name: 'Signal viewer' })).toBeVisible();
  await expect(page.getByRole('img', { name: /Signal plot, \d+ channels/ })).toBeVisible();
  await page.getByLabel('Window [s]').selectOption('60');
  await expect(page.getByText(/pyramid level [1-9]/)).toBeVisible();

  // run a published pipeline
  await page.getByLabel(/Run pipeline/).fill(s.pipelineRef);
  await page.getByRole('button', { name: 'Start run' }).click();
  await expect(page.getByText('succeeded', { exact: true })).toBeVisible({ timeout: 300_000 });
  await expect(page.getByRole('table', { name: 'Run artifacts' })).toBeVisible();

  // lineage: raw -> recording -> run -> artifact, ranks strictly increasing along the flow
  await page.getByRole('link', { name: 'Open lineage' }).click();
  await expect(page.getByTestId('flow')).toHaveText(/raw_file.*recording.*run.*artifact/);
  const rankOf = async (type: string) =>
    Number(
      await page.locator(`[role=option][data-type="${type}"]`).first().getAttribute('data-rank'),
    );
  const ranks = await Promise.all(['raw_file', 'recording', 'run', 'artifact'].map(rankOf));
  expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
  expect(new Set(ranks).size).toBe(4);

  // keyboard navigation of the node list
  const list = page.getByRole('listbox', { name: /Nodes/ });
  await list.focus();
  await page.keyboard.press('End');
  await expect(page.locator('[role=option][aria-selected=true]')).toHaveAttribute(
    'data-type',
    'artifact',
  );

  // security properties of the whole session
  expect(await cspViolations()).toEqual([]);
  expect(foreign).toEqual([]);
  expect(await page.context().cookies()).toEqual([]);
  const storage = await page.evaluate(() => ({
    local: window.localStorage.length,
    session: window.sessionStorage.length,
    isolated: window.crossOriginIsolated,
  }));
  expect(storage).toEqual({ local: 0, session: 0, isolated: true });
});

test('a reload ends the session (tokens are memory-only)', async ({ page }) => {
  await signIn(page, 'viewer');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

test('role-based hiding: a viewer gets no create or run controls', async ({ page, request }) => {
  const s = await seed(request);
  await signIn(page, 'viewer');
  await expect(page.getByLabel('New project')).toHaveCount(0);
  await page.getByRole('link', { name: s.projectName }).click();
  await expect(page.getByLabel('New dataset')).toHaveCount(0);
  await page.getByRole('link', { name: s.datasetName }).click();
  await page.getByText(`Subject ${s.subjectLabel}`).click();
  await expect(page.getByLabel(/Upload a recording file/)).toHaveCount(0);
});

test('the built console blocks an injected inline script (CSP enforced)', async ({ page }) => {
  const violations = await watchCsp(page);
  await page.goto('/');
  await page
    .evaluate(() => {
      const s = document.createElement('script');
      s.textContent = 'window.__pwned = true';
      document.body.appendChild(s);
    })
    .catch(() => undefined); // Trusted Types may already throw on textContent of a script
  expect(
    await page.evaluate(() => (window as unknown as { __pwned?: boolean }).__pwned),
  ).toBeUndefined();
  expect((await violations()).length).toBeGreaterThan(0);
});
