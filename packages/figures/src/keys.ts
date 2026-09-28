// Pure keyboard stepping through the marks of a figure (unit-tested with node --test).
// Returns the new active index, or null when the key is not handled. `current` = -1 means none active.
export function stepIndex(current: number, key: string, count: number): number | null {
  if (count <= 0) return null;
  switch (key) {
    case 'ArrowRight':
    case 'ArrowDown':
      return current < 0 ? 0 : Math.min(count - 1, current + 1);
    case 'ArrowLeft':
    case 'ArrowUp':
      return current < 0 ? 0 : Math.max(0, current - 1);
    case 'Home':
      return 0;
    case 'End':
      return count - 1;
    case 'PageDown':
      return current < 0 ? 0 : Math.min(count - 1, current + 10);
    case 'PageUp':
      return current < 0 ? 0 : Math.max(0, current - 10);
    default:
      return null;
  }
}
