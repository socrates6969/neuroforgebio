import type { ReactNode } from 'react';
import { ApiError } from '../api/client';

export function Loading({ what }: { what: string }) {
  return (
    <p className="muted" role="status">
      Loading {what}…
    </p>
  );
}

export function ErrorBox({ error }: { error: Error }) {
  const status = error instanceof ApiError ? error.status : null;
  const rid = error instanceof ApiError ? error.problem.request_id : undefined;
  let msg = error.message;
  if (status === 403) msg = `Not permitted: ${error.message}`;
  if (status === 404) msg = 'Not found (or not visible to your tenant).';
  return (
    <div className="alert" role="alert">
      <p>{msg}</p>
      {rid ? <p className="small mono">Request ID {rid}</p> : null}
    </div>
  );
}

export function Page({
  title,
  children,
  actions,
}: {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <>
      <div className="page-head">
        <h1 tabIndex={-1} id="page-title">
          {title}
        </h1>
        {actions ? <div className="page-actions">{actions}</div> : null}
      </div>
      {children}
    </>
  );
}

export function Mono({ children }: { children: ReactNode }) {
  return <span className="mono">{children}</span>;
}

export const shortId = (id: string) => (id.length > 12 ? `${id.slice(0, 8)}…` : id);

export function fmtTime(s: string | null | undefined): string {
  if (!s) return '–';
  const d = new Date(s);
  return Number.isNaN(d.getTime())
    ? s
    : d
        .toISOString()
        .replace('T', ' ')
        .replace(/\.\d+Z$/, 'Z');
}

export function StateBadge({ state }: { state: string }) {
  return <span className={`state state-${state.replace(/[^a-z-]/g, '')}`}>{state}</span>;
}
