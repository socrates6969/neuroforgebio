import { useEffect, useMemo, useState, type FormEvent } from 'react';
import type { RecordingOut } from '../api/generated';
import { useRoles, useSession } from '../auth/session';
import { can, canReadQuarantined } from '../authz/can';
import { ErrorBox, Loading, Page, StateBadge, fmtTime } from '../components/common';
import { SignalPlot } from '../components/SignalPlot';
import { navigate } from '../router';
import { runRegistry } from '../runs';
import { chooseLevel, fetchTraces, type Trace } from '../signal/window';
import { useAsync } from '../useAsync';

const PLOT_WIDTH_GUESS = 1000;

export function RecordingPage({ id }: { id: string }) {
  const { client } = useSession();
  const roles = useRoles();
  const rec = useAsync(
    (signal) => client.call('getRecording', { path: { recording_id: id }, signal }),
    [client, id],
  );
  const r = rec.data;
  const quarantinedHidden = r?.state === 'quarantined' && !canReadQuarantined(roles);
  return (
    <Page title={r ? `Recording: ${r.label}` : 'Recording'}>
      {rec.loading ? <Loading what="recording" /> : null}
      {rec.error ? <ErrorBox error={rec.error} /> : null}
      {r ? (
        <>
          <dl className="kv card">
            <dt>ID</dt>
            <dd className="mono">{r.id}</dd>
            <dt>State</dt>
            <dd>
              <StateBadge state={r.state} />
            </dd>
            <dt>Format</dt>
            <dd>{r.source_format ?? '–'}</dd>
            <dt>Duration</dt>
            <dd>{r.duration_s != null ? `${r.duration_s.toFixed(2)} s` : '–'}</dd>
            <dt>Channels</dt>
            <dd>{r.channels?.length ?? 0}</dd>
            <dt>Created</dt>
            <dd>{fmtTime(r.created_at)}</dd>
          </dl>
          {quarantinedHidden ? (
            <p className="alert" role="alert">
              This recording is quarantined until the consent policy allows access; only owners,
              admins and data stewards can view its data.
            </p>
          ) : can(roles, 'signal:read') ? (
            <Viewer rec={r} />
          ) : null}
          {can(roles, 'run:create') ? <RunForm recordingId={r.id} /> : null}
        </>
      ) : null}
    </Page>
  );
}

function Viewer({ rec }: { rec: RecordingOut }) {
  const { client } = useSession();
  const channels = rec.channels ?? [];
  const sfreq = channels[0]?.sampling_rate ?? 0;
  const duration = rec.duration_s ?? 0;
  const [start, setStart] = useState(0);
  const [span, setSpan] = useState(() => Math.min(10, duration || 10));
  const [nch, setNch] = useState(() => Math.min(8, channels.length || 1));
  const [data, setData] = useState<{ level: number; traces: Trace[]; truncated: boolean } | null>(
    null,
  );
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);

  const end = Math.min(duration || start + span, start + span);
  const chanSpec = useMemo(
    () =>
      channels
        .slice(0, nch)
        .map((c) => c.index)
        .join(','),
    [channels, nch],
  );
  const level = chooseLevel(sfreq || 1, end - start, nch, PLOT_WIDTH_GUESS);

  useEffect(() => {
    if (!(end > start) || !sfreq) return;
    const ac = new AbortController();
    setLoading(true);
    setError(null);
    fetchTraces(client, { recordingId: rec.id, start, end, channels: chanSpec, level }, ac.signal)
      .then((d) => !ac.signal.aborted && setData(d))
      .catch((e: Error) => !ac.signal.aborted && setError(e))
      .finally(() => !ac.signal.aborted && setLoading(false));
    return () => ac.abort();
  }, [client, rec.id, start, end, chanSpec, level, sfreq]);

  if (!sfreq) return <p className="muted">No channel metadata: nothing to plot.</p>;
  const step = span / 2;
  return (
    <section aria-labelledby="viewer-title" className="card">
      <h2 id="viewer-title">Signal viewer</h2>
      <div className="controls">
        <button
          type="button"
          className="btn ghost"
          disabled={start <= 0}
          onClick={() => setStart(Math.max(0, start - step))}
        >
          Earlier
        </button>
        <button
          type="button"
          className="btn ghost"
          disabled={duration > 0 && end >= duration}
          onClick={() => setStart(Math.min(Math.max(0, duration - span), start + step))}
        >
          Later
        </button>
        <label>
          Window [s]
          <select value={span} onChange={(e) => setSpan(Number(e.target.value))}>
            {[1, 2, 5, 10, 30, 60, 300, 1800].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Channels
          <input
            type="number"
            min={1}
            max={Math.max(1, channels.length)}
            value={nch}
            onChange={(e) =>
              setNch(Math.max(1, Math.min(channels.length, Number(e.target.value) || 1)))
            }
          />
        </label>
      </div>
      <p className="small muted" role="status">
        {start.toFixed(2)}–{end.toFixed(2)} s, pyramid level {data?.level ?? level}
        {data && data.level > 0 ? ' (block mean with min/max envelope)' : ' (raw samples)'}
        {loading ? ', loading…' : ''}
      </p>
      {error ? <ErrorBox error={error} /> : null}
      {data ? (
        <SignalPlot
          traces={data.traces}
          span={[start, end]}
          label={`Signal plot, ${data.traces.length} channels, ${start.toFixed(1)} to ${end.toFixed(1)} seconds`}
        />
      ) : null}
    </section>
  );
}

function RunForm({ recordingId }: { recordingId: string }) {
  const { client } = useSession();
  const [pipeline, setPipeline] = useState('eeg-basic@1.0.0');
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const run = await client.call('createRun', { body: { pipeline, recording_id: recordingId } });
      runRegistry.remember(run);
      navigate(`/runs/${run.id}`);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="inline-form card" onSubmit={submit}>
      <label htmlFor="pipeline-ref">Run pipeline (name@semver or PipelineVersion ID)</label>
      <input
        id="pipeline-ref"
        value={pipeline}
        onChange={(e) => setPipeline(e.target.value)}
        required
      />
      <button className="btn" type="submit" disabled={busy || !pipeline.trim()}>
        Start run
      </button>
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}
