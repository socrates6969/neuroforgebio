import { useState, type FormEvent } from 'react';
import { useRoles, useSession } from '../auth/session';
import { can } from '../authz/can';
import { ErrorBox, Loading, Page, fmtTime } from '../components/common';
import { href } from '../router';
import { useAsync } from '../useAsync';

const PAGE = 50;

export function ProjectsPage() {
  const { client } = useSession();
  const roles = useRoles();
  const [offset, setOffset] = useState(0);
  const list = useAsync(
    (signal) => client.call('listProjects', { query: { limit: PAGE, offset }, signal }),
    [client, offset],
  );

  return (
    <Page title="Projects">
      {can(roles, 'project:create') ? <CreateProject onCreated={list.reload} /> : null}
      {list.loading ? <Loading what="projects" /> : null}
      {list.error ? <ErrorBox error={list.error} /> : null}
      {list.data ? (
        list.data.length === 0 ? (
          <p className="muted">No projects yet.</p>
        ) : (
          <table className="table">
            <caption className="sr-only">Projects</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Description</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {list.data.map((p) => (
                <tr key={p.id}>
                  <td>
                    <a href={href(`/projects/${p.id}`)}>{p.name}</a>
                  </td>
                  <td>{p.description ?? ''}</td>
                  <td>{fmtTime(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : null}
      <nav className="pager" aria-label="Project pages">
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

function CreateProject({ onCreated }: { onCreated: () => void }) {
  const { client } = useSession();
  const [name, setName] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await client.call('createProject', { body: { name } });
      setName('');
      onCreated();
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="inline-form card" onSubmit={submit}>
      <label htmlFor="new-project">New project</label>
      <input
        id="new-project"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        maxLength={200}
      />
      <button className="btn" type="submit" disabled={busy || !name.trim()}>
        Create
      </button>
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}
