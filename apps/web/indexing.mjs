// Search-engine indexing per deployment stage (APP-L8). Zero dependencies; used by
// src/pages/robots.txt.ts (stage from astro.config.mjs); the X-Robots-Tag header itself is emitted by
// security-headers.mjs globalHeaders().
// Preview builds (SITE_STAGE=preview, the default) must never be indexed: robots.txt disallows
// everything and every response carries X-Robots-Tag. There is no per-page robots meta for preview:
// Base.astro renders the home page, which is frozen by owner directive (parked, see
// docs/hive/REVIEW-ci-site-hardening.md). Launch and public builds are crawlable; single pages opt out
// with Base's `noindex` prop (gallery, 404, legal drafts), unchanged from main.
// From stage.mjs, never security-headers.mjs: page code bundles this module, and security-headers.mjs reads
// csp-exceptions.json relative to import.meta.url, which breaks inside dist/<theme>/chunks/.
import { ROBOTS_NOINDEX, resolveStage } from './stage.mjs';

/** X-Robots-Tag value for preview builds (defined next to the other headers). */
export { ROBOTS_NOINDEX };

export function isIndexable(stage) {
  return resolveStage(stage) !== 'preview';
}

/** robots.txt text. Clinical (canonical host) lists the sitemap; cosmos (secondary host) does not. */
export function robotsTxt({ stage, theme, canonicalOrigin }) {
  if (!isIndexable(stage))
    return (
      [
        `# SITE_STAGE=${resolveStage(stage)}: preview builds are not for search engines.`,
        'User-agent: *',
        'Disallow: /',
      ].join('\n') + '\n'
    );
  const lines = ['User-agent: *', 'Allow: /', 'Disallow: /gallery/'];
  if (theme === 'clinical')
    lines.push('', `Sitemap: ${new URL('/sitemap.xml', canonicalOrigin).href}`);
  else
    lines.push(
      '',
      `# Secondary host (theme: ${theme}). Canonical URLs point to ${canonicalOrigin}`,
    );
  return lines.join('\n') + '\n';
}
