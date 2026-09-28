import { describe, expect, it, vi } from 'vitest';
import { fakeApi, jsonResponse } from '../test/helpers';
import { ApiClient, ApiError, buildPath, buildQuery } from './client';
import { OPERATIONS } from './generated';

describe('generated operation table', () => {
  it('covers the console routes with their authz actions', () => {
    expect(OPERATIONS.listProjects).toMatchObject({
      method: 'GET',
      path: '/v1/projects',
      action: 'project:read',
    });
    expect(OPERATIONS.getLineage).toMatchObject({
      path: '/v1/provenance/{node_id}/lineage',
      action: 'provenance:read',
    });
    expect(OPERATIONS.readRecordingData.action).toBe('signal:read');
    expect(OPERATIONS.createRun).toMatchObject({ method: 'POST', status: 202, body: 'json' });
    expect(OPERATIONS.putUploadPart.body).toBe('binary');
    // every route but health declares an action (the server denies routes without one)
    for (const [name, op] of Object.entries(OPERATIONS))
      if (name !== 'health') expect(op.action, name).toMatch(/^[a-z-]+:[a-z]+(-[a-z]+)*$/);
  });
});

describe('ApiClient', () => {
  it('encodes path and query parameters', () => {
    expect(buildPath('/v1/runs/{run_id}', { run_id: 'a/b c' })).toBe('/v1/runs/a%2Fb%20c');
    expect(() => buildPath('/v1/runs/{run_id}', {})).toThrow(/run_id/);
    expect(buildQuery({ a: 1, b: undefined, c: '', d: 'x y' })).toBe('?a=1&d=x+y');
  });

  it('sends the bearer token, no cookies, no cache', async () => {
    const f = vi.fn(async (_u: string, _i?: RequestInit) => jsonResponse([]));
    const c = new ApiClient({
      baseUrl: 'https://api.example.test',
      token: async () => 'tok',
      fetch: f as unknown as typeof fetch,
    });
    await c.call('listProjects', { query: { limit: 5 } });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.example.test/v1/projects?limit=5');
    expect(init.credentials).toBe('omit');
    expect(init.cache).toBe('no-store');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('turns problem+json into ApiError and reports 401', async () => {
    const onUnauthorized = vi.fn();
    const api = fakeApi({
      'GET /v1/runs/00000000-0000-4000-8000-000000000001': () =>
        jsonResponse(
          {
            title: 'Forbidden',
            status: 403,
            detail: 'role does not permit this action',
            request_id: 'r1',
          },
          403,
          'application/problem+json',
        ),
      'GET /v1/whoami': () =>
        jsonResponse({ title: 'Unauthorized', status: 401 }, 401, 'application/problem+json'),
    });
    const c = new ApiClient({
      baseUrl: '',
      token: async () => 't',
      fetch: api.fetch,
      onUnauthorized,
    });
    const e = await c
      .call('getRun', { path: { run_id: '00000000-0000-4000-8000-000000000001' } })
      .catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect((e as ApiError).status).toBe(403);
    expect((e as ApiError).problem.request_id).toBe('r1');
    await expect(c.call('whoami', {})).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('never sends the platform token to a URL outside the API', async () => {
    const f = vi.fn(async (_u: string, _i?: RequestInit) => jsonResponse({}));
    const c = new ApiClient({
      baseUrl: '',
      token: async () => 'tok',
      fetch: f as unknown as typeof fetch,
    });
    const origin = 'https://console.example.test';
    await expect(
      c.putPart(
        { url: 'https://evil.example/x', method: 'PUT', auth: 'bearer' },
        new Blob(['x']),
        origin,
      ),
    ).rejects.toThrow(/off-API/);
    await expect(
      c.putPart({ url: '/not-api/x', method: 'PUT', auth: 'bearer' }, new Blob(['x']), origin),
    ).rejects.toThrow(/off-API/);
    expect(f).not.toHaveBeenCalled();
    // pre-signed (auth "none"): sent WITHOUT the token
    await c.putPart(
      { url: 'https://bucket.example/p?sig=1', method: 'PUT', auth: 'none' },
      new Blob(['x']),
      origin,
    );
    const init = f.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
    // the API's own part URL: token sent
    await c.putPart(
      { url: '/v1/uploads/u/parts/1', method: 'PUT', auth: 'bearer' },
      new Blob(['x']),
      origin,
    );
    expect((f.mock.calls[1]![1] as RequestInit).headers).toMatchObject({
      Authorization: 'Bearer tok',
    });
  });
});
