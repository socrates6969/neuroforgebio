import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiClient } from '../api/client';
import type { Whoami } from '../api/types';
import { OidcSession, type SessionState } from './oidc';

export interface SessionContextValue {
  session: OidcSession;
  client: ApiClient;
  state: SessionState;
  /** GET /v1/whoami once signed in (effective roles from the server) */
  me: Whoami | null;
  meError: string | null;
}

const Ctx = createContext<SessionContextValue | null>(null);

/** How often idle/absolute limits are checked (the limits themselves are in oidc.ts). */
export const CHECK_INTERVAL_MS = 15_000;

export function SessionProvider({
  session,
  client,
  children,
}: {
  session: OidcSession;
  client: ApiClient;
  children: ReactNode;
}) {
  const [state, setState] = useState<SessionState>(session.getState());
  const [me, setMe] = useState<Whoami | null>(null);
  const [meError, setMeError] = useState<string | null>(null);

  useEffect(() => session.subscribe(setState), [session]);

  // Activity resets the idle timer; the interval enforces idle (15 min) and absolute (12 h) limits.
  useEffect(() => {
    const touch = () => session.touch();
    const events = ['keydown', 'pointerdown', 'wheel'] as const;
    for (const e of events) window.addEventListener(e, touch, { passive: true });
    const id = window.setInterval(() => session.check(), CHECK_INTERVAL_MS);
    return () => {
      for (const e of events) window.removeEventListener(e, touch);
      window.clearInterval(id);
    };
  }, [session]);

  useEffect(() => {
    if (state.status !== 'signed-in') {
      setMe(null);
      setMeError(null);
      return;
    }
    let live = true;
    client
      .call('whoami', {})
      .then((w) => live && setMe(w as unknown as Whoami))
      .catch((e: Error) => live && setMeError(e.message));
    return () => {
      live = false;
    };
  }, [state, client]);

  const value = useMemo(
    () => ({ session, client, state, me, meError }),
    [session, client, state, me, meError],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error('useSession outside SessionProvider');
  return v;
}

/** Effective roles of the signed-in user ([] while loading or signed out). */
export function useRoles(): string[] {
  return useSession().me?.roles ?? [];
}
