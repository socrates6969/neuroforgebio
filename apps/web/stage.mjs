// Deployment stage (SEC-151) and the preview X-Robots-Tag value (APP-L8). Zero dependencies and no file reads
// on import, because page code (robots.txt.ts via indexing.mjs) imports it and Astro bundles it into
// dist/<theme>/chunks/. security-headers.mjs reads csp-exceptions.json via import.meta.url at import time, so page
// code must never import security-headers.mjs itself: that path breaks once bundled.

/** Deployment stage (SEC-151). Set SITE_STAGE=preview|launch|public; default preview. */
export const STAGES = ['preview', 'launch', 'public'];

export function resolveStage(value = process.env.SITE_STAGE) {
  const stage = value && value.trim() ? value.trim() : 'preview';
  if (!STAGES.includes(stage))
    throw new Error(`SITE_STAGE must be one of ${STAGES.join('|')}, got "${stage}"`);
  return stage;
}

/** APP-L8: X-Robots-Tag on every response of a preview build (see indexing.mjs). */
export const ROBOTS_NOINDEX = 'noindex, nofollow';
