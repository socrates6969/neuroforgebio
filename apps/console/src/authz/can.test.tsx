import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import matrix from '../api/authz.json';
import { OPERATIONS } from '../api/generated';
import { App } from '../App';
import { ProjectsPage } from '../pages/Projects';
import { RecordingPage } from '../pages/Recording';
import { RunPage } from '../pages/Runs';
import { renderWithApi, uuid } from '../test/helpers';
import { can, canReadQuarantined } from './can';

const ALL_ROLES = matrix.roles;

describe('can() mirrors the server matrix', () => {
  it('matches PERMISSIONS for every role x action, and denies unknown actions', () => {
    for (const [action, allowed] of Object.entries(matrix.permissions))
      for (const role of ALL_ROLES)
        expect(can([role], action), `${role} ${action}`).toBe(allowed.includes(role));
    expect(can(ALL_ROLES, 'no:such-action')).toBe(false);
    expect(can([], 'project:read')).toBe(false);
  });

  it('knows every action the API declares', () => {
    for (const op of Object.values(OPERATIONS))
      if (op.action && op.action !== 'public')
        expect(matrix.permissions, op.action).toHaveProperty([op.action]);
  });

  it('quarantine readers are owner/admin/data-steward', () => {
    expect(canReadQuarantined(['scientist'])).toBe(false);
    expect(canReadQuarantined(['data-steward'])).toBe(true);
  });
});

const RUN_ID = uuid(9);
const REC_ID = uuid(3);
const run = (state = 'running') => ({
  id: RUN_ID,
  pipeline_ref: 'eeg-basic@1.0.0',
  pipeline_version_id: 'pv:sha256:' + 'a'.repeat(64),
  recording_id: REC_ID,
  state,
  seed: 1,
  attempt: 1,
  error: null,
  record: {},
  prov_activity_id: uuid(50),
  prov_batch_id: null,
  created_at: '2026-09-26T10:00:00Z',
  started_at: null,
  finished_at: null,
  artifacts: [],
});
const recording = {
  id: REC_ID,
  session_id: uuid(2),
  label: 'rec-1',
  source_format: 'edf',
  state: 'ready',
  duration_s: 20,
  created_at: '2026-09-26T10:00:00Z',
  channels: [],
};

describe('role-based hiding (UI only; the server enforces)', () => {
  it('project creation: owner/admin only', async () => {
    const routes = { 'GET /v1/projects': () => [] };
    const a = renderWithApi(<ProjectsPage />, { roles: ['admin'], routes });
    expect(await screen.findByLabelText('New project')).toBeTruthy();
    a.unmount();
    renderWithApi(<ProjectsPage />, { roles: ['scientist'], routes });
    await screen.findByText('No projects yet.');
    expect(screen.queryByLabelText('New project')).toBeNull();
  });

  it('run start: writers yes, viewer and auditor no', async () => {
    const routes = { [`GET /v1/recordings/${REC_ID}`]: () => recording };
    for (const [role, visible] of [
      ['scientist', true],
      ['viewer', false],
      ['auditor', false],
    ] as const) {
      const r = renderWithApi(<RecordingPage id={REC_ID} />, { roles: [role], routes });
      await screen.findByText('rec-1', { exact: false });
      await waitFor(() => expect(r.api.calls.some((c) => c.path === '/v1/whoami')).toBe(true));
      await waitFor(() => expect(!!screen.queryByLabelText(/Run pipeline/)).toBe(visible));
      r.unmount();
    }
  });

  it('run cancel: hidden for viewers, shown for scientists while running', async () => {
    const routes = { [`GET /v1/runs/${RUN_ID}`]: () => run('running') };
    const a = renderWithApi(<RunPage id={RUN_ID} pollMs={60_000} />, {
      roles: ['scientist'],
      routes,
    });
    expect(await screen.findByRole('button', { name: 'Cancel run' })).toBeTruthy();
    a.unmount();
    renderWithApi(<RunPage id={RUN_ID} pollMs={60_000} />, { roles: ['viewer'], routes });
    await screen.findByText('eeg-basic@1.0.0');
    expect(screen.queryByRole('button', { name: 'Cancel run' })).toBeNull();
  });

  it('navigation hides sections a role cannot read (device has none)', async () => {
    window.location.hash = '#/account';
    const r = renderWithApi(<App />, { roles: ['device'] });
    await screen.findByRole('navigation', { name: 'Main' });
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Account' })).toBeTruthy());
    expect(screen.queryByRole('link', { name: 'Projects' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Runs' })).toBeNull();
    r.unmount();
    renderWithApi(<App />, { roles: ['viewer'] });
    expect(await screen.findByRole('link', { name: 'Projects' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Lineage' })).toBeTruthy();
  });

  it('a hidden control is not the enforcement: a forced call still gets the server 403', async () => {
    const r = renderWithApi(<ProjectsPage />, {
      roles: ['viewer'],
      routes: {
        'GET /v1/projects': () => [],
        'POST /v1/projects': () =>
          new Response(JSON.stringify({ title: 'Forbidden', status: 403 }), {
            status: 403,
            headers: { 'content-type': 'application/problem+json' },
          }),
      },
    });
    await screen.findByText('No projects yet.');
    const { ApiClient } = await import('../api/client');
    const c = new ApiClient({ baseUrl: '', token: async () => 't', fetch: r.api.fetch });
    await expect(c.call('createProject', { body: { name: 'x' } })).rejects.toMatchObject({
      status: 403,
    });
  });
});
