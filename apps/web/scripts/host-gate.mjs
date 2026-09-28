// Launch gate for the placeholder host (web-queen 2026-09-27): brand.json's domain is a reserved
// `<name>.invalid` host until the owner registers a real one (DECISIONS.md GATE B). A launch or public
// build must not ship any built text file that still names a `.invalid` host (canonical links, sitemap,
// security.txt, JSON-LD, _headers ...). Preview builds keep the placeholder. Same pattern and message style as
// security-txt.mjs assertPublicReady(), which only covers security.txt.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

/** A host under the reserved .invalid TLD (RFC 6761), e.g. site.invalid, cosmos.site.invalid. */
export const PLACEHOLDER_HOST = /\b(?:[a-z0-9-]+\.)+invalid\b/i;

/** Built text files the gate reads. JS/CSS bundles are excluded: minified code has `x.invalid` identifiers. */
const TEXT_FILE = /(\.(html?|xml|txt|json|webmanifest)|(^|\/)_headers)$/i;

function* walk(dir) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

/** ["<file>:<line>: <host>"] for every placeholder host in the built text files of `dist`. */
export function placeholderHosts(dist) {
  const hits = [];
  for (const f of walk(dist)) {
    const rel = relative(dist, f).split(sep).join('/');
    if (!TEXT_FILE.test(rel)) continue;
    const lines = readFileSync(f, 'utf8').split('\n');
    lines.forEach((line, i) => {
      const m = line.match(PLACEHOLDER_HOST);
      if (m) hits.push(`${rel}:${i + 1}: ${m[0]}`);
    });
  }
  return hits;
}

/** Throws on a launch/public build whose dist still names a placeholder host; previews pass. */
export function assertNoPlaceholderHost(dist, { stage, max = 20 }) {
  if (stage === 'preview') return;
  const hits = placeholderHosts(dist);
  if (hits.length) {
    const shown = hits.slice(0, max);
    const more = hits.length > max ? `\n  ... and ${hits.length - max} more` : '';
    throw new Error(
      `host gate: SITE_STAGE=${stage} but the placeholder host remains in ${hits.length} place(s) ` +
        `(set a real domain in packages/content/brand.json first):\n  ${shown.join('\n  ')}${more}`,
    );
  }
}
