// Helpers for the CI-only console e2e tests.
import { expect, type APIRequestContext, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));

export const ROOT = resolve(HERE, '..', '..', '..');
export const FIXTURE_EDF = resolve(HERE, '.out', 'synth-seed3.edf');
const PIPELINE_JSON = resolve(
  ROOT,
  'services/workers/steps/nf_steps/nf_steps/pipelines/eeg-resample-features.json',
);

/** Access token straight from the mock IdP (MOCK_IDP_TEST_MINT=1), to seed data via the public API. */
export async function mint(request: APIRequestContext, roles: string): Promise<string> {
  const r = await request.post('/mock-idp/test/mint', { form: { roles } });
  expect(r.ok()).toBeTruthy();
  return (await r.json()).access_token as string;
}

export async function post<T>(
  request: APIRequestContext,
  token: string,
  path: string,
  data: unknown,
): Promise<T> {
  const r = await request.post(path, { data, headers: { Authorization: `Bearer ${token}` } });
  expect(r.status(), `${path}: ${await r.text()}`).toBeLessThan(300);
  return (await r.json()) as T;
}

export interface Seed {
  projectName: string;
  datasetName: string;
  subjectLabel: string;
  sessionLabel: string;
  pipelineRef: string;
  datasetId: string;
  subjectId: string;
}

/** Project -> dataset -> subject -> session, and the published pipeline, through the API as admin. */
export async function seed(request: APIRequestContext): Promise<Seed> {
  const token = await mint(request, 'admin');
  const tag = Date.now().toString(36);
  const projectName = `e2e-project-${tag}`;
  const datasetName = `e2e-dataset-${tag}`;
  const subjectLabel = `S-${tag}`;
  const sessionLabel = `ses-${tag}`;
  const p = await post<{ id: string }>(request, token, '/v1/projects', { name: projectName });
  const d = await post<{ id: string }>(request, token, `/v1/projects/${p.id}/datasets`, {
    name: datasetName,
  });
  const s = await post<{ id: string }>(request, token, `/v1/datasets/${d.id}/subjects`, {
    label: subjectLabel,
  });
  await post(request, token, `/v1/subjects/${s.id}/sessions`, { label: sessionLabel });
  const spec = JSON.parse(readFileSync(PIPELINE_JSON, 'utf8'));
  await post(request, token, '/v1/pipelines', spec);
  return {
    projectName,
    datasetName,
    subjectLabel,
    sessionLabel,
    pipelineRef: `${spec.meta.name}@${spec.meta.version}`,
    datasetId: d.id,
    subjectId: s.id,
  };
}

/** Popup login through the mock IdP's role form. */
export async function signIn(page: Page, role: string): Promise<void> {
  await page.goto('/');
  const popupP = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const popup = await popupP;
  await popup.getByLabel('Sign in as').selectOption(role);
  await popup.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
}

/** Collect CSP violations reported in the page (securitypolicyviolation events). */
export async function watchCsp(page: Page): Promise<() => Promise<string[]>> {
  await page.addInitScript(() => {
    (window as unknown as { __csp: string[] }).__csp = [];
    document.addEventListener('securitypolicyviolation', (e) =>
      (window as unknown as { __csp: string[] }).__csp.push(
        `${e.violatedDirective} ${e.blockedURI}`,
      ),
    );
  });
  const fromConsole: string[] = [];
  page.on('console', (m) => {
    if (/Content Security Policy|Trusted Type/i.test(m.text())) fromConsole.push(m.text());
  });
  return async () => [
    ...fromConsole,
    ...((await page.evaluate(
      () => (window as unknown as { __csp?: string[] }).__csp ?? [],
    )) as string[]),
  ];
}
