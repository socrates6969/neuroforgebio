import { useSession } from '../auth/session';
import { allowedActions } from '../authz/can';
import { Page } from '../components/common';
import { ABSOLUTE_S, ACCESS_MAX_S, IDLE_S } from '../auth/oidc';

export function AccountPage() {
  const { me, meError } = useSession();
  return (
    <Page title="Account">
      {meError ? <p className="alert">Could not load your identity: {meError}</p> : null}
      {me ? (
        <dl className="kv card">
          <dt>User</dt>
          <dd className="mono">{me.id}</dd>
          <dt>Tenant</dt>
          <dd className="mono">{me.tenant_id}</dd>
          <dt>Effective roles</dt>
          <dd>{me.roles.join(', ') || 'none'}</dd>
          <dt>Phishing-resistant login</dt>
          <dd>{me.mfa_phishing_resistant ? 'yes' : 'no (admin-class roles are inactive)'}</dd>
        </dl>
      ) : null}
      <h2>What the console offers you</h2>
      <p className="small">
        Controls are hidden when your roles cannot use them. That is convenience, not security: the
        platform checks every request itself.
      </p>
      <ul className="columns">
        {allowedActions(me?.roles ?? []).map((a) => (
          <li key={a} className="mono small">
            {a}
          </li>
        ))}
      </ul>
      <h2>Session</h2>
      <p className="small">
        Tokens are kept in memory only (a reload signs you out). Access tokens are used for at most{' '}
        {ACCESS_MAX_S / 60} min, then rotated; you are signed out after {IDLE_S / 60} min without
        activity and {ABSOLUTE_S / 3600} h after sign-in.
      </p>
    </Page>
  );
}
