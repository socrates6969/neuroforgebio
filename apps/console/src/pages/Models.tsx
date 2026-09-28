import { useRef, useState, type FormEvent } from 'react';
import { useRoles, useSession } from '../auth/session';
import { can } from '../authz/can';
import { ErrorBox, Loading, Mono, Page, StateBadge, fmtTime } from '../components/common';
import { LineageView } from '../components/LineageView';
import { href, navigate } from '../router';
import {
  PAGE,
  getModel,
  getVersion,
  getVersionLineage,
  getVocabulary,
  listDeployments,
  listModels,
  requestDeployment,
  type DeploymentOutcome,
} from '../registry/api';
import {
  CONTEXT_FIELDS,
  CONTROL_SETTINGS,
  DEPLOY_ACTION,
  JURISDICTION_PATTERN,
  LINEAGE_ACTION,
  UPLOAD_TAINT_REASON,
  labelOf,
  reasonText,
  weightsSourceText,
  type Option,
} from '../registry/context';
import type {
  ContextIn,
  DeploymentOut,
  FlagOut,
  Measurement,
  ModelCard,
  VersionOut,
  VersionSummary,
  VocabularyOut,
} from '../registry/types';
import { useAsync } from '../useAsync';

// ------------------------------------------------------------------------------------ list
export function ModelsPage() {
  const { client } = useSession();
  const [offset, setOffset] = useState(0);
  const list = useAsync((signal) => listModels(client, offset, signal), [client, offset]);

  return (
    <Page title="Models">
      <p className="small muted">
        Registered models of your tenant. A version is flagged <strong>retrain required</strong>{' '}
        when a subject whose data trained it withdrew consent.
      </p>
      {list.loading ? <Loading what="models" /> : null}
      {list.error ? <ErrorBox error={list.error} /> : null}
      {list.data ? (
        list.data.length === 0 ? (
          <p className="muted">No models registered yet.</p>
        ) : (
          <table className="table">
            <caption className="sr-only">Models</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Task</th>
                <th scope="col">Latest version</th>
                <th scope="col">Status</th>
                <th scope="col">Registered</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((m) => (
                <tr key={m.id}>
                  <td>
                    <a href={href(`/models/${m.id}`)}>{m.name}</a>
                  </td>
                  <td>{m.card.task}</td>
                  <td>{m.latest_version ? `v${m.latest_version.version}` : '–'}</td>
                  <td>
                    <TaintBadge flagged={m.retrain_required} />
                  </td>
                  <td>{fmtTime(m.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : null}
      <nav className="pager" aria-label="Model pages">
        <button
          type="button"
          className="btn ghost"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE))}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn ghost"
          disabled={!list.data || list.data.length < PAGE}
          onClick={() => setOffset(offset + PAGE)}
        >
          Next
        </button>
      </nav>
    </Page>
  );
}

export function TaintBadge({ flagged }: { flagged: boolean }) {
  return flagged ? (
    <span className="state state-flagged">retrain required</span>
  ) : (
    <span className="state state-ready">ok</span>
  );
}

// ---------------------------------------------------------------------------------- detail
export function ModelPage({ id, query }: { id: string; query: URLSearchParams }) {
  const { client } = useSession();
  const model = useAsync((signal) => getModel(client, id, signal), [client, id]);
  const m = model.data;
  const selected = m ? pickVersion(m.versions, query.get('version')) : undefined;

  return (
    <Page title={m ? `Model ${m.name}` : 'Model'}>
      {model.loading ? <Loading what="model" /> : null}
      {model.error ? <ErrorBox error={model.error} /> : null}
      {m?.retrain_required ? (
        <p className="alert" role="alert">
          A version of this model is flagged <strong>retrain required</strong>. The version details
          name the deletion job that caused it.
        </p>
      ) : null}
      {m ? <CardView card={m.card} /> : null}
      {m ? (
        <section aria-labelledby="versions-h">
          <h2 id="versions-h">Versions</h2>
          {m.versions.length === 0 ? (
            <p className="muted">No versions registered.</p>
          ) : (
            <table className="table">
              <caption className="sr-only">Versions of {m.name}</caption>
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Registered</th>
                  <th scope="col">Weights</th>
                  <th scope="col">Visibility</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {m.versions.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <a
                        href={href(`/models/${m.id}`, { version: String(v.version) })}
                        aria-current={v.version === selected?.version ? 'true' : undefined}
                      >
                        v{v.version}
                      </a>
                      {v.version === selected?.version ? (
                        <span className="badge">shown below</span>
                      ) : null}
                    </td>
                    <td>{fmtTime(v.created_at)}</td>
                    <td>{v.weights_source === 'upload' ? 'uploaded' : 'platform'}</td>
                    <td>{v.visibility}</td>
                    <td>
                      <TaintBadge flagged={v.retrain_required} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}
      {m && selected ? (
        <VersionPanel key={selected.id} modelId={m.id} version={selected.version} />
      ) : null}
      {m ? <Deployments modelId={m.id} selected={selected} /> : null}
    </Page>
  );
}

/** The version named in the URL, else the newest one. */
export function pickVersion(versions: VersionSummary[], wanted: string | null) {
  if (wanted) {
    const v = versions.find((x) => String(x.version) === wanted);
    if (v) return v;
  }
  return [...versions].sort((a, b) => b.version - a.version)[0];
}

function VersionPanel({ modelId, version }: { modelId: string; version: number }) {
  const { client } = useSession();
  const roles = useRoles();
  const v = useAsync(
    (signal) => getVersion(client, modelId, version, signal),
    [client, modelId, version],
  );
  if (v.loading) return <Loading what="version" />;
  if (v.error) return <ErrorBox error={v.error} />;
  const d = v.data;
  if (!d) return null;
  return (
    <section aria-labelledby="version-h">
      <h2 id="version-h">Version {d.version}</h2>
      <TaintPanel version={d} />
      <div className="card">
        <h3>Intended use</h3>
        <p className="prewrap" data-testid="intended-use">
          {d.intended_use}
        </p>
        <h3 id="restrictions-h">Use restrictions</h3>
        {d.use_restrictions.length === 0 ? (
          <p className="muted">None declared.</p>
        ) : (
          <ul aria-labelledby="restrictions-h" className="restrictions">
            {d.use_restrictions.map((r) => (
              <li key={r}>
                <Mono>{r}</Mono>
              </li>
            ))}
          </ul>
        )}
      </div>
      <dl className="kv card">
        <dt>Code commit</dt>
        <dd className="mono">{d.code_commit}</dd>
        <dt>Pipeline versions</dt>
        <dd className="mono">{d.pipeline_version_ids.join(', ') || '–'}</dd>
        <dt>Parent version</dt>
        <dd>{d.parent_version ? `v${d.parent_version}` : '–'}</dd>
        <dt>Training data</dt>
        <dd>{trainingText(d)}</dd>
        <dt>Weights</dt>
        <dd>
          {d.weights_format}, sha256 <Mono>{d.weights_sha256}</Mono>
        </dd>
        <dt>Weights source</dt>
        <dd data-testid="weights-source">{weightsSourceText(d.weights_source)}</dd>
        <dt>Visibility</dt>
        <dd>{d.visibility}</dd>
        <dt>Registered</dt>
        <dd>
          {fmtTime(d.created_at)} by {d.created_by}
        </dd>
      </dl>
      {can(roles, LINEAGE_ACTION) ? <VersionLineage modelId={modelId} version={version} /> : null}
    </section>
  );
}

export function trainingText(d: VersionOut): string {
  const t = d.manifest_summary;
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`;
  let s = `${plural(t.n_subjects, 'subject')} from ${plural(t.n_source_recordings, 'recording')}`;
  if (t.n_shards) s += `, ${t.n_shards} SISA shards`;
  if (t.n_excluded_subjects) s += `, ${t.n_excluded_subjects} withdrawn subject(s) excluded`;
  return s;
}

// ------------------------------------------------------------------------------------- card
const ROBUSTNESS_NOTE = 'Measured on perturbed inputs; not a robustness claim.';

export function CardView({ card }: { card: ModelCard }) {
  return (
    <section aria-labelledby="card-h" className="card">
      <h2 id="card-h">Model card</h2>
      <p className="prewrap">{card.summary}</p>
      <dl className="kv">
        <dt>Task</dt>
        <dd>{card.task}</dd>
        <dt>Inferences</dt>
        <dd>{card.inferences.join(', ')}</dd>
        <dt>Modalities</dt>
        <dd>{card.modalities.join(', ')}</dd>
        <dt>Contact</dt>
        <dd>{card.contact ?? '–'}</dd>
      </dl>
      <h3>Limitations</h3>
      <p className="prewrap">{card.limitations}</p>
      <MeasurementTable caption="Evaluation" rows={(card.evaluation ?? []).map((m) => ['', m])} />
      <MeasurementTable
        caption="Robustness"
        note={ROBUSTNESS_NOTE}
        rows={[
          ['Additive noise', card.robustness.noise],
          ['Channel dropout', card.robustness.channel_dropout],
          ['Adversarial', card.robustness.adversarial],
        ]}
      />
      {card.privacy_risk ? (
        <MeasurementTable
          caption="Privacy risk"
          note={`Membership inference on held-out split ${card.privacy_risk.held_out_split}.`}
          rows={[['Membership inference', card.privacy_risk.membership_inference]]}
        />
      ) : (
        <p className="small muted">
          No privacy-risk (membership inference) result recorded; required before publication.
        </p>
      )}
    </section>
  );
}

function MeasurementTable({
  caption,
  note,
  rows,
}: {
  caption: string;
  note?: string;
  rows: Array<[string, Measurement]>;
}) {
  if (rows.length === 0) return null;
  const named = rows.some(([k]) => k);
  return (
    <>
      <h3>{caption}</h3>
      {note ? <p className="small muted">{note}</p> : null}
      <table className="table compact">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {named ? <th scope="col">Test</th> : null}
            <th scope="col">Metric</th>
            <th scope="col">Value</th>
            <th scope="col">Method</th>
            <th scope="col">Split</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, m], i) => (
            <tr key={`${k}${i}`}>
              {named ? <td>{k}</td> : null}
              <td>{m.metric}</td>
              <td className="mono">{m.value}</td>
              <td>{m.method}</td>
              <td>{m.split ?? '–'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

// ------------------------------------------------------------------------------------ taint
export function TaintPanel({ version }: { version: VersionOut }) {
  if (!version.retrain_required) {
    return (
      <p className="small" data-testid="taint-status">
        <TaintBadge flagged={false} /> No consent withdrawal affects this version&apos;s training
        data.
      </p>
    );
  }
  return (
    <div className="alert taint" role="alert" data-testid="taint-status">
      <p>
        <strong>Retrain required.</strong>{' '}
        {version.taint.length > 0 && version.taint.every((t) => t.reason === UPLOAD_TAINT_REASON)
          ? 'A subject of your tenant withdrew consent after this version was registered. Its weights were uploaded, so the platform cannot tell whether that subject’s data trained it; retrain it on the platform.'
          : 'Data of a subject who withdrew consent was used to train this version; it has to be retrained without that data.'}{' '}
        {version.deployments_blocked
          ? 'Deployments of this version are blocked.'
          : 'Your tenant policy does not block its deployments.'}
      </p>
      {version.taint.length === 0 ? (
        <p className="small">The platform did not return the deletion job that caused the flag.</p>
      ) : (
        <ul aria-label="Reasons">
          {version.taint.map((t) => (
            <TaintItem key={t.deletion_job_id} t={t} />
          ))}
        </ul>
      )}
    </div>
  );
}

function TaintItem({ t }: { t: FlagOut }) {
  return (
    <li>
      Consent withdrawal: deletion job <Mono>{t.deletion_job_id}</Mono> flagged it on{' '}
      {fmtTime(t.created_at)}
      {t.block_deployments ? ' (deployments blocked)' : ''}. Reason: {t.reason}.
    </li>
  );
}

// ---------------------------------------------------------------------------------- lineage
function VersionLineage({ modelId, version }: { modelId: string; version: number }) {
  const { client } = useSession();
  const g = useAsync(
    (signal) => getVersionLineage(client, modelId, version, signal),
    [client, modelId, version],
  );
  return (
    <section aria-labelledby="lineage-h">
      <h3 id="lineage-h">Training lineage</h3>
      <p className="small">
        Where this version came from: training inputs, runs, source recordings and pipelines.
        {g.data ? ` ${g.data.n_training_subjects} training subject(s).` : ''}
      </p>
      {g.loading ? <Loading what="lineage" /> : null}
      {g.error ? <ErrorBox error={g.error} /> : null}
      {g.data ? (
        <>
          <p className="small">
            <a href={href(`/lineage/${g.data.root}`, { direction: 'up' })}>
              Open in the lineage explorer
            </a>
          </p>
          <LineageView
            graph={g.data}
            onReroot={(n) => navigate(`/lineage/${n.id}`, { direction: 'both' })}
          />
        </>
      ) : null}
    </section>
  );
}

// ------------------------------------------------------------------------------ deployments
function Deployments({ modelId, selected }: { modelId: string; selected?: VersionSummary }) {
  const { client } = useSession();
  const roles = useRoles();
  const list = useAsync((signal) => listDeployments(client, modelId, signal), [client, modelId]);
  return (
    <section aria-labelledby="deploy-h">
      <h2 id="deploy-h">Deployment requests</h2>
      {selected && can(roles, DEPLOY_ACTION) ? (
        <DeploymentForm
          key={`${modelId}:${selected.version}`}
          modelId={modelId}
          version={selected.version}
          retrainRequired={selected.retrain_required}
          onDone={list.reload}
        />
      ) : null}
      {list.loading ? <Loading what="deployments" /> : null}
      {list.error ? <ErrorBox error={list.error} /> : null}
      {list.data ? (
        list.data.length === 0 ? (
          <p className="muted">No deployment requests yet.</p>
        ) : (
          <DeploymentTable rows={list.data} />
        )
      ) : null}
    </section>
  );
}

export function DeploymentTable({ rows }: { rows: DeploymentOut[] }) {
  return (
    <table className="table">
      <caption className="sr-only">Deployment requests</caption>
      <thead>
        <tr>
          <th scope="col">Requested</th>
          <th scope="col">Version</th>
          <th scope="col">Declared context</th>
          <th scope="col">State</th>
          <th scope="col">Reasons</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((d) => (
          <tr key={d.id}>
            <td>
              {fmtTime(d.created_at)}
              <br />
              <span className="small muted">{d.requested_by}</span>
            </td>
            <td>v{d.version}</td>
            <td>{describeContext(d)}</td>
            <td>
              <StateBadge state={d.effective_state} />
              {d.effective_state !== d.state ? (
                <span className="small muted"> (was {d.state})</span>
              ) : null}
            </td>
            <td>
              <ReasonList d={d} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ReasonList({ d }: { d: DeploymentOut }) {
  const reasons = [...d.reasons];
  // A later taint blocks an approved deployment; the stored reasons predate it.
  if (d.effective_state === 'blocked' && !reasons.includes('retrain_required'))
    reasons.push('retrain_required');
  if (reasons.length === 0) return <>–</>;
  return (
    <ul className="reasons">
      {reasons.map((r) => (
        <li key={r}>{reasonText(r)}</li>
      ))}
    </ul>
  );
}

export function describeContext(d: DeploymentOut): string {
  const c = d.context as Partial<ContextIn>;
  const parts = [
    d.purpose,
    `${labelOf('setting', d.setting)} setting`,
    `jurisdiction ${d.jurisdiction}`,
  ];
  if (c.outputs) parts.push(`outputs: ${labelOf('outputs', c.outputs)}`);
  if (c.influences_behaviour) parts.push('influences behaviour');
  if (d.exception_id) parts.push(`exception ${d.exception_id}`);
  return parts.join('; ');
}

/** Form options from the platform vocabulary (never a control setting), else the built-in list. */
export function formOptions(vocab: VocabularyOut | null): Record<'setting' | 'outputs', Option[]> {
  const control = new Set(CONTROL_SETTINGS.map((o) => o.value));
  const opt = (field: 'setting' | 'outputs', values: string[]) =>
    values.filter((v) => !control.has(v)).map((v) => ({ value: v, label: labelOf(field, v) }));
  const builtIn = (name: 'setting' | 'outputs') =>
    CONTEXT_FIELDS.find((f) => f.name === name)!.options;
  return {
    setting: vocab ? opt('setting', vocab.settings) : builtIn('setting'),
    outputs: vocab ? opt('outputs', vocab.allowed_outputs) : builtIn('outputs'),
  };
}

export function DeploymentForm({
  modelId,
  version,
  retrainRequired = false,
  onDone,
}: {
  modelId: string;
  version: number;
  retrainRequired?: boolean;
  onDone: () => void;
}) {
  const { client } = useSession();
  const vocab = useAsync((signal) => getVocabulary(client, signal), [client]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [outcome, setOutcome] = useState<DeploymentOutcome | null>(null);
  const options = formOptions(vocab.data ?? null);
  // BUG-HUNT M11: a refusal/approval belongs to one model version. When the target changes, drop
  // the previous outcome at once (reset during render: no stale frame) and ignore a late answer
  // to a request made for the previous target.
  const target = `${modelId}:${version}`;
  const [shownFor, setShownFor] = useState(target);
  const current = useRef(target);
  current.current = target;
  if (shownFor !== target) {
    setShownFor(target);
    setBusy(false);
    setError(null);
    setOutcome(null);
  }

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const str = (k: string) => String(data.get(k) ?? '').trim();
    const context: ContextIn = {
      jurisdiction: str('jurisdiction').toUpperCase(),
      setting: str('setting'),
      purpose: str('purpose'),
      outputs: str('outputs') as ContextIn['outputs'],
      influences_behaviour: data.get('influences_behaviour') === 'on',
    };
    if (str('exception_id')) context.exception_id = str('exception_id');
    setBusy(true);
    setError(null);
    setOutcome(null);
    const sentFor = target;
    try {
      const out = await requestDeployment(client, modelId, version, context);
      onDone();
      if (current.current === sentFor) setOutcome(out);
    } catch (err) {
      if (current.current === sentFor) setError(err as Error);
    } finally {
      if (current.current === sentFor) setBusy(false);
    }
  };

  return (
    <form className="card deploy-form" onSubmit={submit} aria-labelledby="deploy-form-h">
      <h3 id="deploy-form-h">Request a deployment of version {version}</h3>
      <p className="small">
        Declare where and how the model will be used. The platform checks the request against the
        version&apos;s restrictions and the regulatory rules, and refuses it with the reason if it
        does not fit. Refusals are recorded.
      </p>
      <p className="small" data-testid="control-note">
        Stimulation, neuromodulation and actuator control are not offered: the platform never
        controls hardware (SEC-092) and refuses such requests.
      </p>
      {retrainRequired ? (
        <p className="small muted">
          This version is flagged retrain required; a request will be refused or blocked.
        </p>
      ) : null}
      <div className="field">
        <label htmlFor="ctx-purpose">Purpose</label>
        <input
          id="ctx-purpose"
          name="purpose"
          required
          maxLength={500}
          aria-describedby="ctx-purpose-help"
        />
        <p id="ctx-purpose-help" className="small muted">
          What the outputs are used for, e.g. &quot;offline sleep-stage research analysis&quot;.
        </p>
      </div>
      {CONTEXT_FIELDS.map((f) => (
        <div className="field" key={f.name}>
          <label htmlFor={`ctx-${f.name}`}>{f.label}</label>
          <select id={`ctx-${f.name}`} name={f.name} required defaultValue={f.initial ?? ''}>
            {f.initial ? null : (
              <option value="" disabled>
                Choose…
              </option>
            )}
            {options[f.name].map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      ))}
      <div className="field">
        <label htmlFor="ctx-jurisdiction">Jurisdiction</label>
        <input
          id="ctx-jurisdiction"
          name="jurisdiction"
          required
          pattern={JURISDICTION_PATTERN}
          maxLength={6}
          aria-describedby="ctx-jurisdiction-help"
        />
        <p id="ctx-jurisdiction-help" className="small muted">
          EU, a two-letter country code (e.g. DE), or a subdivision such as US-CO.
        </p>
      </div>
      <div className="field check">
        <input id="ctx-influence" name="influences_behaviour" type="checkbox" />
        <label htmlFor="ctx-influence">
          Outputs are used to influence the person&apos;s behaviour
        </label>
      </div>
      <div className="field">
        <label htmlFor="ctx-exception">Exception record ID (optional)</label>
        <input
          id="ctx-exception"
          name="exception_id"
          aria-describedby="ctx-exception-help"
          pattern="[0-9a-fA-F\-]{36}"
        />
        <p id="ctx-exception-help" className="small muted">
          Only for a documented medical or safety exception on record.
        </p>
      </div>
      <button className="btn" type="submit" disabled={busy}>
        {busy ? 'Requesting…' : 'Request deployment'}
      </button>
      <div aria-live="polite">
        {outcome?.kind === 'approved' ? (
          <p role="status">
            Request recorded: <StateBadge state={outcome.deployment.effective_state} />
          </p>
        ) : null}
        {outcome?.kind === 'refused' ? (
          <div className="alert" role="alert" data-testid="refusal">
            <p>
              <strong>Refused.</strong> The refusal is recorded
              {outcome.deploymentId ? (
                <>
                  {' '}
                  as <Mono>{outcome.deploymentId}</Mono>
                </>
              ) : null}
              .
            </p>
            <ul aria-label="Refusal reasons">
              {outcome.reasons.map((r) => (
                <li key={r}>{reasonText(r)}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}
