import { describe, expect, it } from 'vitest';
import { ApiClient } from './api/client';
import { fakeApi } from './test/helpers';
import { sha256Hex, uploadFile, type UploadProgress } from './upload';

describe('uploadFile', () => {
  it('hashes, PUTs each missing part, completes with the SHA-256 and polls to done', async () => {
    const bytes = new Uint8Array(10).map((_, i) => i);
    const file = new File([bytes], 'synthetic.edf');
    const parts: Array<{ n: string; size: number }> = [];
    let polls = 0;
    const base = {
      id: 'u1',
      dataset_id: 'd1',
      session_id: 's1',
      filename: 'synthetic.edf',
      size_bytes: 10,
      part_size: 4,
      n_parts: 3,
      synthetic: true,
      server_sha256: null,
      error: null,
      recording_ids: [] as string[],
      created_at: '2026-09-26T10:00:00Z',
      completed_at: null,
    };
    const target = (n: number) => ({
      part_number: n,
      method: 'PUT',
      url: `/v1/uploads/u1/parts/${n}`,
      expires_at: null,
      auth: 'bearer',
    });
    let completedWith: unknown;
    const api = fakeApi({
      'POST /v1/datasets/d1/uploads': ({ body }) => {
        expect(body).toEqual({
          session_id: 's1',
          filename: 'synthetic.edf',
          size_bytes: 10,
          synthetic: true,
        });
        return {
          ...base,
          state: 'open',
          parts: [target(1), target(2), target(3)],
          received_parts: [{ part_number: 1, sha256: 'x', size_bytes: 4 }],
        };
      },
      'PUT /v1/uploads/u1/parts/2': ({ body }) => (
        parts.push({ n: '2', size: (body as Blob).size }),
        {}
      ),
      'PUT /v1/uploads/u1/parts/3': ({ body }) => (
        parts.push({ n: '3', size: (body as Blob).size }),
        {}
      ),
      'POST /v1/uploads/u1/complete': ({ body }) => {
        completedWith = body;
        return { ...base, state: 'uploaded', parts: [], received_parts: [] };
      },
      'GET /v1/uploads/u1': () => {
        polls += 1;
        return {
          ...base,
          state: polls < 2 ? 'processing' : 'done',
          parts: [],
          received_parts: [],
          recording_ids: ['r1'],
        };
      },
    });
    const c = new ApiClient({ baseUrl: '', token: async () => 't', fetch: api.fetch });
    const phases: string[] = [];
    const up = await uploadFile(
      c,
      { datasetId: 'd1', sessionId: 's1', file, synthetic: true, origin: 'http://console.test' },
      (p: UploadProgress) => phases.push(p.phase),
      { pollMs: 1 },
    );
    expect(parts).toEqual([
      { n: '2', size: 4 },
      { n: '3', size: 2 },
    ]);
    expect(completedWith).toEqual({ sha256: await sha256Hex(new Blob([bytes])) });
    expect(up.state).toBe('done');
    expect(up.recording_ids).toEqual(['r1']);
    expect(phases[0]).toBe('hashing');
    expect(phases.at(-1)).toBe('done');
  });

  it('sha256Hex matches a known vector', async () => {
    expect(await sha256Hex(new Blob(['abc']))).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    );
  });
});
