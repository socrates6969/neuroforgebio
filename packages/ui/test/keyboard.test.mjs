// Cheap local unit tests of the keyboard logic (the DOM-level tests are Playwright, CI-only).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { nextTabIndex } from '../src/lib/tabs.ts';
import { reduceMenu } from '../src/lib/menu.ts';

test('tabs: arrows wrap around', () => {
  assert.deepEqual(nextTabIndex(0, 'ArrowRight', 2), { index: 1 });
  assert.deepEqual(nextTabIndex(1, 'ArrowRight', 2), { index: 0 });
  assert.deepEqual(nextTabIndex(0, 'ArrowLeft', 3), { index: 2 });
  assert.deepEqual(nextTabIndex(2, 'ArrowLeft', 3), { index: 1 });
});

test('tabs: Home/End jump to ends', () => {
  assert.deepEqual(nextTabIndex(1, 'Home', 3), { index: 0 });
  assert.deepEqual(nextTabIndex(0, 'End', 3), { index: 2 });
});

test('tabs: other keys and bad input are ignored', () => {
  assert.equal(nextTabIndex(0, 'Tab', 2), null);
  assert.equal(nextTabIndex(0, 'Enter', 2), null);
  assert.equal(nextTabIndex(0, 'ArrowDown', 2), null);
  assert.equal(nextTabIndex(5, 'ArrowRight', 2), null);
  assert.equal(nextTabIndex(0, 'ArrowRight', 0), null);
});

test('menu: toggle opens and closes', () => {
  const a = reduceMenu({ open: false }, { type: 'toggle' });
  assert.equal(a.state.open, true);
  assert.equal(reduceMenu(a.state, { type: 'toggle' }).state.open, false);
});

test('menu: Escape closes an open menu and returns focus to the toggle', () => {
  const r = reduceMenu({ open: true }, { type: 'key', key: 'Escape' });
  assert.deepEqual(r, { state: { open: false }, focusToggle: true });
  const closed = reduceMenu({ open: false }, { type: 'key', key: 'Escape' });
  assert.equal(closed.focusToggle, false);
});

test('menu: focus leaving the menu closes it; focus inside keeps it open', () => {
  assert.equal(
    reduceMenu({ open: true }, { type: 'focusout', insideMenu: false }).state.open,
    false,
  );
  assert.equal(reduceMenu({ open: true }, { type: 'focusout', insideMenu: true }).state.open, true);
});

test('menu: switching to desktop layout closes it', () => {
  assert.equal(reduceMenu({ open: true }, { type: 'resize', desktop: true }).state.open, false);
  assert.equal(reduceMenu({ open: true }, { type: 'resize', desktop: false }).state.open, true);
});
