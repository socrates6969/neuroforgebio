import { useEffect, useRef, useState } from 'react';
import brand from '@nf/content/brand.json';
import { useRoles, useSession } from './auth/session';
import { can } from './authz/can';
import { AccountPage } from './pages/Account';
import { ApiKeysPage } from './pages/ApiKeys';
import { DatasetPage } from './pages/Dataset';
import { LineagePage } from './pages/Lineage';
import { ModelPage, ModelsPage } from './pages/Models';
import { ProjectPage } from './pages/Project';
import { ProjectsPage } from './pages/Projects';
import { RecordingPage } from './pages/Recording';
import { RunPage, RunsPage } from './pages/Runs';
import { SweepPage, SweepsPage } from './pages/Sweep';
import { MODEL_READ_ACTION } from './registry/context';
import { href, useRoute, type Route } from './router';
import { runRegistry } from './runs';

export const APP_NAME = `${brand.name} console`;

const REASONS: Record<string, string> = {
  idle: 'You were signed out after 15 minutes without activity.',
  absolute: 'Your session reached its 12-hour limit. Please sign in again.',
  'refresh-failed': 'Your session could not be renewed. Please sign in again.',
  logout: 'You are signed out.',
};

export function App({ devIdp = false }: { devIdp?: boolean }) {
  const { state } = useSession();
  useEffect(() => {
    document.title = APP_NAME;
  }, []);
  useEffect(() => {
    if (state.status === 'signed-out') runRegistry.clear();
  }, [state.status]);
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {devIdp ? (
        <p className="dev-banner" role="note">
          Development identity provider: not for real data.
        </p>
      ) : null}
      {state.status === 'signed-in' ? <Shell /> : <Login />}
    </>
  );
}

function Login() {
  const { session, state } = useSession();
  const [error, setError] = useState<string | null>(null);
  const reason = state.status === 'signed-out' ? state.reason : undefined;
  const signIn = () => {
    setError(null);
    session.login().catch((e: Error) => setError(e.message));
  };
  return (
    <main id="main" className="login">
      <div className="card login-card">
        <h1>{APP_NAME}</h1>
        {reason ? <p role="status">{REASONS[reason]}</p> : null}
        <p>Sign in with your organisation's identity provider. A sign-in window opens.</p>
        <button
          type="button"
          className="btn"
          onClick={signIn}
          disabled={state.status === 'signing-in'}
        >
          {state.status === 'signing-in' ? 'Waiting for sign-in…' : 'Sign in'}
        </button>
        {error ? (
          <p className="alert" role="alert">
            Sign-in failed: {error}
          </p>
        ) : null}
      </div>
    </main>
  );
}

function Shell() {
  const route = useRoute();
  const roles = useRoles();
  const { session, me } = useSession();
  const main = useRef<HTMLElement>(null);

  // Move focus to the new page's heading on navigation (screen readers announce it).
  useEffect(() => {
    const h = main.current?.querySelector<HTMLElement>('#page-title');
    h?.focus();
  }, [route.name, route.params.id]);

  const nav: Array<[string, string, boolean]> = [
    ['Projects', '/projects', can(roles, 'project:read')],
    ['Runs', '/runs', can(roles, 'run:read')],
    ['Lineage', '/lineage/', can(roles, 'provenance:read')],
    ['Sweeps', '/sweeps', can(roles, 'sweep:read')],
    ['API keys', '/api-keys', can(roles, 'apikey:read')],
    ['Models', '/models', can(roles, MODEL_READ_ACTION)],
    ['Account', '/account', true],
  ];
  const current = `/${route.name}`;

  return (
    <>
      <header className="topbar">
        <span className="brand">{APP_NAME}</span>
        <nav aria-label="Main">
          <ul>
            {nav
              .filter(([, , visible]) => visible)
              .map(([label, path]) => (
                <li key={path}>
                  <a
                    href={href(path)}
                    aria-current={
                      path.startsWith(current) && route.name !== 'not-found' ? 'page' : undefined
                    }
                  >
                    {label}
                  </a>
                </li>
              ))}
          </ul>
        </nav>
        <span className="who small">{me ? me.roles.join(', ') || 'no roles' : ''}</span>
        <button type="button" className="btn ghost" onClick={() => void session.logout('logout')}>
          Sign out
        </button>
      </header>
      <main id="main" ref={main}>
        <RouteView route={route} />
      </main>
    </>
  );
}

export function RouteView({ route }: { route: Route }) {
  const id = route.params.id ?? '';
  switch (route.name) {
    case 'projects':
      return <ProjectsPage />;
    case 'project':
      return <ProjectPage id={id} />;
    case 'dataset':
      return <DatasetPage id={id} />;
    case 'recording':
      return <RecordingPage id={id} />;
    case 'runs':
      return <RunsPage />;
    case 'run':
      return <RunPage id={id} />;
    case 'sweeps':
      return <SweepsPage />;
    case 'sweep':
      return <SweepPage id={id} />;
    case 'models':
      return <ModelsPage />;
    case 'model':
      // key: a different model is a new page (no flash of the previous model's data; BUG-HUNT L4)
      return <ModelPage key={id} id={id} query={route.query} />;
    case 'lineage':
      return <LineagePage id={id} query={route.query} />;
    case 'account':
      return <AccountPage />;
    case 'api-keys':
      return <ApiKeysPage />;
    default:
      return (
        <>
          <h1 id="page-title" tabIndex={-1}>
            Page not found
          </h1>
          <p>
            <a href={href('/projects')}>Go to projects</a>
          </p>
        </>
      );
  }
}
