// API-key management (BUILD-GUIDE 4.8; SEC-014, SEC-017): list, create, revoke.
// - The secret is returned by the server ONCE (POST /v1/api-keys). It lives only in this
//   component's state until the user dismisses it; it is never written to storage, the URL or logs,
//   and the list never contains it.
// - A revoked key is refused by the platform at once for new requests and within 60 s on open
//   streams. Role checks here only hide controls; the server authorizes every call.
import { useState, type FormEvent } from 'react';
import type { ApiKeyIssued, ApiKeyOut } from '../api/generated';
import { useRoles, useSession } from '../auth/session';
import { can } from '../authz/can';
import { ErrorBox, Loading, Page, fmtTime } from '../components/common';
import { useAsync } from '../useAsync';

const PAGE = 50;
// Roles a console user may hand to a key (the server enforces the real delegation rules: admin-class
// roles are never delegable).
const KEY_ROLES = ['scientist', 'viewer'] as const;
const SCOPES = ['metadata:read', 'metadata:write', 'data:read', 'data:write'] as const;

export function keyStatus(k: ApiKeyOut, now = Date.now()): 'revoked' | 'expired' | 'active' {
  if (k.revoked_at) return 'revoked';
  if (Date.parse(k.expires_at) <= now) return 'expired';
  return 'active';
}

export function ApiKeysPage() {
  const { client } = useSession();
  const roles = useRoles();
  const [offset, setOffset] = useState(0);
  const [issued, setIssued] = useState<ApiKeyIssued | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const list = useAsync(
    (signal) => client.call('listApiKeys', { query: { limit: PAGE, offset }, signal }),
    [client, offset],
  );

  const revoke = async (k: ApiKeyOut) => {
    if (!window.confirm(`Revoke the key "${k.name}" (${k.public_id})? This cannot be undone.`))
      return;
    setError(null);
    try {
      await client.call('revokeApiKey', { path: { key_id: k.id } });
      list.reload();
    } catch (err) {
      setError(err as Error);
    }
  };

  return (
    <Page title="API keys">
      <p className="small">
        Keys let scripts and the SDK call the platform. A key has roles, scopes and an expiry (at
        most 365 days). Revoking a key stops it at once for new requests and within 60 seconds on
        open streams.
      </p>
      {issued ? <IssuedKey issued={issued} onDone={() => setIssued(null)} /> : null}
      {can(roles, 'apikey:create') && !issued ? (
        <CreateKey
          onCreated={(k) => {
            setIssued(k);
            list.reload();
          }}
        />
      ) : null}
      {error ? <ErrorBox error={error} /> : null}
      {list.loading ? <Loading what="API keys" /> : null}
      {list.error ? <ErrorBox error={list.error} /> : null}
      {list.data ? (
        list.data.length === 0 ? (
          <p className="muted">No API keys yet.</p>
        ) : (
          <table className="table">
            <caption className="sr-only">API keys</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Key ID</th>
                <th scope="col">Roles</th>
                <th scope="col">Scopes</th>
                <th scope="col">Expires</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((k) => {
                const status = keyStatus(k);
                return (
                  <tr key={k.id}>
                    <td>{k.name}</td>
                    <td className="mono">{k.public_id}</td>
                    <td>{k.roles.join(', ')}</td>
                    <td className="small">{k.scopes.join(', ')}</td>
                    <td>{fmtTime(k.expires_at)}</td>
                    <td>{status}</td>
                    <td>
                      {status === 'active' && can(roles, 'apikey:revoke') ? (
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={() => void revoke(k)}
                          aria-label={`Revoke ${k.name}`}
                        >
                          Revoke
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )
      ) : null}
      <nav className="pager" aria-label="API key pages">
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

function IssuedKey({ issued, onDone }: { issued: ApiKeyIssued; onDone: () => void }) {
  return (
    <section className="card" aria-labelledby="issued-title">
      <h2 id="issued-title">Key created: copy it now</h2>
      <p role="status">
        This is the only time the key is shown. Store it in a secret manager; the platform keeps
        only a hash.
      </p>
      <label htmlFor="issued-key">API key for {issued.name}</label>
      <input
        id="issued-key"
        className="mono"
        readOnly
        value={issued.key}
        onFocus={(e) => e.currentTarget.select()}
        autoComplete="off"
        spellCheck={false}
      />
      <button type="button" className="btn" onClick={onDone}>
        I have stored the key
      </button>
    </section>
  );
}

function CreateKey({ onCreated }: { onCreated: (k: ApiKeyIssued) => void }) {
  const { client } = useSession();
  const [name, setName] = useState('');
  const [roles, setRoles] = useState<string[]>(['viewer']);
  const [scopes, setScopes] = useState<string[]>(['metadata:read']);
  const [days, setDays] = useState(90);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const toggle = (list: string[], v: string) =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const k = await client.call('createApiKey', {
        body: { name: name.trim(), roles, scopes, expires_in_days: days },
      });
      setName('');
      onCreated(k);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };
  const valid = name.trim() && roles.length > 0 && scopes.length > 0 && days >= 1 && days <= 365;
  return (
    <form className="card stack" onSubmit={submit} aria-labelledby="new-key-title">
      <h2 id="new-key-title">New API key</h2>
      <label htmlFor="key-name">Name</label>
      <input
        id="key-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        maxLength={100}
      />
      <fieldset>
        <legend>Roles</legend>
        {KEY_ROLES.map((r) => (
          <label key={r} className="check">
            <input
              type="checkbox"
              checked={roles.includes(r)}
              onChange={() => setRoles(toggle(roles, r))}
            />{' '}
            {r}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Scopes</legend>
        {SCOPES.map((s) => (
          <label key={s} className="check">
            <input
              type="checkbox"
              checked={scopes.includes(s)}
              onChange={() => setScopes(toggle(scopes, s))}
            />{' '}
            <span className="mono">{s}</span>
          </label>
        ))}
      </fieldset>
      <label htmlFor="key-days">Expires in (days, 1 to 365)</label>
      <input
        id="key-days"
        type="number"
        min={1}
        max={365}
        value={days}
        onChange={(e) => setDays(Number(e.target.value))}
      />
      <button className="btn" type="submit" disabled={busy || !valid}>
        Create key
      </button>
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}
