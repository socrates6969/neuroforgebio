import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { LineageGraph, ProvNode } from '../api/types';
import { LineageView } from '../components/LineageView';
import { LineagePage } from '../pages/Lineage';
import { renderWithApi, uuid } from '../test/helpers';
import { flowTypes, layout, mergeGraphs, orderedNodes, rankNodes } from './graph';

const node = (
  i: number,
  kind: ProvNode['kind'],
  type: string,
  extra: Partial<ProvNode> = {},
): ProvNode => ({
  id: uuid(i),
  kind,
  type,
  ref_id: `ref-${i}`,
  content_hash: null,
  node_hash: `h${i}`,
  attrs: {},
  batch_seq: 1,
  created_at: '2026-09-26T10:00:00Z',
  ...extra,
});

// raw_file(1) <-used- convert(2) <-wasGeneratedBy- recording(3) <-used- run(4) <-wasGeneratedBy- artifact(5)
const RAW = node(1, 'entity', 'raw_file');
const CONVERT = node(2, 'activity', 'convert');
const REC = node(3, 'entity', 'recording');
const RUN = node(4, 'activity', 'run');
const ART = node(5, 'entity', 'artifact', { attrs: { name: 'bandpower.npz' } });
const PV = node(6, 'agent', 'pipeline_version');
const SW = node(7, 'agent', 'software');

const up: LineageGraph = {
  root: RUN.id,
  direction: 'up',
  depth: null,
  truncated: false,
  nodes: [RUN, REC, CONVERT, RAW, PV, SW].map((n, d) => ({ ...n, depth: d })),
  edges: [
    { src: RUN.id, rel: 'used', dst: REC.id },
    { src: RUN.id, rel: 'wasAssociatedWith', dst: PV.id },
    { src: REC.id, rel: 'wasGeneratedBy', dst: CONVERT.id },
    { src: REC.id, rel: 'wasDerivedFrom', dst: RAW.id },
    { src: CONVERT.id, rel: 'used', dst: RAW.id },
    { src: CONVERT.id, rel: 'wasAssociatedWith', dst: SW.id },
  ],
};
const down: LineageGraph = {
  root: RUN.id,
  direction: 'down',
  depth: null,
  truncated: false,
  nodes: [RUN, ART],
  edges: [
    { src: ART.id, rel: 'wasGeneratedBy', dst: RUN.id },
    { src: ART.id, rel: 'wasDerivedFrom', dst: REC.id }, // REC not in the down graph: dropped by merge only if absent
  ],
};

describe('lineage graph helpers', () => {
  it('merges up + down and ranks along the data flow: raw -> recording -> run -> artifact', () => {
    const g = mergeGraphs(up, down);
    expect(g.nodes).toHaveLength(7);
    expect(g.edges).toHaveLength(8);
    const r = rankNodes(g);
    expect([RAW, CONVERT, REC, RUN, ART].map((n) => r.get(n.id))).toEqual([0, 1, 2, 3, 4]);
    expect(r.get(PV.id)).toBe(0);
    const flow = flowTypes(g).filter((t) =>
      ['raw_file', 'recording', 'run', 'artifact'].includes(t),
    );
    expect(flow).toEqual(['raw_file', 'recording', 'run', 'artifact']);
    expect(
      orderedNodes(g)
        .map((n) => n.type)
        .slice(-1),
    ).toEqual(['artifact']);
    const { placed, width } = layout(g);
    expect(placed.get(ART.id)!.x).toBeGreaterThan(placed.get(RUN.id)!.x);
    expect(width).toBeGreaterThan(0);
  });

  it('survives a cycle (not valid PROV, but never loops)', () => {
    const g = mergeGraphs({
      ...up,
      nodes: [RAW, REC],
      edges: [
        { src: RAW.id, rel: 'wasDerivedFrom', dst: REC.id },
        { src: REC.id, rel: 'wasDerivedFrom', dst: RAW.id },
      ],
    });
    expect(rankNodes(g).size).toBe(2);
  });
});

describe('LineageView (keyboard-navigable list + SVG)', () => {
  it('moves with arrow keys, jumps with Home/End, re-roots with Enter', () => {
    const onReroot = vi.fn();
    render(<LineageView graph={mergeGraphs(up, down)} onReroot={onReroot} />);
    const list = screen.getByRole('listbox', { name: /Nodes/ });
    const active = () => document.getElementById(list.getAttribute('aria-activedescendant')!)!;
    expect(active().textContent).toContain('run');
    fireEvent.keyDown(list, { key: 'End' });
    expect(active().getAttribute('data-type')).toBe('artifact');
    fireEvent.keyDown(list, { key: 'Home' });
    expect(active().getAttribute('data-rank')).toBe('0');
    fireEvent.keyDown(list, { key: 'ArrowDown' });
    fireEvent.keyDown(list, { key: 'Enter' });
    expect(onReroot).toHaveBeenCalledTimes(1);
    expect(within(list).getAllByRole('option')).toHaveLength(7);
    expect(screen.getByRole('img', { name: /Lineage graph with 7 nodes/ })).toBeTruthy();
  });
});

describe('LineagePage', () => {
  it('fetches both directions and shows the flow', async () => {
    const r = renderWithApi(
      <LineagePage id={RUN.id} query={new URLSearchParams('direction=both')} />,
      {
        routes: {
          [`GET /v1/provenance/${RUN.id}/lineage`]: ({ url }) =>
            url.searchParams.get('direction') === 'up' ? up : down,
        },
      },
    );
    const flow = await screen.findByTestId('flow');
    expect(flow.textContent).toMatch(/raw_file.*recording.*run.*artifact/);
    const dirs = r.api.calls
      .filter((c) => c.path.includes('/lineage'))
      .map((c) => new URL(c.path, 'http://x').searchParams.get('direction'));
    expect(dirs.sort()).toEqual(['down', 'up']);
  });
});
