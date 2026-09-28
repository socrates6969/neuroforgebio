import { useMemo, useRef, useState, type KeyboardEvent } from 'react';
import type { ProvNode } from '../api/types';
import { layout, nodeLabel, orderedNodes, rankNodes, type Graph } from '../lineage/graph';

const NODE_W = 140;
const NODE_H = 36;

/**
 * Keyboard-navigable node list (the primary, accessible view) plus a simple SVG graph.
 * List keys: Up/Down (or Left/Right) move, Home/End jump, Enter re-roots the explorer on the node.
 */
export function LineageView({
  graph,
  onReroot,
}: {
  graph: Graph;
  onReroot: (node: ProvNode) => void;
}) {
  const rank = useMemo(() => rankNodes(graph), [graph]);
  const nodes = useMemo(() => orderedNodes(graph, rank), [graph, rank]);
  const { placed, width, height } = useMemo(() => layout(graph), [graph]);
  const [active, setActive] = useState(() =>
    Math.max(
      0,
      nodes.findIndex((n) => n.id === graph.root),
    ),
  );
  const listRef = useRef<HTMLUListElement>(null);
  const current = nodes[Math.min(active, nodes.length - 1)];

  const onKey = (e: KeyboardEvent<HTMLUListElement>) => {
    const last = nodes.length - 1;
    let next = active;
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') next = Math.min(last, active + 1);
    else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') next = Math.max(0, active - 1);
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = last;
    else if (e.key === 'Enter' && current) {
      e.preventDefault();
      onReroot(current);
      return;
    } else return;
    e.preventDefault();
    setActive(next);
  };

  const optionId = (n: ProvNode) => `lineage-node-${n.id}`;

  return (
    <div className="lineage">
      <div className="lineage-list">
        <h3 id="lineage-list-label">Nodes ({nodes.length})</h3>
        <p className="muted small">
          Arrow keys move, Enter re-roots on the selected node. Ordered along the data flow.
        </p>
        <ul
          ref={listRef}
          role="listbox"
          tabIndex={0}
          aria-labelledby="lineage-list-label"
          aria-activedescendant={current ? optionId(current) : undefined}
          onKeyDown={onKey}
          className="listbox"
        >
          {nodes.map((n, i) => (
            <li
              key={n.id}
              id={optionId(n)}
              role="option"
              aria-selected={i === active}
              data-type={n.type}
              data-rank={rank.get(n.id)}
              className={`option kind-${n.kind}${n.id === graph.root ? ' is-root' : ''}`}
              onClick={() => setActive(i)}
              onDoubleClick={() => onReroot(n)}
            >
              <span className="rank">{rank.get(n.id)}</span>
              <span className="kind">{n.kind}</span> {nodeLabel(n)}
              {n.id === graph.root ? <span className="badge">root</span> : null}
            </li>
          ))}
        </ul>
      </div>

      <div className="lineage-graph">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Lineage graph with ${nodes.length} nodes and ${graph.edges.length} edges; the list shows the same nodes`}
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className="edge-head" />
            </marker>
          </defs>
          {graph.edges.map((e) => {
            // draw along the data flow: source (dst of the PROV edge) -> derived (src)
            const from = placed.get(e.dst);
            const to = placed.get(e.src);
            if (!from || !to) return null;
            return (
              <line
                key={`${e.src}|${e.rel}|${e.dst}`}
                className={`edge rel-${e.rel}`}
                x1={from.x + NODE_W}
                y1={from.y + NODE_H / 2}
                x2={to.x}
                y2={to.y + NODE_H / 2}
                markerEnd="url(#arrow)"
              >
                <title>{e.rel}</title>
              </line>
            );
          })}
          {[...placed.values()].map((p) => (
            <g
              key={p.node.id}
              className={`gnode kind-${p.node.kind}${current?.id === p.node.id ? ' is-active' : ''}${p.node.id === graph.root ? ' is-root' : ''}`}
              transform={`translate(${p.x},${p.y})`}
              onClick={() => setActive(nodes.findIndex((n) => n.id === p.node.id))}
            >
              <rect width={NODE_W} height={NODE_H} rx={p.node.kind === 'activity' ? 2 : 14} />
              <text x={8} y={22}>
                {nodeLabel(p.node).slice(0, 20)}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {current ? (
        <section className="card lineage-detail" aria-live="polite">
          <h3>{nodeLabel(current)}</h3>
          <dl className="kv">
            <dt>Node ID</dt>
            <dd className="mono">{current.id}</dd>
            <dt>Kind / type</dt>
            <dd>
              {current.kind} / {current.type}
            </dd>
            <dt>Reference</dt>
            <dd className="mono">{current.ref_id ?? '–'}</dd>
            <dt>Content hash</dt>
            <dd className="mono">{current.content_hash ?? '–'}</dd>
            <dt>Node hash</dt>
            <dd className="mono">{current.node_hash}</dd>
            <dt>Recorded</dt>
            <dd>{current.created_at}</dd>
          </dl>
          <button type="button" className="btn" onClick={() => onReroot(current)}>
            Explore from this node
          </button>
        </section>
      ) : null}
    </div>
  );
}
