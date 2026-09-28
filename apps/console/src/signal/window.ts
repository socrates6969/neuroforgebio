// Window reads for the recording viewer: pick a pyramid level, fetch, convert to physical units.
// Pyramid (nf_platform/signals/zarr_store.py): level k is decimated by 4^k (PYRAMID_FACTOR = 4) and
// stores block mean/min/max; level 0 is the raw samples. JSON window reads are capped at
// window_json_max_values (250 000 values = samples x channels) by default.
import { ApiError, type ApiClient } from '../api/client';
import type { SignalWindow } from '../api/types';

export const PYRAMID_FACTOR = 4;
export const MAX_LEVEL = 11; // the route's own bound (le=11)
export const JSON_MAX_VALUES = 250_000;

/**
 * Coarsest detail still worth drawing: about two samples per pixel column, and never more than the
 * JSON cap. Returns the smallest level satisfying both.
 */
export function chooseLevel(
  sfreq: number,
  spanS: number,
  nChannels: number,
  widthPx: number,
  maxValues = JSON_MAX_VALUES,
): number {
  const samples0 = Math.max(1, Math.ceil(spanS * sfreq));
  const target = Math.max(2 * Math.max(1, widthPx), 1);
  let level = 0;
  let n = samples0;
  while (level < MAX_LEVEL && (n > target || n * nChannels > maxValues)) {
    level += 1;
    n = Math.ceil(n / PYRAMID_FACTOR);
  }
  return level;
}

/** "level must be in 0..N" (422 from the server when the recording has fewer levels) -> N. */
export function maxLevelFromProblem(e: unknown): number | null {
  if (!(e instanceof ApiError) || e.status !== 422) return null;
  const m = /level must be in 0\.\.(\d+)/.exec(e.problem.detail ?? '');
  return m ? Number(m[1]) : null;
}

export interface Trace {
  channel: string;
  unit: string;
  /** time of sample i: t0 + i / sfreq */
  t0: number;
  sfreq: number;
  mean: Float64Array;
  min?: Float64Array;
  max?: Float64Array;
}

export function toPhysical(w: SignalWindow): Float64Array[] {
  return w.data.map((row, c) => {
    const s = w.scale[c] ?? 1;
    const o = w.offset[c] ?? 0;
    const out = new Float64Array(row.length);
    for (let i = 0; i < row.length; i++) out[i] = row[i] * s + o;
    return out;
  });
}

export interface WindowRequest {
  recordingId: string;
  start: number;
  end: number;
  channels?: string;
  level: number;
}

async function read(
  client: ApiClient,
  r: WindowRequest,
  kind: 'mean' | 'min' | 'max',
  signal?: AbortSignal,
): Promise<SignalWindow> {
  return (await client.call('readRecordingData', {
    path: { recording_id: r.recordingId },
    query: {
      start: r.start,
      end: r.end,
      channels: r.channels || undefined,
      level: r.level,
      kind,
      format: 'json',
    },
    signal,
  })) as SignalWindow;
}

/**
 * Fetch mean (+ min/max envelope above level 0). If the recording has fewer pyramid levels than
 * requested, retry once at the server's maximum.
 */
export async function fetchTraces(
  client: ApiClient,
  req: WindowRequest,
  signal?: AbortSignal,
): Promise<{ level: number; traces: Trace[]; truncated: boolean }> {
  let level = req.level;
  let mean: SignalWindow;
  try {
    mean = await read(client, { ...req, level }, 'mean', signal);
  } catch (e) {
    const max = maxLevelFromProblem(e);
    if (max === null || max >= level) throw e;
    level = max;
    mean = await read(client, { ...req, level }, 'mean', signal);
  }
  let min: SignalWindow | undefined;
  let max: SignalWindow | undefined;
  if (level > 0) {
    [min, max] = await Promise.all([
      read(client, { ...req, level }, 'min', signal),
      read(client, { ...req, level }, 'max', signal),
    ]);
  }
  const m = toPhysical(mean);
  const lo = min ? toPhysical(min) : undefined;
  const hi = max ? toPhysical(max) : undefined;
  const traces = mean.channels.map((ch, c) => ({
    channel: ch,
    unit: mean.units[c] ?? '',
    t0: mean.start_s,
    sfreq: mean.sfreq,
    mean: m[c],
    min: lo?.[c],
    max: hi?.[c],
  }));
  const expected = Math.ceil((req.end - req.start) * mean.sfreq) - 1;
  return { level, traces, truncated: (m[0]?.length ?? 0) < expected };
}
