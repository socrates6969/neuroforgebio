// sitemap.xml with canonical (clinical-host) URLs. The gallery and 404 are excluded.
import type { APIRoute } from 'astro';
import { canonicalUrl, sitemapRoutes } from '../lib/site.ts';

export const GET: APIRoute = () => {
  const urls = sitemapRoutes()
    .map((r) => `  <url><loc>${canonicalUrl(r)}</loc></url>`)
    .join('\n');
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml' } });
};
