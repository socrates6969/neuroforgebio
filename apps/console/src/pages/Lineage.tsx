import { useState, type FormEvent } from 'react';
import type { LineageGraph } from '../api/types';
import { useSession } from '../auth/session';
import { ErrorBox, Loading, Page } from '../components/common';
import { LineageView } from '../components/LineageView';
import { flowTypes, mergeGraphs } from '../lineage/graph';
import { navigate } from '../router';
import { useAsync } from '../useAsync';

export type Direction = 'up' | 'down' | 'both';

export function LineagePage({ id, query }: { id: string; query: URLSearchParams }) {
  const { client } = useSession();
  const direction = (
    ['up', 'down', 'both'].includes(query.get('direction') ?? '') ? query.get('direction') : 'both'
  ) as Direction;
  const depthRaw = query.get('depth');
  const depth = depthRaw && /^\d+$/.test(depthRaw) ? Number(depthRaw) : undefined;
  const [nodeInput, setNodeInput] = useState(id);

  const graph = useAsync(
    async (signal) => {
      if (!id) return null;
      const get = (dir: 'up' | 'down') =>
        client.call('getLineage', {
          path: { node_id: id },
          query: { direction: dir, depth },
          signal,
        }) as Promise<unknown> as Promise<LineageGraph>;
      const parts =
        direction === 'both' ? await Promise.all([get('up'), get('down')]) : [await get(direction)];
      return mergeGraphs(...parts);
    },
    [client, id, direction, depth],
  );

  const go = (e: FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const data = new FormData(form);
    navigate(`/lineage/${String(data.get('node')).trim()}`, {
      direction: String(data.get('direction')),
      depth: String(data.get('depth') ?? ''),
    });
  };

  return (
    <Page title="Lineage explorer">
      <form className="inline-form card" onSubmit={go}>
        <label htmlFor="lineage-node">Provenance node ID</label>
        <input
          id="lineage-node"
          name="node"
          value={nodeInput}
          onChange={(e) => setNodeInput(e.target.value)}
          required
          pattern="[0-9a-fA-F-]{36}"
        />
        <label htmlFor="lineage-direction">Direction</label>
        <select id="lineage-direction" name="direction" defaultValue={direction} key={direction}>
          <option value="both">Both (ancestry and descendants)</option>
          <option value="up">Up (where it came from)</option>
          <option value="down">Down (what was made from it)</option>
        </select>
        <label htmlFor="lineage-depth">Max hops</label>
        <input
          id="lineage-depth"
          name="depth"
          type="number"
          min={0}
          max={1000}
          defaultValue={depth ?? ''}
          key={`d${depth}`}
        />
        <button className="btn" type="submit">
          Explore
        </button>
      </form>
      {!id ? <p className="muted">Enter a node ID, or open the lineage from a run.</p> : null}
      {id && graph.loading ? <Loading what="lineage" /> : null}
      {graph.error ? <ErrorBox error={graph.error} /> : null}
      {graph.data ? (
        <>
          <p className="flow" data-testid="flow">
            Flow: {flowTypes(graph.data).join(' → ')}
          </p>
          {graph.data.truncated ? (
            <p className="alert" role="alert">
              The graph was truncated by the server's node cap; narrow it with Max hops.
            </p>
          ) : null}
          <LineageView
            key={graph.data.root + direction}
            graph={graph.data}
            onReroot={(n) => {
              setNodeInput(n.id);
              navigate(`/lineage/${n.id}`, { direction, depth });
            }}
          />
        </>
      ) : null}
    </Page>
  );
}
