import { useEffect, useState, useSyncExternalStore, type FormEvent } from 'react';
import { useRoles, useSession } from '../auth/session';
import { can } from '../authz/can';
import { ErrorBox, Loading, Page, StateBadge, fmtTime, shortId } from '../components/common';
import { href, navigate } from '../router';
import { TERMINAL_RUN_STATES, runRegistry } from '../runs';
import { useAsync } from '../useAsync';

export function RunsPage() {
  const runs = useSyncExternalStore(
    (cb) => runRegistry.subscribe(cb),
    () => runRegistry.list(),
  );
  const [id, setId] = useState('');
  const open = (e: FormEvent) => {
    e.preventDefault();
    if (id.trim()) navigate(`/runs/${id.trim()}`);
  };
  return (
    <Page title="Runs">
      <form className="inline-form card" onSubmit={open}>
        <label htmlFor="run-id">Open a run by ID</label>
        <input
          id="run-id"
          value={id}
          onChange={(e) => setId(e.target.value)}
          pattern="[0-9a-fA-F-]{36}"
        />
        <button className="btn" type="submit">
          Open
        </button>
      </form>
      <h2>This session</h2>
      <p className="small muted">
        Runs started or opened since you signed in (kept in memory only). A tenant-wide run list
        needs a list route in the platform API.
      </p>
      {runs.length === 0 ? (
        <p className="muted">No runs yet: start one from a recording.</p>
      ) : (
        <table className="table">
          <caption className="sr-only">Runs in this session</caption>
          <thead>
            <tr>
              <th scope="col">Run</th>
              <th scope="col">Pipeline</th>
              <th scope="col">Recording</th>
              <th scope="col">State</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>
                  <a href={href(`/runs/${r.id}`)} className="mono">
                    {shortId(r.id)}
                  </a>
                </td>
                <td>{r.pipeline_ref}</td>
                <td>
                  <a href={href(`/recordings/${r.recording_id}`)} className="mono">
                    {shortId(r.recording_id)}
                  </a>
                </td>
                <td>
                  <StateBadge state={r.state} />
                </td>
                <td>{fmtTime(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Page>
  );
}

export function RunPage({ id, pollMs = 2000 }: { id: string; pollMs?: number }) {
  const { client } = useSession();
  const roles = useRoles();
  const run = useAsync(
    (signal) => client.call('getRun', { path: { run_id: id }, signal }),
    [client, id],
  );
  const [cancelError, setCancelError] = useState<Error | null>(null);
  const r = run.data;

  useEffect(() => {
    if (r) runRegistry.remember(r);
    if (!r || TERMINAL_RUN_STATES.has(r.state)) return;
    const t = window.setTimeout(run.reload, pollMs);
    return () => window.clearTimeout(t);
  }, [r, run.reload, pollMs]);

  const cancel = async () => {
    setCancelError(null);
    try {
      await client.call('cancelRun', { path: { run_id: id } });
      run.reload();
    } catch (e) {
      setCancelError(e as Error);
    }
  };

  return (
    <Page title="Run">
      <p>
        <a href={href('/runs')}>All runs</a>
      </p>
      {run.loading && !r ? <Loading what="run" /> : null}
      {run.error ? <ErrorBox error={run.error} /> : null}
      {r ? (
        <>
          <dl className="kv card">
            <dt>Run ID</dt>
            <dd className="mono">{r.id}</dd>
            <dt>State</dt>
            <dd>
              <StateBadge state={r.state} /> {r.cancel_requested ? '(cancel requested)' : ''}
            </dd>
            <dt>Pipeline</dt>
            <dd>
              {r.pipeline_ref} <span className="mono small">{r.pipeline_version_id}</span>
            </dd>
            <dt>Recording</dt>
            <dd>
              <a href={href(`/recordings/${r.recording_id}`)} className="mono">
                {r.recording_id}
              </a>
            </dd>
            <dt>Seed</dt>
            <dd>{r.seed ?? '–'}</dd>
            <dt>Attempt</dt>
            <dd>{r.attempt}</dd>
            <dt>Started / finished</dt>
            <dd>
              {fmtTime(r.started_at)} / {fmtTime(r.finished_at)}
            </dd>
            {r.error ? (
              <>
                <dt>Error</dt>
                <dd>{r.error}</dd>
              </>
            ) : null}
          </dl>
          <div className="page-actions">
            {r.prov_activity_id ? (
              <a
                className="btn"
                href={href(`/lineage/${r.prov_activity_id}`, { direction: 'both' })}
              >
                Open lineage
              </a>
            ) : (
              <span className="muted small">
                Lineage appears once the run has committed its provenance.
              </span>
            )}
            {can(roles, 'run:cancel') &&
            !TERMINAL_RUN_STATES.has(r.state) &&
            !r.cancel_requested ? (
              <button type="button" className="btn ghost" onClick={cancel}>
                Cancel run
              </button>
            ) : null}
          </div>
          {cancelError ? <ErrorBox error={cancelError} /> : null}
          <h2>Artifacts</h2>
          {r.artifacts && r.artifacts.length > 0 ? (
            <table className="table">
              <caption className="sr-only">Run artifacts</caption>
              <thead>
                <tr>
                  <th scope="col">Step</th>
                  <th scope="col">Name</th>
                  <th scope="col">Size [bytes]</th>
                  <th scope="col">SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {r.artifacts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.step}</td>
                    <td>{a.name}</td>
                    <td>{a.size_bytes}</td>
                    <td className="mono small">{a.sha256}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">
              No visible artifacts (they appear only after provenance is committed).
            </p>
          )}
          <details className="card">
            <summary>Run record (every step default, as executed)</summary>
            <pre className="code">{JSON.stringify(r.record, null, 2)}</pre>
          </details>
        </>
      ) : null}
    </Page>
  );
}
