// CI-ONLY end-to-end acceptance for BUILD-GUIDE 6.6: the consent-taint scenario. A model is trained
// (registered) on a recording of a subject who then withdraws consent; the DeletionJob (5.5) flags
// the model version retrain_required; the console shows the flagged model with the reason (the
// deletion job) and its approved deployment as blocked. axe (WCAG 2.1 A/AA) on the model views.
// Synthetic data only (tools/synth fixture, AllowAllPolicy stack). axe is injected by Playwright, so
// this file bypasses the page CSP; console.spec.ts checks the CSP itself.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { FIXTURE_EDF, mint, post, seed, signIn } from './util';

test.use({ bypassCSP: true });

async function axe(page: Page, label: string) {
  const r = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(
    r.violations.map((v) => `${label}: ${v.id} (${v.nodes.length})`),
    label,
  ).toEqual([]);
}

async function getJson<T>(request: APIRequestContext, token: string, path: string): Promise<T> {
  const r = await request.get(path, { headers: { Authorization: `Bearer ${token}` } });
  expect(r.status(), `${path}: ${await r.text()}`).toBe(200);
  return (await r.json()) as T;
}

/** A minimal, structurally valid safetensors file (SEC-061: never deserialised by the platform). */
function safetensors(): string {
  const header = Buffer.from(
    JSON.stringify({ w: { dtype: 'F32', shape: [2], data_offsets: [0, 8] } }),
  );
  const len = Buffer.alloc(8);
  len.writeBigUInt64LE(BigInt(header.length));
  return Buffer.concat([len, header, Buffer.alloc(8)]).toString('base64');
}

const measurement = (method: string) => ({ method, metric: 'accuracy', value: 0.5 });

