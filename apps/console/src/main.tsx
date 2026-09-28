import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@nf/themes/clinical/tokens.css';
import './styles/console.css';
import { App } from './App';
import { ApiClient } from './api/client';
import { OidcSession, relayCallback, type Channel } from './auth/oidc';
import { SessionProvider } from './auth/session';
import { isDevIdp, loadConfig, resolveIssuer } from './config';

const channel = (name: string) => new BroadcastChannel(name) as unknown as Channel;
const root = document.getElementById('root')!;

// Login popup: this load is the OIDC redirect. Hand ?code&state to the main window and close.
if (relayCallback(window.location.search, channel)) {
  root.textContent = 'Signed in. You can close this window.';
  window.close();
} else {
  const config = loadConfig();
  const origin = window.location.origin;
  const session = new OidcSession(
    {
      issuer: resolveIssuer(config.issuer, origin),
      clientId: config.clientId,
      // the console root; the query (?code&state) is read by the popup branch above
      redirectUri: `${origin}/`,
      scope: config.scope,
      audience: config.audience || undefined,
    },
    {
      fetch: window.fetch.bind(window),
      now: () => Date.now(),
      openLogin: (url) => {
        window.open(url, 'nf-console-login', 'popup,width=520,height=680');
      },
      channel,
      origin,
    },
  );
  const client = new ApiClient({
    baseUrl: config.apiBase,
    token: () => session.accessToken(),
    onUnauthorized: () => void session.logout('refresh-failed'),
  });
  createRoot(root).render(
    <StrictMode>
      <SessionProvider session={session} client={client}>
        <App devIdp={isDevIdp(config)} />
      </SessionProvider>
    </StrictMode>,
  );
}
