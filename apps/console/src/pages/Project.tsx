import { useState, type FormEvent } from 'react';
import { useRoles, useSession } from '../auth/session';
import { can } from '../authz/can';
import { ErrorBox, Loading, Page, fmtTime } from '../components/common';
import { href } from '../router';
import { useAsync } from '../useAsync';

export function ProjectPage({ id }: { id: string }) {
  const { client } = useSession();
  const roles = useRoles();
  const project = useAsync(
    (signal) => client.call('getProject', { path: { project_id: id }, signal }),
    [client, id],
  );
  const datasets = useAsync(
    (signal) =>
      client.call('listDatasets', { path: { project_id: id }, query: { limit: 200 }, signal }),
    [client, id],
  );

  return (
    <Page title={project.data ? `Project: ${project.data.name}` : 'Project'}>
      <p>
        <a href={href('/projects')}>All projects</a>
      </p>
      {project.error ? <ErrorBox error={project.error} /> : null}
      {project.data?.description ? <p>{project.data.description}</p> : null}
      <h2>Datasets</h2>
      {can(roles, 'dataset:create') ? (
        <CreateDataset projectId={id} onCreated={datasets.reload} />
      ) : null}
      {datasets.loading ? <Loading what="datasets" /> : null}
      {datasets.error ? <ErrorBox error={datasets.error} /> : null}
      {datasets.data && datasets.data.length === 0 ? (
        <p className="muted">No datasets yet.</p>
      ) : null}
      {datasets.data && datasets.data.length > 0 ? (
        <table className="table">
          <caption className="sr-only">Datasets</caption>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Description</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {datasets.data.map((d) => (
              <tr key={d.id}>
                <td>
                  <a href={href(`/datasets/${d.id}`)}>{d.name}</a>
                </td>
                <td>{d.description ?? ''}</td>
                <td>{fmtTime(d.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </Page>
  );
}

function CreateDataset({ projectId, onCreated }: { projectId: string; onCreated: () => void }) {
  const { client } = useSession();
  const [name, setName] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await client.call('createDataset', { path: { project_id: projectId }, body: { name } });
      setName('');
      onCreated();
    } catch (err) {
      setError(err as Error);
    }
  };
  return (
    <form className="inline-form card" onSubmit={submit}>
      <label htmlFor="new-dataset">New dataset</label>
      <input
        id="new-dataset"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        maxLength={200}
      />
      <button className="btn" type="submit" disabled={!name.trim()}>
        Create
      </button>
      {error ? <ErrorBox error={error} /> : null}
    </form>
  );
}
