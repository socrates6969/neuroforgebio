import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ApiKeyOut } from '../api/generated';
import { parseHash } from '../router';
import { jsonResponse, renderWithApi, uuid } from '../test/helpers';
import { ApiKeysPage, keyStatus } from './ApiKeys';

const SECRET = 'nfb_live_abcdefghijklmnop_' + 'x'.repeat(43);

function key(n: number, over: Partial<ApiKeyOut> = {}): ApiKeyOut {
  return {
    id: uuid(n),
    public_id: `pubid${n}`.padEnd(16, 'a'),
    name: `key-${n}`,
    owner_id: 'u1',
    roles: ['viewer'],
    scopes: ['metadata:read'],
    created_at: '2026-09-26T10:00:00Z',
    expires_at: '2099-01-01T00:00:00Z',
    revoked_at: null,
    ...over,
  };
}

afterEach(() => vi.restoreAllMocks());

describe('API keys page (4.8)', () => {
  it('routes #/api-keys', () => {
    expect(parseHash('#/api-keys').name).toBe('api-keys');
  });

  it('computes the key status', () => {
    expect(keyStatus(key(1))).toBe('active');
    expect(keyStatus(key(1, { revoked_at: '2026-09-26T11:00:00Z' }))).toBe('revoked');
    expect(keyStatus(key(1, { expires_at: '2000-01-01T00:00:00Z' }))).toBe('expired');
  });

  it('creates a key and shows the secret exactly once', async () => {
    const keys: ApiKeyOut[] = [];
    let posted: unknown = null;
    const { api } = renderWithApi(<ApiKeysPage />, {
      roles: ['scientist'],
      routes: {
        'GET /v1/api-keys': () => keys,
        'POST /v1/api-keys': ({ body }) => {
          posted = body;
          const k = key(7, { name: 'ci' });
          keys.push(k);
          return jsonResponse({ ...k, key: SECRET }, 201);
        },
      },
    });
    await screen.findByText('No API keys yet.');
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'ci' } });
    fireEvent.click(screen.getByLabelText('data:read'));
    fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
    const box = (await screen.findByLabelText('API key for ci')) as HTMLInputElement;
    expect(box.value).toBe(SECRET);
    expect(posted).toEqual({
      name: 'ci',
      roles: ['viewer'],
      scopes: ['metadata:read', 'data:read'],
      expires_in_days: 90,
    });
    // the list shows the new key without its secret
    await screen.findByText('ci');
    expect(document.body.textContent).not.toContain(SECRET.slice(-20));
    fireEvent.click(screen.getByRole('button', { name: 'I have stored the key' }));
    expect(screen.queryByLabelText('API key for ci')).toBeNull();
    expect(document.body.innerHTML).not.toContain(SECRET);
    // nothing was persisted in the browser
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(api.calls.filter((c) => c.method === 'POST')).toHaveLength(1);
  });

  it('revokes an active key after confirmation', async () => {
    const keys = [key(1), key(2, { revoked_at: '2026-09-26T11:00:00Z' })];
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { api } = renderWithApi(<ApiKeysPage />, {
      roles: ['viewer'],
      routes: {
        'GET /v1/api-keys': () => keys,
        [`DELETE /v1/api-keys/${uuid(1)}`]: () => {
          keys[0] = { ...keys[0], revoked_at: '2026-09-26T12:00:00Z' };
          return new Response(null, { status: 204 });
        },
      },
    });
    await screen.findByText('key-1');
    // only the active key has a revoke button
    expect(screen.getAllByRole('button', { name: /^Revoke / })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Revoke key-1' }));
    await waitFor(() =>
      expect(api.calls.some((c) => c.method === 'DELETE' && c.path.endsWith(uuid(1)))).toBe(true),
    );
    await waitFor(() =>
      expect(screen.queryAllByRole('button', { name: /^Revoke / })).toHaveLength(0),
    );
  });

  it('does not revoke when the confirmation is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { api } = renderWithApi(<ApiKeysPage />, {
      roles: ['viewer'],
      routes: { 'GET /v1/api-keys': () => [key(1)] },
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Revoke key-1' }));
    expect(api.calls.some((c) => c.method === 'DELETE')).toBe(false);
  });

  it('hides create and revoke from roles that cannot use them (the server still decides)', async () => {
    renderWithApi(<ApiKeysPage />, {
      roles: ['auditor'],
      routes: { 'GET /v1/api-keys': () => [key(1)] },
    });
    await screen.findByText('key-1');
    expect(screen.queryByRole('button', { name: 'Create key' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Revoke / })).toBeNull();
  });

  it('shows a problem+json error from the server', async () => {
    renderWithApi(<ApiKeysPage />, {
      roles: ['scientist'],
      routes: {
        'GET /v1/api-keys': () => [],
        'POST /v1/api-keys': () =>
          jsonResponse(
            {
              title: 'Forbidden',
              status: 403,
              detail: 'cannot delegate these roles to an API key',
            },
            403,
            'application/problem+json',
          ),
      },
    });
    await screen.findByText('No API keys yet.');
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'x' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
    await screen.findByText(/cannot delegate these roles/);
  });
});
