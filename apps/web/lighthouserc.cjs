// Lighthouse CI (CI-ONLY). Run once per theme after the build:
//   LHCI_THEME=clinical pnpm --filter @nf/web lhci
//   LHCI_THEME=cosmos   pnpm --filter @nf/web lhci
// Budgets (BLUEPRINT §2.3): clinical <= 60 KB gzip JS on the home page. For cosmos the hero is in
// view at load, so Lighthouse includes the lazy three.js chunk; the "before hero visible" budget
// is enforced by e2e/hero.spec.ts and scripts/js-size.mjs instead, and the total is only warned.
const theme = process.env.LHCI_THEME === 'cosmos' ? 'cosmos' : 'clinical';
const port = theme === 'cosmos' ? 4512 : 4511;
const url = (p) => `http://127.0.0.1:${port}${p}`;

module.exports = {
  ci: {
    collect: {
      startServerCommand: `node scripts/serve.mjs dist/${theme} ${port}`,
      startServerReadyPattern: 'serving',
      url: [
        url('/'),
        url('/platform/'),
        url('/research/somatosensory-closed-loop/'),
        url('/law-tracker/'),
      ],
      numberOfRuns: 1,
      settings: { preset: 'desktop', chromeFlags: '--no-sandbox' },
    },
    assert: {
      assertions: {
        'categories:accessibility': ['error', { minScore: 0.95 }],
        'categories:best-practices': ['warn', { minScore: 0.9 }],
        'categories:seo': ['warn', { minScore: 0.9 }],
        'resource-summary:script:size': [
          theme === 'clinical' ? 'error' : 'warn',
          { maxNumericValue: 60 * 1024 },
        ],
        'resource-summary:third-party:count': ['error', { maxNumericValue: 0 }],
        'total-byte-weight': ['warn', { maxNumericValue: 900 * 1024 }],
      },
    },
    upload: { target: 'filesystem', outputDir: `.lighthouseci/${theme}` },
  },
};
