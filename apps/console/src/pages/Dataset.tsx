import { useState, type FormEvent } from 'react';
import { useRoles, useSession } from '../auth/session';
import { can } from '../authz/can';
import { ErrorBox, Loading, Page, StateBadge, fmtTime } from '../components/common';
import { href } from '../router';
import { uploadFile, type UploadProgress } from '../upload';
import { useAsync } from '../useAsync';

export function DatasetPage({ id }: { id: string }) {
  const { client } = useSession();
  const roles = useRoles();
  const dataset = useAsync(
    (signal) => client.call('getDataset', { path: { dataset_id: id }, signal }),
    [client, id],
  );
  const subjects = useAsync(
    (signal) =>
      client.call('listSubjects', { path: { dataset_id: id }, query: { limit: 200 }, signal }),
    [client, id],
  );
  return (
    <Page title={dataset.data ? `Dataset: ${dataset.data.name}` : 'Dataset'}>
      {dataset.data ? (
        <p>
          <a href={href(`/projects/${dataset.data.project_id}`)}>Back to project</a>
        </p>
      ) : null}
      {dataset.error ? <ErrorBox error={dataset.error} /> : null}
      <h2>Subjects</h2>
      {can(roles, 'subject:create') ? (
        <CreateNamed
          label="New subject (pseudonymous study code)"
          id="new-subject"
          onSubmit={(label) =>
            client
              .call('createSubject', { path: { dataset_id: id }, body: { label } })
              .then(subjects.reload)
          }
        />
      ) : null}
      {subjects.loading ? <Loading what="subjects" /> : null}
      {subjects.error ? <ErrorBox error={subjects.error} /> : null}
      {subjects.data?.length === 0 ? <p className="muted">No subjects yet.</p> : null}
      {subjects.data?.map((s) => (
        <details key={s.id} className="card">
          <summary>
            Subject <strong>{s.label}</strong>
          </summary>
          <SubjectSessions datasetId={id} subjectId={s.id} />
        </details>
      ))}
    </Page>
  );
}

function SubjectSessions({ datasetId, subjectId }: { datasetId: string; subjectId: string }) {
  const { client } = useSession();
  const roles = useRoles();
  const sessions = useAsync(
    (signal) =>
      client.call('listSessions', {
        path: { subject_id: subjectId },
        query: { limit: 200 },
        signal,
      }),
    [client, subjectId],
  );
  return (
    <div className="nested">
      {can(roles, 'session:create') ? (
        <CreateNamed
          label="New session label"
          id={`new-session-${subjectId}`}
          onSubmit={(label) =>
            client
              .call('createSession', { path: { subject_id: subjectId }, body: { label } })
              .then(sessions.reload)
          }
        />
      ) : null}
      {sessions.loading ? <Loading what="sessions" /> : null}
      {sessions.error ? <ErrorBox error={sessions.error} /> : null}
      {sessions.data?.length === 0 ? <p className="muted">No sessions.</p> : null}
      {sessions.data?.map((se) => (
        <section key={se.id} className="session" aria-label={`Session ${se.label}`}>
          <h3>Session {se.label}</h3>
          <SessionRecordings
            sessionId={se.id}
            datasetId={datasetId}
            canUpload={can(roles, 'upload:create')}
          />
        </section>
      ))}
    </div>
  );
}

function SessionRecordings({
  sessionId,
  datasetId,
  canUpload,
}: {
  sessionId: string;
  datasetId: string;
  canUpload: boolean;
}) {
  const { client } = useSession();
  const recs = useAsync(
    (signal) =>
      client.call('listRecordings', {
        path: { session_id: sessionId },
        query: { limit: 200 },
        signal,
      }),
    [client, sessionId],
  );
  return (
    <>
      {recs.loading ? <Loading what="recordings" /> : null}
      {recs.error ? <ErrorBox error={recs.error} /> : null}
      {recs.data && recs.data.length > 0 ? (
        <table className="table compact">
          <caption className="sr-only">Recordings</caption>
          <thead>
            <tr>
              <th scope="col">Recording</th>
              <th scope="col">Format</th>
              <th scope="col">Duration [s]</th>
              <th scope="col">State</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {recs.data.map((r) => (
              <tr key={r.id}>
                <td>
                  <a href={href(`/recordings/${r.id}`)}>{r.label}</a>
                </td>
                <td>{r.source_format ?? '–'}</td>
                <td>{r.duration_s?.toFixed(1) ?? '–'}</td>
                <td>
                  <StateBadge state={r.state} />
                </td>
                <td>{fmtTime(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : recs.data ? (
        <p className="muted">No recordings in this session.</p>
      ) : null}
      {canUpload ? (
        <UploadForm datasetId={datasetId} sessionId={sessionId} onDone={recs.reload} />
      ) : null}
    </>
  );
}

function UploadForm({
  datasetId,
  sessionId,
  onDone,
}: {
  datasetId: string;
  sessionId: string;
  onDone: () => void;
}) {
  const { client } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [synthetic, setSynthetic] = useState(true);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const inputId = `upload-${sessionId}`;
  const busy = progress !== null && !['done', 'failed'].includes(progress.phase);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError(null);
    try {
      const up = await uploadFile(
        client,
        { datasetId, sessionId, file, synthetic, origin: window.location.origin },
        setProgress,
      );
      if (up.state !== 'done') setError(new Error(up.error ?? `upload ${up.state}`));
      onDone();
    } catch (err) {
      setError(err as Error);
      setProgress(null);
    }
  };

  return (
    <form className="upload card" onSubmit={submit}>
      <label htmlFor={inputId}>
        Upload a recording file (EDF, BDF, BrainVision zip, XDF, NWB, BIDS zip)
      </label>
      <input id={inputId} type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <label className="check">
        <input
          type="checkbox"
          checked={synthetic}
          onChange={(e) => setSynthetic(e.target.checked)}
        />
        Synthetic or licence-checked public data (required outside production, SEC-071)
      </label>
      <button className="btn" type="submit" disabled={!file || busy}>
        Upload
      </button>
      <p role="status" className="small">
        {progress
          ? progress.phase === 'uploading'
            ? `Uploading part ${progress.partsDone} of ${progress.parts}`
            : progress.phase === 'done'
              ? `Upload converted: ${progress.upload?.recording_ids.length ?? 0} recording(s)`
              : `Upload ${progress.phase}${progress.upload ? ` (${progress.upload.state})` : ''}`
          : ''}
      </p>
      {progress?.phase === 'done' && progress.upload ? (
        <ul>
          {progress.upload.recording_ids.map((rid) => (
            <li key={rid}>
              <a href={href(`/recordings/${rid}`)}>Open recording {rid.slice(0, 8)}…</a>
            </li>
          ))}
        </ul>
      ) : null}
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}

function CreateNamed({
  label,
  id,
  onSubmit,
}: {
  label: string;
  id: string;
  onSubmit: (value: string) => Promise<unknown>;
}) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await onSubmit(value);
      setValue('');
    } catch (err) {
      setError(err as Error);
    }
  };
  return (
    <form className="inline-form" onSubmit={submit}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        required
        maxLength={200}
      />
      <button className="btn" type="submit" disabled={!value.trim()}>
        Create
      </button>
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}
