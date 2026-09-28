// Minimal hash router: #/projects, #/projects/<id>, #/datasets/<id>, #/recordings/<id>, #/runs,
// #/runs/<id>, #/sweeps, #/sweeps/<id>, #/models, #/models/<id>?version=<versionId>,
// #/lineage/<nodeId>?direction=up|down|both&depth=n, #/api-keys.
// Hash routing needs no server rewrite rules and keeps the OIDC callback query (?code&state) apart
// from app routes.
import { useEffect, useState } from 'react';

export interface Route {
  name: string;
  params: Record<string, string>;
  query: URLSearchParams;
}

const PATTERNS: Array<[string, RegExp, string[]]> = [
  ['projects', /^\/?(?:projects)?\/?$/, []],
  ['project', /^\/projects\/([^/]+)$/, ['id']],
  ['dataset', /^\/datasets\/([^/]+)$/, ['id']],
  ['recording', /^\/recordings\/([^/]+)$/, ['id']],
  ['runs', /^\/runs\/?$/, []],
  ['run', /^\/runs\/([^/]+)$/, ['id']],
  ['sweeps', /^\/sweeps\/?$/, []],
  ['sweep', /^\/sweeps\/([^/]+)$/, ['id']],
  ['models', /^\/models\/?$/, []],
  ['model', /^\/models\/([^/]+)$/, ['id']],
  ['lineage', /^\/lineage\/?([^/]*)$/, ['id']],
  ['account', /^\/account\/?$/, []],
  ['api-keys', /^\/api-keys\/?$/, []],
];

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, '') || '/';
  const [path, qs = ''] = raw.split('?', 2);
  const query = new URLSearchParams(qs);
  for (const [name, re, keys] of PATTERNS) {
    const m = re.exec(path);
    if (m) {
      const params: Record<string, string> = {};
      keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1] ?? '')));
      return { name, params, query };
    }
  }
  return { name: 'not-found', params: { path }, query };
}

export function href(path: string, query?: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {}))
    if (v !== undefined && v !== '') q.set(k, String(v));
  const s = q.toString();
  return `#${path}${s ? `?${s}` : ''}`;
}

export function navigate(path: string, query?: Record<string, string | number | undefined>): void {
  window.location.hash = href(path, query).slice(1);
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}
