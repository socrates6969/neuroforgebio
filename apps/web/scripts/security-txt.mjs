// /.well-known/security.txt (RFC 9116, SEC-157), from the draft in
// docs/inputs/security/website-security-page.md. Values come from packages/content/brand.json.
// Identical in both builds except Canonical (each build lists the canonical host first, then its own).
// Expires = build date + 180 days. Every build except a preview (SITE_STAGE=launch|public) fails while any
// placeholder remains (APP-L7: a launch build is served on the real host too).

export const EXPIRES_DAYS = 180;
/** Markers that must never reach a launch or public build. */
export const PLACEHOLDER = /\.invalid\b|<domain TBD>|\bTBD\b/i;

/** Midnight UTC of the build date. SITE_BUILD_DATE=YYYY-MM-DD pins it (scripts/build.mjs sets it once for both themes). */
export function buildDate(value = process.env.SITE_BUILD_DATE) {
  const d = value ? new Date(`${value}T00:00:00.000Z`) : new Date();
  if (Number.isNaN(d.getTime())) throw new Error(`SITE_BUILD_DATE is not a date: ${value}`);
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

export function hostsFor(brand, theme) {
  const canonical = brand.domain;
  return theme === 'cosmos' ? [canonical, brand.secondaryHost] : [canonical];
}

export function securityTxt({ brand, theme, date = buildDate() }) {
  const expires = new Date(date.getTime() + EXPIRES_DAYS * 86400_000);
  const origin = `https://${brand.domain}`;
  return (
    [
      `# ${brand.name} security contact (RFC 9116)`,
      `Contact: mailto:security@${brand.domain}`,
      `Expires: ${expires.toISOString()}`,
      'Preferred-Languages: en, no',
      ...hostsFor(brand, theme).map((h) => `Canonical: https://${h}/.well-known/security.txt`),
      `Policy: ${origin}/security#disclosure`,
      '# Encryption: roadmap (OpenPGP key or a web form over TLS)',
      '# Acknowledgments: roadmap (/security/thanks)',
    ].join('\n') + '\n'
  );
}

/** Throws if a launch or public build would ship a placeholder domain or contact (only previews may). */
export function assertPublicReady(text, { stage, brand }) {
  if (stage === 'preview') return;
  const problems = [];
  if (brand.domainIsPlaceholder) problems.push('brand.json domainIsPlaceholder is true');
  for (const line of text.split('\n'))
    if (!line.startsWith('#') && PLACEHOLDER.test(line)) problems.push(`placeholder in "${line}"`);
  if (problems.length)
    throw new Error(
      `security.txt: SITE_STAGE=${stage} but placeholders remain:\n  ${problems.join('\n  ')}`,
    );
}

/** RFC 9116 field parser: Map(field -> [values]) (comments and blank lines skipped). */
export function parseSecurityTxt(text) {
  const m = new Map();
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.startsWith('#')) continue;
    const i = line.indexOf(':');
    if (i < 0) throw new Error(`security.txt: malformed line ${line}`);
    const k = line.slice(0, i).trim().toLowerCase();
    m.set(k, [...(m.get(k) ?? []), line.slice(i + 1).trim()]);
  }
  return m;
}
