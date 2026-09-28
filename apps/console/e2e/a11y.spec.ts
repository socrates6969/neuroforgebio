// CI-ONLY axe checks (WCAG 2.1 A/AA) on the console's main views. axe is injected by Playwright, so
// this context bypasses the page CSP; console.spec.ts checks the CSP itself.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { seed, signIn } from './util';

test.use({ bypassCSP: true });

async function axe(page: Page, label: string) {
  const r = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(
    r.violations.map((v) => `${label}: ${v.id} (${v.nodes.length})`),
    label,
  ).toEqual([]);
}

test('login screen', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  await axe(page, 'login');
});

test('projects, dataset, runs, lineage and account views', async ({ page, request }) => {
  const s = await seed(request);
  await signIn(page, 'scientist');
  await axe(page, 'projects');
  await page.getByRole('link', { name: s.projectName }).click();
  await axe(page, 'project');
  await page.getByRole('link', { name: s.datasetName }).click();
  await page.getByText(`Subject ${s.subjectLabel}`).click();
  await axe(page, 'dataset');
  await page.getByRole('link', { name: 'Runs' }).click();
  await axe(page, 'runs');
  await page.getByRole('link', { name: 'Lineage' }).click();
  await axe(page, 'lineage (empty)');
  await page.getByRole('link', { name: 'Sweeps' }).click();
  await axe(page, 'sweeps');
  await page.getByRole('link', { name: 'Account' }).click();
  await axe(page, 'account');
});
