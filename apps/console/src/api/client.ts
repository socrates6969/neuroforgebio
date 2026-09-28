// Typed fetch wrapper over the generated operation table (src/api/generated.ts).
// - Bearer token from the in-memory OIDC session; credentials: 'omit' (the console sends no cookies).
// - RFC 9457 problem+json errors become ApiError.
// - The server authorizes every call; the UI's role checks (src/authz) only hide controls.

import { OPERATIONS, type OperationName, type Operations } from './generated';

export interface Problem {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  request_id?: string;
  [k: string]: unknown;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly problem: Problem,
  ) {
    super(problem.detail || problem.title || `HTTP ${status}`);
  }
}

type Args<K extends OperationName> = ([Operations[K]['path']] extends [never]
  ? { path?: undefined }
  : { path: Operations[K]['path'] }) &
  ([Operations[K]['query']] extends [never]
    ? { query?: undefined }
    : { query?: Operations[K]['query'] }) &
  ([Operations[K]['body']] extends [never]
    ? { body?: undefined }
    : { body: Operations[K]['body'] }) & {
    signal?: AbortSignal;
  };

export interface ClientOptions {
  baseUrl: string;
  token: () => Promise<string>;
  fetch?: typeof fetch;
  /** called on 401 (session gone at the server) */
  onUnauthorized?: () => void;
}

export function buildPath(template: string, params: Record<string, unknown> | undefined): string {
  return template.replace(/\{([^}]+)\}/g, (_, name: string) => {
    const v = params?.[name];
    if (v === undefined || v === null || v === '')
      throw new Error(`missing path parameter ${name}`);
    return encodeURIComponent(String(v));
  });
}

export function buildQuery(query: Record<string, unknown> | undefined): string {
  if (!query) return '';
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(query))
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : '';
}

export class ApiClient {
  private readonly f: typeof fetch;

  constructor(private readonly opts: ClientOptions) {
    this.f = opts.fetch ?? globalThis.fetch.bind(globalThis);
  }

  /** Absolute URL of an API path (same origin when baseUrl is ""). */
  url(path: string): string {
    return `${this.opts.baseUrl}${path}`;
  }

  /** True when `url` points at the platform API (a bearer token may be sent there). */
  isApiUrl(url: string, origin: string): boolean {
    const api = new URL(this.opts.baseUrl || '/', origin);
    const u = new URL(url, api);
    return u.origin === api.origin && u.pathname.startsWith('/v1/');
  }

  async call<K extends OperationName>(name: K, args: Args<K>): Promise<Operations[K]['response']> {
    const op = OPERATIONS[name];
    const a = args as { path?: Record<string, unknown>; query?: Record<string, unknown> };
    const url = this.url(buildPath(op.path, a.path) + buildQuery(a.query));
    const headers: Record<string, string> = {
      Authorization: `Bearer ${await this.opts.token()}`,
      Accept: 'application/json, application/problem+json',
    };
    let body: BodyInit | undefined;
    const b = (args as { body?: unknown }).body;
    if (op.body === 'json') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(b);
    } else if (op.body === 'binary') {
      headers['Content-Type'] = 'application/octet-stream';
      body = b as Blob;
    }
    const r = await this.f(url, {
      method: op.method,
      headers,
      body,
      credentials: 'omit',
      cache: 'no-store',
      signal: args.signal,
    });
    return (await this.parse(r)) as Operations[K]['response'];
  }

  /** GET a JSON path that is not in the generated table yet (e.g. the sweeps fixture routes). */
  async getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
    if (!path.startsWith('/v1/')) throw new Error('API paths start with /v1/');
    const r = await this.f(this.url(path), {
      headers: {
        Authorization: `Bearer ${await this.opts.token()}`,
        Accept: 'application/json, application/problem+json',
      },
      credentials: 'omit',
      cache: 'no-store',
      signal,
    });
    return (await this.parse(r)) as T;
  }

  /** POST JSON to an API path that is not in the generated table yet. */
  async postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
    if (!path.startsWith('/v1/')) throw new Error('API paths start with /v1/');
    const r = await this.f(this.url(path), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${await this.opts.token()}`,
        Accept: 'application/json, application/problem+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      credentials: 'omit',
      cache: 'no-store',
      signal,
    });
    return (await this.parse(r)) as T;
  }

  /** PUT raw bytes to an upload part target (bearer only for the API's own URLs). */
  async putPart(
    target: { url: string; method: string; auth: string },
    data: Blob,
    origin: string,
    signal?: AbortSignal,
  ): Promise<unknown> {
    const headers: Record<string, string> = { 'Content-Type': 'application/octet-stream' };
    if (target.auth === 'bearer') {
      // Never hand the platform credential to a URL outside the API (e.g. a compromised response).
      if (!this.isApiUrl(target.url, origin)) throw new Error('refusing to send a token off-API');
      headers.Authorization = `Bearer ${await this.opts.token()}`;
    }
    const r = await this.f(
      new URL(target.url, new URL(this.opts.baseUrl || '/', origin)).toString(),
      {
        method: target.method,
        headers,
        body: data,
        credentials: 'omit',
        cache: 'no-store',
        signal,
      },
    );
    return this.parse(r);
  }

  private async parse(r: Response): Promise<unknown> {
    const ct = r.headers.get('content-type') || '';
    if (!r.ok) {
      let problem: Problem = { status: r.status, title: r.statusText };
      if (ct.includes('json')) {
        try {
          problem = { ...problem, ...((await r.json()) as Problem) };
        } catch {
          // keep the status-only problem
        }
      }
      if (r.status === 401) this.opts.onUnauthorized?.();
      throw new ApiError(r.status, problem);
    }
    if (r.status === 204) return undefined;
    if (ct.includes('json')) return r.json();
    return r.arrayBuffer();
  }
}
