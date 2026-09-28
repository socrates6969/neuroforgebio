// robots.txt per build and stage (indexing.mjs). Preview builds (the default): Disallow everything.
// Launch/public: clinical (canonical host) is crawlable + sitemap; cosmos (secondary host) is crawlable
// so crawlers can see rel=canonical, but has no sitemap of its own.
import type { APIRoute } from 'astro';
import { robotsTxt } from '../../indexing.mjs';
import { THEME, CANONICAL_ORIGIN, SITE_STAGE } from '../lib/site.ts';

export const GET: APIRoute = () =>
  new Response(robotsTxt({ stage: SITE_STAGE, theme: THEME, canonicalOrigin: CANONICAL_ORIGIN }), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
