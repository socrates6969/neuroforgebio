// Pure helpers for the lineage explorer: merge up/down graphs, rank nodes along the data flow,
// lay them out in columns.
//
// PROV edges point from the derived thing to its source (artifact -wasGeneratedBy-> run,
// run -used-> recording, recording -wasDerivedFrom-> raw_file). Data FLOWS the other way, so a node's
// rank is 1 + the highest rank among the nodes it points at; sources (raw files, agents) are rank 0.
// Typical chain: raw_file 0 -> convert 1 -> recording 2 -> run 3 -> artifact 4.
import type { LineageGraph, ProvEdge, ProvNode } from '../api/types';

export interface Graph {
  root: string;
  truncated: boolean;
  nodes: ProvNode[];
  edges: ProvEdge[];
}

export function mergeGraphs(...gs: LineageGraph[]): Graph {
  const nodes = new Map<string, ProvNode>();
  const edges = new Map<string, ProvEdge>();
  for (const g of gs) {
    for (const n of g.nodes) if (!nodes.has(n.id)) nodes.set(n.id, n);
    for (const e of g.edges) edges.set(`${e.src}|${e.rel}|${e.dst}`, e);
  }
  return {
    root: gs[0]?.root ?? '',
    truncated: gs.some((g) => g.truncated),
    nodes: [...nodes.values()],
    edges: [...edges.values()].filter((e) => nodes.has(e.src) && nodes.has(e.dst)),
  };
}

/** Longest-path rank along the data flow; cycles (not expected in PROV) are cut, not looped. */
export function rankNodes(g: Graph): Map<string, number> {
  const out = new Map<string, string[]>();
  for (const n of g.nodes) out.set(n.id, []);
  for (const e of g.edges) out.get(e.src)?.push(e.dst);
  const rank = new Map<string, number>();
  const visiting = new Set<string>();
  const visit = (id: string): number => {
    const known = rank.get(id);
    if (known !== undefined) return known;
    if (visiting.has(id)) return 0;
    visiting.add(id);
    let r = 0;
    for (const dst of out.get(id) ?? []) r = Math.max(r, visit(dst) + 1);
    visiting.delete(id);
    rank.set(id, r);
    return r;
  };
  for (const n of g.nodes) visit(n.id);
  return rank;
}

const KIND_ORDER = { entity: 0, activity: 1, agent: 2 } as const;

/** Nodes sorted for the list view: by rank, then kind, then type, then id (stable). */
export function orderedNodes(g: Graph, rank = rankNodes(g)): ProvNode[] {
  return [...g.nodes].sort(
    (a, b) =>
      (rank.get(a.id) ?? 0) - (rank.get(b.id) ?? 0) ||
      KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
      a.type.localeCompare(b.type) ||
      a.id.localeCompare(b.id),
  );
}

export interface Placed {
  node: ProvNode;
  rank: number;
  x: number;
  y: number;
}

export const COL_W = 170;
export const ROW_H = 64;
export const PAD = 24;

export function layout(g: Graph): { placed: Map<string, Placed>; width: number; height: number } {
  const rank = rankNodes(g);
  const cols = new Map<number, ProvNode[]>();
  for (const n of orderedNodes(g, rank)) {
    const r = rank.get(n.id) ?? 0;
    if (!cols.has(r)) cols.set(r, []);
    cols.get(r)!.push(n);
  }
  const placed = new Map<string, Placed>();
  let maxRows = 1;
  let maxRank = 0;
  for (const [r, list] of cols) {
    maxRows = Math.max(maxRows, list.length);
    maxRank = Math.max(maxRank, r);
    list.forEach((node, i) =>
      placed.set(node.id, { node, rank: r, x: PAD + r * COL_W, y: PAD + i * ROW_H }),
    );
  }
  return {
    placed,
    width: PAD * 2 + (maxRank + 1) * COL_W,
    height: PAD * 2 + maxRows * ROW_H,
  };
}

/** Short human label: "run 3f2a…", "artifact bandpower.npz". */
export function nodeLabel(n: ProvNode): string {
  const name = typeof n.attrs?.name === 'string' ? (n.attrs.name as string) : null;
  if (name) return `${n.type} ${name}`;
  if (n.ref_id) return `${n.type} ${n.ref_id.length > 12 ? `${n.ref_id.slice(0, 8)}…` : n.ref_id}`;
  return `${n.type} ${n.id.slice(0, 8)}…`;
}

/** The raw → recording → run → artifact chain present in the graph, in flow order. */
export function flowTypes(g: Graph): string[] {
  const rank = rankNodes(g);
  const seen = new Map<string, number>();
  for (const n of g.nodes) {
    const r = rank.get(n.id) ?? 0;
    if (!seen.has(n.type) || r < seen.get(n.type)!) seen.set(n.type, r);
  }
  return [...seen.entries()]
    .sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]))
    .map((e) => e[0]);
}
