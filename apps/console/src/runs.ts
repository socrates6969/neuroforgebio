// Runs known to this browser session. The platform has no "list runs" route yet (only POST /v1/runs,
// GET /v1/runs/{id}, cancel), so the runs page lists runs started or opened in this session (memory
// only, gone on reload) and opens any other run by ID. Replace with the list route when it exists.
import type { RunOut } from './api/generated';

export const TERMINAL_RUN_STATES = new Set(['succeeded', 'failed', 'cancelled']);

type Listener = () => void;

class RunRegistry {
  private runs = new Map<string, RunOut>();
  private listeners = new Set<Listener>();
  // cached snapshot: useSyncExternalStore needs a stable value between changes
  private snapshot: RunOut[] = [];

  private changed(): void {
    this.snapshot = [...this.runs.values()].sort((a, b) =>
      b.created_at.localeCompare(a.created_at),
    );
    for (const l of this.listeners) l();
  }

  remember(run: RunOut): void {
    const prev = this.runs.get(run.id);
    if (prev && JSON.stringify(prev) === JSON.stringify(run)) return;
    this.runs.set(run.id, run);
    this.changed();
  }

  list(): RunOut[] {
    return this.snapshot;
  }

  /** Signing out forgets them (they are tenant data). */
  clear(): void {
    this.runs.clear();
    this.changed();
  }

  subscribe(l: Listener): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }
}

export const runRegistry = new RunRegistry();
