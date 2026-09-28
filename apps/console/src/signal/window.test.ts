import { describe, expect, it } from 'vitest';
import { ApiClient, ApiError } from '../api/client';
import type { SignalWindow } from '../api/types';
import { fakeApi, jsonResponse } from '../test/helpers';
import { chooseLevel, fetchTraces, maxLevelFromProblem, toPhysical } from './window';

const win = (over: Partial<SignalWindow>): SignalWindow => ({
  byte_order: 'little',
  channels: ['Fz', 'Cz'],
  chunk_id: 'c',
  decimation: 1,
  dtype: 'int16',
  kind: 'samples',
  level: 0,
  offset: [0, 1],
  order: 'C',
  physical: 'stored * scale + offset',
  scale: [0.5, 2],
  sfreq: 256,
  shape: [2, 3],
  start_index: 0,
  start_s: 0,
  units: ['uV', 'uV'],
  data: [
    [2, 4, 6],
    [1, 2, 3],
  ],
  ...over,
});

describe('pyramid level choice', () => {
  it('uses raw samples when they fit, coarser levels for long windows', () => {
    expect(chooseLevel(256, 2, 8, 1000)).toBe(0); // 512 samples <= 2000 px budget
    expect(chooseLevel(256, 60, 8, 1000)).toBe(2); // 15360 -> 3840 -> 960
    expect(chooseLevel(30000, 10, 1024, 1000)).toBeGreaterThan(5);
  });

  it('respects the JSON value cap (samples x channels)', () => {
    const lvl = chooseLevel(1000, 1, 1024, 1000);
    const values = Math.ceil(1000 / 4 ** lvl) * 1024;
    expect(values).toBeLessThanOrEqual(250_000);
  });
});

describe('window conversion', () => {
  it('applies scale and offset per channel', () => {
    const [a, b] = toPhysical(win({}));
    expect([...a]).toEqual([1, 2, 3]);
    expect([...b]).toEqual([3, 5, 7]);
  });

  it('parses the server level limit', () => {
    expect(maxLevelFromProblem(new ApiError(422, { detail: 'level must be in 0..2' }))).toBe(2);
    expect(maxLevelFromProblem(new ApiError(403, { detail: 'level must be in 0..2' }))).toBeNull();
  });

  it('retries at the maximum level and fetches the min/max envelope', async () => {
    const seen: string[] = [];
    const api = fakeApi({
      'GET /v1/recordings/r1/data': ({ url }) => {
        const lvl = Number(url.searchParams.get('level'));
        const kind = url.searchParams.get('kind')!;
        seen.push(`${lvl}:${kind}`);
        if (lvl > 2)
          return jsonResponse(
            { title: 'Invalid request', status: 422, detail: 'level must be in 0..2' },
            422,
            'application/problem+json',
          );
        return win({ level: lvl, kind: kind as SignalWindow['kind'], sfreq: 16, decimation: 16 });
      },
    });
    const c = new ApiClient({ baseUrl: '', token: async () => 't', fetch: api.fetch });
    const out = await fetchTraces(c, { recordingId: 'r1', start: 0, end: 10, level: 5 });
    expect(out.level).toBe(2);
    expect(seen).toEqual(['5:mean', '2:mean', '2:min', '2:max']);
    expect(out.traces[0]!.min).toBeDefined();
    expect(out.traces.map((t) => t.channel)).toEqual(['Fz', 'Cz']);
  });
});