test('taint: a withdrawn subject flags the model; the console shows it with the reason', async ({
  page,
  request,
}) => {
  const s = await seed(request);
  const admin = await mint(request, 'admin');
  const scientist = await mint(request, 'scientist');
  const steward = await mint(request, 'data-steward');

  // consent record incl. model_training (SEC-146: registering a version needs it)
  const doc = await post<{ id: string }>(request, admin, '/v1/consent-documents', {
    name: `e2e-consent-${Date.now().toString(36)}`,
    version: '1',
    sha256: 'ef'.repeat(32),
  });
  await post(request, admin, `/v1/subjects/${s.subjectId}/consents`, {
    kind: 'grant',
    scopes: ['collection', 'processing', 'model_training'],
    document_id: doc.id,
  });

  // upload the synthetic fixture and run the published pipeline through the console
  await signIn(page, 'scientist');
  await page.getByRole('link', { name: s.projectName }).click();
  await page.getByRole('link', { name: s.datasetName }).click();
  await page.getByText(`Subject ${s.subjectLabel}`).click();
  await page.getByLabel(/Upload a recording file/).setInputFiles(FIXTURE_EDF);
  await page.getByRole('button', { name: 'Upload' }).click();
  await expect(page.getByText(/Upload converted: 1 recording/)).toBeVisible({ timeout: 180_000 });
  await page.getByRole('link', { name: /Open recording/ }).click();
  await page.getByLabel(/Run pipeline/).fill(s.pipelineRef);
  await page.getByRole('button', { name: 'Start run' }).click();
  await expect(page.getByText('succeeded', { exact: true })).toBeVisible({ timeout: 300_000 });
  const lineageHref = await page.getByRole('link', { name: 'Open lineage' }).getAttribute('href');
  const activity = /#\/lineage\/([0-9a-f-]{36})/.exec(lineageHref ?? '')?.[1];
  expect(activity, `run lineage link: ${lineageHref}`).toBeTruthy();

  // the run's input recording is the training input of the model
  const up = await getJson<{ nodes: Array<{ id: string; type: string }> }>(
    request,
    scientist,
    `/v1/provenance/${activity}/lineage?direction=up`,
  );
  const recordingNode = up.nodes.find((n) => n.type === 'recording')?.id;
  expect(recordingNode).toBeTruthy();

  // register model + version 1 (inline safetensors weights, manifest from the lineage)
  const name = `e2e-decoder-${Date.now().toString(36)}`;
  const model = await post<{ id: string }>(request, scientist, '/v1/models', {
    name,
    card: {
      summary: 'Synthetic end-to-end test model.',
      task: 'decoding',
      inferences: ['motor_intent'],
      modalities: ['EEG'],
      limitations: 'Synthetic data only.',
      robustness: {
        noise: measurement('additive gaussian noise, SNR 10 dB'),
        channel_dropout: measurement('drop 1 channel'),
        adversarial: measurement('FGSM, eps=0.01'),
      },
    },
  });
  await post(request, scientist, `/v1/models/${model.id}/versions`, {
    weights: { format: 'safetensors', data_base64: safetensors() },
    training_manifest: { input_node_ids: [recordingNode] },
    code_commit: '0123456789abcdef0123456789abcdef01234567',
    intended_use: 'Research decoding of motor intent (e2e test).',
    use_restrictions: [],
  });
  const dep = await post<{ state: string }>(
    request,
    scientist,
    `/v1/models/${model.id}/deployments`,
    {
      version: 1,
      context: { jurisdiction: 'US', setting: 'research', purpose: 'e2e study' },
    },
  );
  expect(dep.state).toBe('approved');

  // the subject withdraws (5.5); the stack's worker runs the DeletionJob, which flags the model
  const dj = await post<{ id: string }>(
    request,
    steward,
    `/v1/subjects/${s.subjectId}/withdrawals`,
    {},
  );
  await expect
    .poll(
      async () =>
        (await getJson<{ state: string }>(request, steward, `/v1/deletion-jobs/${dj.id}`)).state,
      { timeout: 180_000, intervals: [1_000, 2_000, 5_000] },
    )
    .toBe('succeeded');

  // console: the flagged model is shown with the reason
  await page
    .getByRole('navigation', { name: 'Main' })
    .getByRole('link', { name: 'Models' })
    .click();
  const list = page.getByRole('table', { name: 'Models' });
  const row = list.getByRole('row', { name: new RegExp(name) });
  await expect(row.getByText('retrain required')).toBeVisible();
  await axe(page, 'models list');

  await row.getByRole('link', { name }).click();
  const taint = page.getByTestId('taint-status');
  await expect(taint).toHaveAttribute('role', 'alert');
  await expect(taint).toContainText('Retrain required');
  await expect(taint).toContainText(`deletion job ${dj.id}`);
  await expect(taint).toContainText('Deployments of this version are blocked');

  const deps = page.getByRole('table', { name: 'Deployment requests' });
  await expect(deps.getByText('blocked', { exact: true })).toBeVisible();
  await expect(deps).toContainText('(was approved)');
  await expect(deps).toContainText('Retrain required: a subject whose data trained');

  // the request form never offers control contexts (SEC-092)
  const settings = await page
    .getByLabel('Setting')
    .locator('option')
    .evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value));
  expect(settings).toContain('research');
  for (const c of ['closed_loop_stimulation', 'neuromodulation_control', 'actuator_control'])
    expect(settings).not.toContain(c);

  // a new request on the flagged version is refused with the reason
  await page.getByLabel('Purpose').fill('e2e study');
  await page.getByLabel('Setting').selectOption('research');
  await page.getByLabel('Jurisdiction').fill('US');
  await page.getByRole('button', { name: 'Request deployment' }).click();
  await expect(page.getByTestId('refusal')).toContainText('Retrain required');
  await axe(page, 'model detail (tainted)');

  // no tokens or data left in web storage
  expect(await page.context().cookies()).toEqual([]);
  expect(await page.evaluate(() => window.localStorage.length + window.sessionStorage.length)).toBe(
    0,
  );
});
