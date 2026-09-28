// Serves the research team's static SVG exports (hash-verified) for download / print.
import type { APIRoute, GetStaticPaths } from 'astro';
import { readFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { content } from '../../../lib/site.ts';
import { manifestFor, REPO_ROOT } from '../../../lib/figures.ts';

export const getStaticPaths: GetStaticPaths = () => {
  const out: { params: { file: string }; props: { path: string } }[] = [];
  for (const slug of Object.keys(content.whitepapers)) {
    for (const f of manifestFor(slug)?.figures ?? []) {
      if (f.staticSvg)
        out.push({
          params: { file: basename(f.staticSvg.path) },
          props: { path: f.staticSvg.path },
        });
    }
  }
  return out;
};

export const GET: APIRoute = ({ props }) =>
  new Response(readFileSync(join(REPO_ROOT, (props as { path: string }).path)), {
    headers: { 'Content-Type': 'image/svg+xml' },
  });
