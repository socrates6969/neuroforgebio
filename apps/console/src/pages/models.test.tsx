import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { App } from '../App';
import { ApiClient, ApiError } from '../api/client';
import { SessionProvider } from '../auth/session';
import { can } from '../authz/can';
import { refusalFromError } from '../registry/api';
import {
  CONTROL_SETTINGS,
  DEPLOY_ACTION,
  MODEL_READ_ACTION,
  reasonText,
} from '../registry/context';
import {
  CLEAN_MODEL_ID,
  DELETION_JOB,
  MODEL_ID,
  RECORDING_NODE,
  VERSION_NODE,
  approvedDeployment,
  blockedDeployment,
  cleanVersion,
  modelDetail,
  models,
  refusedDeployment,
  taintedVersion,
  uploadedVersion,
  versionLineage,
  versions,
  vocabulary,
} from '../test/registry-fixtures';
import { fakeApi, fakeSession, jsonResponse, renderWithApi, whoami } from '../test/helpers';
import {
  DeploymentForm,
  DeploymentTable,
  ModelPage,
  ModelsPage,
  formOptions,
  pickVersion,
} from './Models';

const M = `/v1/models/${MODEL_ID}`;
const detailRoutes = () => ({
  [`GET ${M}`]: () => modelDetail,
  [`GET ${M}/versions/2`]: () => taintedVersion,
  [`GET ${M}/versions/1`]: () => cleanVersion,
  [`GET ${M}/versions/2/lineage`]: () => versionLineage,
  [`GET ${M}/versions/1/lineage`]: () => versionLineage,
  [`GET ${M}/deployments`]: () => [blockedDeployment, refusedDeployment, approvedDeployment],
  'GET /v1/registry/vocabulary': () => vocabulary,
});

const problem = (status: number, extra: Record<string, unknown>) =>
  jsonResponse({ status, title: 'Problem', ...extra }, status, 'application/problem+json');

describe('model list', () => {
  it('lists models with their taint status and links to the detail page', async () => {
    const { api } = renderWithApi(<ModelsPage />, {
      routes: { 'GET /v1/models': () => models },
    });
    const table = await screen.findByRole('table', { name: 'Models' });
    const flagged = within(table).getByRole('row', { name: /motor-imagery-decoder/ });
    expect(within(flagged).getByText('retrain required')).toBeTruthy();
    expect(within(flagged).getByText('v2')).toBeTruthy();
    expect(within(flagged).getByRole('link').getAttribute('href')).toBe(`#/models/${MODEL_ID}`);
    const clean = within(table).getByRole('row', { name: /sleep-stager/ });
    expect(within(clean).queryByText('retrain required')).toBeNull();
    expect(within(clean).getByRole('link').getAttribute('href')).toBe(`#/models/${CLEAN_MODEL_ID}`);
    expect(api.calls.some((c) => c.path === '/v1/models?limit=50&offset=0')).toBe(true);
  });

  it('shows the server error (e.g. 403) instead of data', async () => {
    renderWithApi(<ModelsPage />, {
      routes: { 'GET /v1/models': () => problem(403, { detail: 'role lacks model:read' }) },
    });
    expect((await screen.findByRole('alert')).textContent).toMatch(/Not permitted/);
    expect(screen.queryByRole('table')).toBeNull();
  });
});

