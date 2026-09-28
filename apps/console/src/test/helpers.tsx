import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { ApiClient } from '../api/client';
import type { OidcSession, SessionState } from '../auth/oidc';
import { SessionProvider } from '../auth/session';

export type Handler = (req: { method: string; url: URL; body: unknown }) => unknown;

export interface FakeApi {
  fetch: typeof fetch;
  calls: Array<{ method: string; path: string; headers: Record<string, string> }>;
}

export function jsonResponse(body: unknown, status = 200, type = 'application/json'): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': type } });
}

/**
 * fetch stub: routes "METHOD /path" (path without query) to handlers. A handler may return a
 * Response, or a value that becomes a 200 JSON body. Unknown routes -> 404 problem+json.
 */
export function fakeApi(routes: Record<string, Handler>): FakeApi {
  const calls: FakeApi['calls'] = [];
  const f = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://console.test');
    const method = (init?.method ?? 'GET').toUpperCase();
    const headers = (init?.headers ?? {}) as Record<string, string>;
    calls.push({ method, path: url.pathname + url.search, headers });
    const key = `${method} ${url.pathname}`;
    const h = routes[key];
    if (!h)
      return jsonResponse({ title: 'Not Found', status: 404 }, 404, 'application/problem+json');
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : init?.body;
    const out = await h({ method, url, body });
    return out instanceof Response ? out : jsonResponse(out);
  }) as typeof fetch;
  return { fetch: f, calls };
}

/** Minimal stand-in for OidcSession (signed in); the real class is tested in oidc.test.ts. */
export function fakeSession(
  state: SessionState = { status: 'signed-in', subject: 'u1', loginAt: 0 },
) {
  let s = state;
  const listeners = new Set<(st: SessionState) => void>();
  const session = {
    getState: () => s,
    subscribe: (fn: (st: SessionState) => void) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    touch: () => {},
    check: () => s.status === 'signed-in',
    accessToken: async () => 'test-access-token',
    login: async () => {
      s = { status: 'signed-in', subject: 'u1', loginAt: 0 };
      for (const l of listeners) l(s);
    },
    logout: async () => {
      s = { status: 'signed-out', reason: 'logout' };
      for (const l of listeners) l(s);
    },
  };
  return session as unknown as OidcSession;
}

export function whoami(roles: string[]) {
  return {
    id: 'u1',
    tenant_id: '11111111-1111-4111-8111-111111111111',
    kind: 'user',
    roles,
    scopes: [],
    mfa_phishing_resistant: roles.some((r) =>
      ['owner', 'admin', 'data-steward', 'auditor'].includes(r),
    ),
    auth_method: 'oidc',
  };
}

export function renderWithApi(
  ui: ReactElement,
  {
    roles = ['scientist'],
    routes = {},
  }: { roles?: string[]; routes?: Record<string, Handler> } = {},
): RenderResult & { api: FakeApi } {
  const api = fakeApi({ 'GET /v1/whoami': () => whoami(roles), ...routes });
  const client = new ApiClient({
    baseUrl: '',
    token: async () => 'test-access-token',
    fetch: api.fetch,
  });
  const r = render(
    <SessionProvider session={fakeSession()} client={client}>
      {ui}
    </SessionProvider>,
  );
  return { ...r, api };
}

export const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
