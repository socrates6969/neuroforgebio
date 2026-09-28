import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReportOut } from '../api/generated';
import { App } from '../App';
import { fakeSession, renderWithApi, uuid, whoami } from '../test/helpers';
import { render } from '@testing-library/react';
import { SessionProvider } from '../auth/session';
import { ApiClient } from '../api/client';
import { fakeApi } from '../test/helpers';
import { parseHash } from '../router';
import { ReportView, pivot } from './Sweep';
import { RunPage } from './Runs';
import { runRegistry } from '../runs';

describe('router', () => {
  it('parses routes and queries', () => {
    expect(parseHash('')).toMatchObject({ name: 'projects' });
    expect(parseHash('#/runs/abc')).toMatchObject({ name: 'run', params: { id: 'abc' } });
    const l = parseHash('#/lineage/n1?direction=up&depth=3');
    expect(l.name).toBe('lineage');
    expect(l.query.get('depth')).toBe('3');
    expect(parseHash('#/nope/x/y').name).toBe('not-found');
  });
});

/** Typed like the generated ReportOut (m3-sweeps' pydantic model); numbers are synthetic. */
function report(): ReportOut {
  const lf = [0.1, 1.0];
  const hf = [30, 40];
  const variants: ReportOut['variants'] = [];
  const cells: ReportOut['cells'] = [];
  let n = 0;
  lf.forEach((a) =>
    hf.forEach((b) => {
      const v = variants.length;
      const params = { 'filter.l_freq': a, 'filter.h_freq': b };
      const runs = [uuid(100 + n++), uuid(100 + n++)];
      runs.forEach((run_id, k) =>
        cells.push({
          run_id,
          recording_id: uuid(k + 1),
          variant: v,
          params,
          pipeline_ref: `eeg-basic-v${v}@1.0.0`,
          pipeline_version_id: 'pv:sha256:' + String(v).repeat(64),
          state: 'succeeded',
          value: 0.6 + v / 100,
          prov_activity_id: uuid(200 + n),
          prov_node_id: uuid(300 + n),
          artifact: null,
        }),
      );
      variants.push({
        variant: v,
        params,
        pipeline_ref: `eeg-basic-v${v}@1.0.0`,
        pipeline_version_id: 'pv:sha256:' + String(v).repeat(64),
        mean: 0.6 + v / 100,
        n: 2,
        run_ids: runs,
      });
    }),
  );
  return {
    sweep_id: uuid(99),
    state: 'succeeded',
    complete: true,
    pipeline: 'eeg-basic@1.0.0',
    pipeline_version_id: 'pv:sha256:' + 'e'.repeat(64),
    metric: { name: 'decode.accuracy', step: 'decode', key: 'accuracy', higher_is_better: true },
    factors: [
      { name: 'filter.l_freq', values: lf },
      { name: 'filter.h_freq', values: hf },
    ],
    cells,
    variants,
    sensitivity: [
      {
        factor: 'filter.l_freq',
        range: 0.02,
        levels: lf.map((value, i) => ({
          value: value as never,
          mean: 0.6 + i / 50,
          n: 4,
          run_ids: [cells[i]!.run_id],
        })),
      },
    ],
    best: { variant: 3, params: variants[3]!.params, mean: 0.63, run_ids: variants[3]!.run_ids },
    prov_node_id: uuid(400),
  };
}

describe('sweep report', () => {
  it('pivots factors and links every number to the runs it comes from', () => {
    const rep = report();
    const p = pivot(rep);
    expect(p.rows).toEqual([0.1, 1.0]);
    expect(p.cols).toEqual([30, 40]);
    expect(p.variant(1.0, 40).map((v) => v.variant)).toEqual([3]);
    render(<ReportView report={rep} />);
    const grid = screen.getByRole('table', { name: /per variant/ });
    const hrefs = within(grid)
      .getAllByRole('link')
      .map((a) => a.getAttribute('href'));
    for (const v of rep.variants) for (const r of v.run_ids) expect(hrefs).toContain(`#/runs/${r}`);
    for (const c of rep.cells)
      expect(
        screen.getByRole('link', { name: `${c.value!.toFixed(3)}, run ${c.run_id}` }),
      ).toBeTruthy();
    expect(screen.getByText(/Best variant #3/)).toBeTruthy();
  });
});

describe('run detail', () => {
  it('shows artifacts, links the lineage and remembers the run for the runs list', async () => {
    runRegistry.clear();
    const id = uuid(9);
    renderWithApi(<RunPage id={id} />, {
      routes: {
        [`GET /v1/runs/${id}`]: () => ({
          id,
          pipeline_ref: 'eeg-basic@1.0.0',
          pipeline_version_id: 'pv:sha256:' + 'b'.repeat(64),
          recording_id: uuid(3),
          state: 'succeeded',
          seed: 7,
          attempt: 1,
          error: null,
          record: { steps: [] },
          prov_activity_id: uuid(50),
          prov_batch_id: 'provb:x',
          created_at: '2026-09-26T10:00:00Z',
          started_at: '2026-09-26T10:00:01Z',
          finished_at: '2026-09-26T10:00:05Z',
          artifacts: [
            {
              id: uuid(60),
              step: 'psd',
              name: 'bandpower.npz',
              sha256: 'c'.repeat(64),
              size_bytes: 123,
              visible_at: '2026-09-26T10:00:05Z',
            },
          ],
        }),
      },
    });
    expect(await screen.findByText('bandpower.npz')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open lineage' }).getAttribute('href')).toBe(
      `#/lineage/${uuid(50)}?direction=both`,
    );
    await waitFor(() => expect(runRegistry.list().map((r) => r.id)).toEqual([id]));
  });
});

describe('App', () => {
  it('shows the login screen, signs in, loads whoami and signs out', async () => {
    const session = fakeSession({ status: 'signed-out' });
    const api = fakeApi({
      'GET /v1/whoami': () => whoami(['scientist']),
      'GET /v1/projects': () => [],
    });
    const client = new ApiClient({ baseUrl: '', token: async () => 't', fetch: api.fetch });
    render(
      <SessionProvider session={session} client={client}>
        <App devIdp />
      </SessionProvider>,
    );
    expect(screen.getByRole('note').textContent).toMatch(/Development identity provider/);
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Sign in' })));
    expect(await screen.findByText('scientist')).toBeTruthy();
    expect(document.title).toMatch(/console$/);
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Sign out' })));
    expect(await screen.findByText('You are signed out.')).toBeTruthy();
  });
});
