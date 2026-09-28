import { useState, type FormEvent, type ReactNode } from 'react';
import type { ReportOut } from '../api/generated';
import { useSession } from '../auth/session';
import { ErrorBox, Loading, Page, StateBadge, shortId } from '../components/common';
import { href, navigate } from '../router';
import { useAsync } from '../useAsync';

const key = (v: unknown) => JSON.stringify(v);
const show = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v));
const fmt = (v: number | null | undefined) => (v === null || v === undefined ? '–' : v.toFixed(3));

/** Grid of variant means: rows = first factor, columns = second factor (if any). */
export function pivot(report: ReportOut) {
  const [rowF, colF] = report.factors;
  const rows = rowF?.values ?? [null];
  const cols = colF?.values ?? [null];
  const variant = (rv: unknown, cv: unknown) =>
    report.variants.filter(
      (v) =>
        (!rowF || key(v.params[rowF.name]) === key(rv)) &&
        (!colF || key(v.params[colF.name]) === key(cv)),
    );
  return { rowF, colF, rows, cols, variant };
}

function RunLinks({ ids, label }: { ids: string[]; label: string }) {
  if (ids.length === 0) return null;
  return (
    <span className="small">
      {' '}
      (runs:{' '}
      {ids.map((id, i) => (
        <span key={id}>
          {i > 0 ? ', ' : ''}
          <a href={href(`/runs/${id}`)} aria-label={`${label}: run ${id}`} className="mono">
            {shortId(id)}
          </a>
        </span>
      ))}
      )
    </span>
  );
}

export function SweepsPage() {
  const [id, setId] = useState('');
  const open = (e: FormEvent) => {
    e.preventDefault();
    if (id.trim()) navigate(`/sweeps/${id.trim()}`);
  };
  return (
    <Page title="Sweeps">
      <form className="inline-form card" onSubmit={open}>
        <label htmlFor="sweep-id">Open a sweep report by ID</label>
        <input
          id="sweep-id"
          value={id}
          onChange={(e) => setId(e.target.value)}
          pattern="[0-9a-fA-F-]{36}"
          required
        />
        <button className="btn" type="submit">
          Open
        </button>
      </form>
      <p className="small muted">
        The platform has no sweep list route yet; sweeps are opened by ID.
      </p>
    </Page>
  );
}

export function SweepPage({ id }: { id: string }) {
  const { client } = useSession();
  const sweep = useAsync(
    (signal) => client.call('getSweep', { path: { sweep_id: id }, signal }),
    [client, id],
  );
  const report = useAsync(
    (signal) => client.call('getSweepReport', { path: { sweep_id: id }, signal }),
    [client, id],
  );
  const s = sweep.data;
  return (
    <Page title={s ? `Sweep: ${s.name}` : 'Sweep report'}>
      <p>
        <a href={href('/sweeps')}>All sweeps</a>
      </p>
      {sweep.error ? <ErrorBox error={sweep.error} /> : null}
      {s ? (
        <dl className="kv card">
          <dt>State</dt>
          <dd>
            <StateBadge state={s.state} />{' '}
            {Object.entries(s.run_states)
              .map(([k, n]) => `${n} ${k}`)
              .join(', ')}
          </dd>
          <dt>Base pipeline</dt>
          <dd>
            {s.pipeline} <span className="mono small">{s.pipeline_version_id}</span>
          </dd>
          <dt>Recordings</dt>
          <dd>
            {s.recording_ids.map((r) => (
              <a key={r} href={href(`/recordings/${r}`)} className="mono">
                {shortId(r)}{' '}
              </a>
            ))}
          </dd>
          <dt>Variants / runs</dt>
          <dd>
            {s.variants.length} / {s.run_ids.length}
          </dd>
          {s.prov_node_id ? (
            <>
              <dt>Provenance</dt>
              <dd>
                <a href={href(`/lineage/${s.prov_node_id}`, { direction: 'both' })}>
                  Open sweep lineage
                </a>
              </dd>
            </>
          ) : null}
        </dl>
      ) : null}
      {report.loading ? <Loading what="sweep report" /> : null}
      {report.error ? <ErrorBox error={report.error} /> : null}
      {report.data ? <ReportView report={report.data} /> : null}
    </Page>
  );
}