describe('model detail', () => {
  it('shows the card, versions and the newest version with restrictions and taint reason', async () => {
    renderWithApi(<ModelPage id={MODEL_ID} query={new URLSearchParams()} />, {
      routes: detailRoutes(),
    });
    expect(
      await screen.findByRole('heading', { name: 'Model motor-imagery-decoder' }),
    ).toBeTruthy();
    const vt = await screen.findByRole('table', { name: /Versions of/ });
    expect(within(vt).getAllByRole('row')).toHaveLength(3);
    expect(await screen.findByRole('heading', { name: 'Version 2' })).toBeTruthy();
    expect(within(vt).getByRole('link', { name: 'v2' }).getAttribute('aria-current')).toBe('true');

    const taint = screen.getByTestId('taint-status');
    expect(taint.getAttribute('role')).toBe('alert');
    expect(taint.textContent).toMatch(/Retrain required/);
    expect(taint.textContent).toMatch(/Consent withdrawal: deletion job/);
    expect(taint.textContent).toContain(DELETION_JOB);
    expect(taint.textContent).toMatch(/Deployments of this version are blocked/);

    const restrictions = screen.getByRole('list', { name: 'Use restrictions' });
    expect(
      within(restrictions)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(taintedVersion.use_restrictions);
    expect(screen.getByTestId('intended-use').textContent).toBe(taintedVersion.intended_use);
    expect(screen.getByText('12 subjects from 24 recordings, 4 SISA shards')).toBeTruthy();

    // model card incl. SEC-145 robustness measurements (recorded, not claimed)
    expect(screen.getByRole('heading', { name: 'Model card' })).toBeTruthy();
    const rob = screen.getByRole('table', { name: 'Robustness' });
    expect(within(rob).getAllByRole('row')).toHaveLength(4);
    expect(screen.getByText(/not a robustness claim/)).toBeTruthy();
    expect(screen.getByText(/required before publication/)).toBeTruthy();
  });

  it('shows a clean version without a taint alert when selected in the URL', async () => {
    renderWithApi(<ModelPage id={MODEL_ID} query={new URLSearchParams({ version: '1' })} />, {
      routes: detailRoutes(),
    });
    expect(await screen.findByRole('heading', { name: 'Version 1' })).toBeTruthy();
    const status = screen.getByTestId('taint-status');
    expect(status.getAttribute('role')).toBeNull();
    expect(status.textContent).toMatch(/No consent withdrawal/);
  });

  it('shows the weights source (AppSec M3): platform-trained vs uploaded', async () => {
    renderWithApi(<ModelPage id={MODEL_ID} query={new URLSearchParams()} />, {
      routes: detailRoutes(),
    });
    expect(await screen.findByRole('heading', { name: 'Version 2' })).toBeTruthy();
    expect(screen.getByTestId('weights-source').textContent).toMatch(/Trained on the platform/);
    const vt = screen.getByRole('table', { name: /Versions of/ });
    expect(
      within(vt)
        .getAllByRole('columnheader')
        .map((c) => c.textContent),
    ).toContain('Weights');
    expect(within(vt).getAllByText('platform')).toHaveLength(2);
  });

  it('explains an uploaded version flagged for unverifiable lineage', async () => {
    renderWithApi(<ModelPage id={MODEL_ID} query={new URLSearchParams()} />, {
      routes: { ...detailRoutes(), [`GET ${M}/versions/2`]: () => uploadedVersion },
    });
    expect(await screen.findByRole('heading', { name: 'Version 2' })).toBeTruthy();
    expect(screen.getByTestId('weights-source').textContent).toMatch(
      /Uploaded: the training data is declared by the uploader and not verified/,
    );
    const taint = screen.getByTestId('taint-status');
    expect(taint.textContent).toMatch(/Its weights were uploaded/);
    expect(taint.textContent).toMatch(/Reason: unverifiable lineage \(uploaded weights\)/);
    expect(taint.textContent).not.toMatch(/Data of a subject who withdrew consent was used/);
    expect(reasonText('upload_approval_required')).toMatch(/other than the uploader/);
  });

  it('reuses the lineage explorer for the training lineage (keyboard listbox)', async () => {
    renderWithApi(<ModelPage id={MODEL_ID} query={new URLSearchParams()} />, {
      routes: detailRoutes(),
    });
    const list = await screen.findByRole('listbox', { name: /Nodes/ });
    expect(within(list).getAllByRole('option')).toHaveLength(3);
    expect(screen.getByText(/12 training subject\(s\)/)).toBeTruthy();
    expect(
      screen.getByRole('link', { name: 'Open in the lineage explorer' }).getAttribute('href'),
    ).toBe(`#/lineage/${VERSION_NODE}?direction=up`);
    list.focus();
    expect(document.activeElement).toBe(list);
    fireEvent.keyDown(list, { key: 'Home' });
    expect(list.querySelector('[aria-selected=true]')?.getAttribute('data-type')).toBe('recording');
    expect(list.getAttribute('aria-activedescendant')).toBe(`lineage-node-${RECORDING_NODE}`);
    fireEvent.keyDown(list, { key: 'End' });
    expect(list.querySelector('[aria-selected=true]')?.getAttribute('data-type')).toBe('model');
  });

  it('lists deployment requests: blocked after approval, refused, approved, with reasons', async () => {
    renderWithApi(<ModelPage id={MODEL_ID} query={new URLSearchParams()} />, {
      routes: detailRoutes(),
    });
    const table = await screen.findByRole('table', { name: 'Deployment requests' });
    const [blocked, refused, approved] = within(table).getAllByRole('row').slice(1);
    expect(within(blocked!).getByText('blocked')).toBeTruthy();
    expect(blocked!.textContent).toMatch(/\(was approved\)/);
    expect(blocked!.textContent).toMatch(/Retrain required: a subject whose data trained/);
    expect(within(refused!).getByText('refused')).toBeTruthy();
    expect(refused!.textContent).toContain('Art. 5(1)(f)');
    expect(refused!.textContent).toMatch(
      /staff stress monitoring; Workplace setting; jurisdiction EU/,
    );
    expect(within(approved!).getByText('approved')).toBeTruthy();
    expect(approved!.textContent).not.toMatch(/was /);
  });

  it('picks the requested version, else the newest', () => {
    expect(pickVersion(versions, '1')?.version).toBe(1);
    expect(pickVersion(versions, null)?.version).toBe(2);
    expect(pickVersion(versions, 'nope')?.version).toBe(2);
    expect(pickVersion([], null)).toBeUndefined();
  });
});

describe('deployment requests', () => {
  async function fill(ctx: { purpose: string; setting: string; jurisdiction: string }) {
    await screen.findByRole('option', { name: 'Safety monitoring' });
    fireEvent.change(screen.getByLabelText('Purpose'), { target: { value: ctx.purpose } });
    fireEvent.change(screen.getByLabelText('Setting'), { target: { value: ctx.setting } });
    fireEvent.change(screen.getByLabelText('Jurisdiction'), {
      target: { value: ctx.jurisdiction },
    });
    await act(async () => {
      fireEvent.submit(screen.getByRole('button', { name: 'Request deployment' }).closest('form')!);
    });
  }
  const form = (version = 1) => (
    <DeploymentForm modelId={MODEL_ID} version={version} onDone={() => {}} />
  );
  const vocabRoute = { 'GET /v1/registry/vocabulary': () => vocabulary };

  it('sends the declared context and shows the platform refusal with its reasons', async () => {
    let sent: unknown;
    renderWithApi(form(), {
      routes: {
        ...vocabRoute,
        [`POST ${M}/deployments`]: ({ body }) => {
          sent = body;
          return problem(403, {
            type: 'deployment-refused',
            detail: 'The declared context is prohibited for this model version: no_clinical_care',
            code: 'no_clinical_care',
            reasons: ['no_clinical_care'],
            deployment_id: refusedDeployment.id,
          });
        },
      },
    });
    await fill({ purpose: 'seizure alerting', setting: 'clinical_care', jurisdiction: 'us-co' });
    const refusal = await screen.findByTestId('refusal');
    expect(refusal.getAttribute('role')).toBe('alert');
    expect(within(refusal).getByRole('list', { name: 'Refusal reasons' }).textContent).toBe(
      'This version may not be deployed in clinical care.',
    );
    expect(refusal.textContent).toContain(refusedDeployment.id);
    expect(sent).toEqual({
      version: 1,
      context: {
        jurisdiction: 'US-CO',
        setting: 'clinical_care',
        purpose: 'seizure alerting',
        outputs: 'labels',
        influences_behaviour: false,
      },
    });
  });

  it('shows a retrain_required refusal and then an approved request', async () => {
    let n = 0;
    renderWithApi(form(2), {
      routes: {
        ...vocabRoute,
        [`POST ${M}/deployments`]: () =>
          n++ === 0
            ? problem(403, {
                code: 'retrain_required',
                reasons: ['retrain_required'],
                deployment_id: blockedDeployment.id,
              })
            : approvedDeployment,
      },
    });
    await fill({ purpose: 'research', setting: 'research', jurisdiction: 'EU' });
    const refusal = await screen.findByTestId('refusal');
    expect(refusal.textContent).toMatch(/Retrain required: a subject whose data trained/);
    await fill({ purpose: 'research', setting: 'research', jurisdiction: 'EU' });
    expect((await screen.findByRole('status')).textContent).toMatch(/Request recorded: approved/);
    expect(screen.queryByTestId('refusal')).toBeNull();
  });

  it('a hidden action forced anyway gets the server 403, not a refusal', async () => {
    renderWithApi(form(), {
      roles: ['viewer'],
      routes: {
        ...vocabRoute,
        [`POST ${M}/deployments`]: () => problem(403, { detail: 'denied' }),
      },
    });
    await fill({ purpose: 'research', setting: 'research', jurisdiction: 'EU' });
    expect((await screen.findByRole('alert')).textContent).toMatch(/Not permitted/);
    expect(screen.queryByTestId('refusal')).toBeNull();
  });

  it('does not offer stimulation, neuromodulation or actuator control (SEC-092)', async () => {
    renderWithApi(form(), {
      routes: {
        // even if a platform vocabulary listed a control setting, the form drops it
        'GET /v1/registry/vocabulary': () => ({
          ...vocabulary,
          settings: [...vocabulary.settings, 'actuator_control'],
        }),
      },
    });
    await screen.findByRole('option', { name: 'Safety monitoring' });
    const values = within(screen.getByLabelText('Setting'))
      .getAllByRole('option')
      .map((o) => (o as HTMLOptionElement).value);
    for (const c of CONTROL_SETTINGS) expect(values).not.toContain(c.value);
    expect(values).toContain('research');
    expect(screen.getByTestId('control-note').textContent).toMatch(/SEC-092/);
    expect(formOptions(null).setting.map((o) => o.value)).not.toContain('closed_loop_stimulation');
    expect(
      formOptions(vocabulary)
        .outputs.map((o) => o.value)
        .sort(),
    ).toEqual(['coarse_scores', 'labels']);
  });

  it('shows a stored control-context refusal (sent by another client) readably', () => {
    render(
      <DeploymentTable
        rows={[
          {
            ...refusedDeployment,
            setting: 'actuator_control',
            reasons: ['sec_092_control_context'],
          },
        ]}
      />,
    );
    expect(screen.getByText(/Actuator control \(never allowed\)/)).toBeTruthy();
    expect(screen.getByText(/SEC-092: the platform never controls/)).toBeTruthy();
  });

  it('form controls are labelled and reachable by keyboard', async () => {
    renderWithApi(form(), { routes: vocabRoute });
    await screen.findByRole('option', { name: 'Safety monitoring' });
    const controls = [
      screen.getByLabelText('Purpose'),
      screen.getByLabelText('Setting'),
      screen.getByLabelText('Outputs exposed'),
      screen.getByLabelText('Jurisdiction'),
      screen.getByLabelText(/influence the person/),
      screen.getByLabelText(/Exception record ID/),
      screen.getByRole('button', { name: 'Request deployment' }),
    ];
    for (const c of controls) {
      expect(c.getAttribute('tabindex')).not.toBe('-1');
      expect(c.hasAttribute('disabled')).toBe(false);
      c.focus();
      expect(document.activeElement).toBe(c);
    }
    expect(screen.getByLabelText('Jurisdiction').getAttribute('aria-describedby')).toBe(
      'ctx-jurisdiction-help',
    );
  });

  it('counts only a problem with a code and reasons as a refusal', () => {
    expect(refusalFromError(new Error('x'))).toBeNull();
    expect(refusalFromError(new ApiError(403, { detail: 'denied' }))).toBeNull();
    expect(refusalFromError(new ApiError(403, { code: 'x' }))).toBeNull();
    expect(
      refusalFromError(
        new ApiError(403, { code: 'eu_ai_act_5_1_f', reasons: ['eu_ai_act_5_1_f', 'x'] }),
      ),
    ).toEqual({ code: 'eu_ai_act_5_1_f', reasons: ['eu_ai_act_5_1_f', 'x'], deploymentId: null });
  });
});

describe('role-based hiding mirrors the authz matrix (not enforcement)', () => {
  for (const role of ['viewer', 'auditor', 'scientist', 'owner']) {
    it(`${role}: Models nav and deploy form follow authz.json`, async () => {
      window.location.hash = `#/models/${MODEL_ID}`;
      const api = fakeApi({ 'GET /v1/whoami': () => whoami([role]), ...detailRoutes() });
      const client = new ApiClient({ baseUrl: '', token: async () => 't', fetch: api.fetch });
      render(
        <SessionProvider session={fakeSession()} client={client}>
          <App />
        </SessionProvider>,
      );
      await screen.findByText(role);
      const nav = screen.getByRole('navigation', { name: 'Main' });
      expect(within(nav).queryByRole('link', { name: 'Models' }) !== null).toBe(
        can([role], MODEL_READ_ACTION),
      );
      await screen.findByRole('table', { name: 'Deployment requests' });
      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Request deployment' }) !== null).toBe(
          can([role], DEPLOY_ACTION),
        ),
      );
    });
  }
});

