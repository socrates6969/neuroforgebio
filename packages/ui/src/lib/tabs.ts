// Pure keyboard logic for ARIA tabs (WAI-ARIA APG "Tabs with automatic activation").
// No DOM access here, so it can be unit-tested with node --test.

export type TabKeyResult = { index: number } | null;

/**
 * Returns the tab index that should receive focus/selection after `key` is pressed
 * on the tab at `current`, or null when the key is not handled.
 */
export function nextTabIndex(current: number, key: string, count: number): TabKeyResult {
  if (count <= 0 || current < 0 || current >= count) return null;
  switch (key) {
    case 'ArrowRight':
    case 'Right':
      return { index: (current + 1) % count };
    case 'ArrowLeft':
    case 'Left':
      return { index: (current - 1 + count) % count };
    case 'Home':
      return { index: 0 };
    case 'End':
      return { index: count - 1 };
    default:
      return null;
  }
}