export function ReportView({ report }: { report: ReportOut }) {
  const p = pivot(report);
  const m = report.metric;
  let best: ReactNode = null;
  if (report.best)
    best = (
      <p>
        Best variant #{report.best.variant} (
        {Object.entries(report.best.params)
          .map(([k, v]) => `${k}=${show(v)}`)
          .join(', ')}
        ): <strong>{fmt(report.best.mean)}</strong>
        <RunLinks ids={report.best.run_ids} label="best mean" />
      </p>
    );
  return (
    <>
      <p>
        Metric <strong>{m.name}</strong> ({m.higher_is_better ? 'higher' : 'lower'} is better).{' '}
        {report.complete ? 'All runs finished.' : 'Incomplete: some runs are not finished.'} Every
        number links to the runs it is computed from.
      </p>
      {best}
      <table className="table grid">
        <caption>
          Mean {m.name} per variant: {p.rowF?.name ?? 'variant'} (rows)
          {p.colF ? ` × ${p.colF.name} (columns)` : ''}
        </caption>
        <thead>
          <tr>
            <th scope="col">{p.rowF?.name ?? ''}</th>
            {p.cols.map((c) => (
              <th scope="col" key={key(c)}>
                {p.colF ? show(c) : 'mean'}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {p.rows.map((rv) => (
            <tr key={key(rv)}>
              <th scope="row">{show(rv)}</th>
              {p.cols.map((cv) => (
                <td key={key(cv)}>
                  {p.variant(rv, cv).map((v) => (
                    <div key={v.variant}>
                      {fmt(v.mean)} <span className="small muted">n={v.n}</span>
                      <RunLinks ids={v.run_ids} label={`variant ${v.variant} mean`} />
                    </div>
                  ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Sensitivity</h2>
      <table className="table compact">
        <caption className="sr-only">Sensitivity per factor</caption>
        <thead>
          <tr>
            <th scope="col">Factor</th>
            <th scope="col">Range of level means</th>
            <th scope="col">Level means</th>
          </tr>
        </thead>
        <tbody>
          {[...report.sensitivity]
            .sort((a, b) => (b.range ?? -1) - (a.range ?? -1))
            .map((s) => (
              <tr key={s.factor}>
                <td>{s.factor}</td>
                <td>{fmt(s.range)}</td>
                <td>
                  {s.levels.map((l) => (
                    <div key={key(l.value)}>
                      {show(l.value)}: {fmt(l.mean)}
                      <RunLinks ids={l.run_ids} label={`${s.factor}=${show(l.value)} mean`} />
                    </div>
                  ))}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <h2>Runs</h2>
      <table className="table compact">
        <caption className="sr-only">Every run of the sweep</caption>
        <thead>
          <tr>
            <th scope="col">Run</th>
            <th scope="col">Variant</th>
            <th scope="col">Parameters</th>
            <th scope="col">Recording</th>
            <th scope="col">State</th>
            <th scope="col">{m.name}</th>
            <th scope="col">Lineage</th>
          </tr>
        </thead>
        <tbody>
          {report.cells.map((c) => (
            <tr key={c.run_id}>
              <td>
                <a href={href(`/runs/${c.run_id}`)} className="mono">
                  {shortId(c.run_id)}
                </a>
              </td>
              <td>{c.variant}</td>
              <td className="small">
                {Object.entries(c.params)
                  .map(([k, v]) => `${k}=${show(v)}`)
                  .join(', ')}
              </td>
              <td>
                <a href={href(`/recordings/${c.recording_id}`)} className="mono">
                  {shortId(c.recording_id)}
                </a>
              </td>
              <td>
                <StateBadge state={c.state} />
              </td>
              <td>
                <a href={href(`/runs/${c.run_id}`)} aria-label={`${fmt(c.value)}, run ${c.run_id}`}>
                  {fmt(c.value)}
                </a>
              </td>
              <td>
                {c.prov_node_id ? (
                  <a href={href(`/lineage/${c.prov_node_id}`, { direction: 'up' })}>
                    value lineage
                  </a>
                ) : (
                  '–'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