describe('no stale state across versions and models (BUG-HUNT M11, L4)', () => {
  const refuseRetrain = {
    'GET /v1/registry/vocabulary': () => vocabulary,
    [`POST ${M}/deployments`]: () =>
      problem(403, {
        code: 'retrain_required',
        reasons: ['retrain_required'],
        deployment_id: blockedDeployment.id,
      }),
  };
  async function refuse() {
    await screen.findByRole('option', { name: 'Safety monitoring' });
    fireEvent.change(screen.getByLabelText('Purpose'), { target: { value: 'research' } });
    fireEvent.change(screen.getByLabelText('Setting'), { target: { value: 'research' } });
    fireEvent.change(screen.getByLabelText('Jurisdiction'), { target: { value: 'EU' } });
    await act(async () => {
      fireEvent.submit(screen.getByRole('button', { name: 'Request deployment' }).closest('form')!);
    });
    expect((await screen.findByTestId('refusal')).textContent).toMatch(/Retrain required/);
  }

  it('switching the version on the model page drops the previous version’s refusal', async () => {
    function Harness() {
      const [v, setV] = useState('2');
      return (
        <>
          <button type="button" onClick={() => setV('1')}>
            switch version
          </button>
          <ModelPage id={MODEL_ID} query={new URLSearchParams({ version: v })} />
        </>
      );
    }
    renderWithApi(<Harness />, {
      roles: ['owner'],
      routes: { ...detailRoutes(), ...refuseRetrain },
    });
    await screen.findByRole('heading', { name: 'Request a deployment of version 2' });
    await refuse();
    fireEvent.click(screen.getByRole('button', { name: 'switch version' }));
    await screen.findByRole('heading', { name: 'Request a deployment of version 1' });
    expect(screen.queryByTestId('refusal')).toBeNull();
    expect(screen.queryByText(/Request recorded/)).toBeNull();
    expect((screen.getByLabelText('Purpose') as HTMLInputElement).value).toBe('');
  });

  it('the deployment form resets its outcome when its version prop changes', async () => {
    function Harness() {
      const [v, setV] = useState(2);
      return (
        <>
          <button type="button" onClick={() => setV(1)}>
            switch version
          </button>
          <DeploymentForm modelId={MODEL_ID} version={v} onDone={() => {}} />
        </>
      );
    }
    renderWithApi(<Harness />, { routes: refuseRetrain });
    await refuse();
    fireEvent.click(screen.getByRole('button', { name: 'switch version' }));
    await screen.findByRole('heading', { name: 'Request a deployment of version 1' });
    expect(screen.queryByTestId('refusal')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('navigating between two model ids never shows the previous model while loading', async () => {
    window.location.hash = `#/models/${MODEL_ID}`;
    let release: (v: unknown) => void = () => {};
    const clean = new Promise((r) => {
      release = r;
    });
    const api = fakeApi({
      'GET /v1/whoami': () => whoami(['owner']),
      ...detailRoutes(),
      [`GET /v1/models/${CLEAN_MODEL_ID}`]: () => clean,
      [`GET /v1/models/${CLEAN_MODEL_ID}/deployments`]: () => [],
    });
    const client = new ApiClient({ baseUrl: '', token: async () => 't', fetch: api.fetch });
    render(
      <SessionProvider session={fakeSession()} client={client}>
        <App />
      </SessionProvider>,
    );
    await screen.findByRole('heading', { name: 'Model motor-imagery-decoder' });
    await screen.findByTestId('taint-status');
    await act(async () => {
      window.location.hash = `#/models/${CLEAN_MODEL_ID}`;
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    await waitFor(() =>
      expect(api.calls.some((c) => c.path === `/v1/models/${CLEAN_MODEL_ID}`)).toBe(true),
    );
    // the second model is still loading: nothing of the first model may be shown
    expect(screen.queryByRole('heading', { name: 'Model motor-imagery-decoder' })).toBeNull();
    expect(screen.queryByTestId('taint-status')).toBeNull();
    expect(screen.queryByText(/retrain required/i)).toBeNull();
    await act(async () => {
      release({ ...models[1]!, versions: [] });
    });
    expect(await screen.findByRole('heading', { name: 'Model sleep-stager' })).toBeTruthy();
  });
});
