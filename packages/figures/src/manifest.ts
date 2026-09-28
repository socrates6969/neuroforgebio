// Figure manifest: every plotted result file is pinned by SHA-256 (BLUEPRINT §2.5).
// The web build calls verifyManifest(); a mismatch throws, which fails `astro build`.
// Node-only module (fs/crypto): import it from Astro frontmatter or scripts, never from client code.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve, isAbsolute } from 'node:path';

export type FigureStatus = 'preliminary';
export type KeyPath = string[];

export interface PinnedFile {
  path: string;
  sha256: string;
}

export interface LineSpec {
  kind: 'line';
  x: { path: KeyPath; label: string };
  y: { label: string };
  series: { label: string; path: KeyPath }[];
}
export interface HeatmapSpec {
  kind: 'heatmap';
  base: KeyPath;
  /** Key template, e.g. "0|{row}|{col}". */
  key: string;
  field: string;
  rows: { values: string[]; label: string };
  cols: { values: string[]; label: string };
  value: { label: string };
}
export interface ScatterSpec {
  kind: 'scatter';
  base: KeyPath;
  keys: string[];
  /** Point label template, "{key}" is replaced by the key. */
  pointLabel: string;
  groupTitle: string;
  pointTitle: string;
  groups: string[];
  x: { field: string; label: string };
  y: { field: string; label: string };
}
export type PlotSpec = LineSpec | HeatmapSpec | ScatterSpec;

export interface FigureEntry {
  id: string;
  status: FigureStatus;
  result: PinnedFile;
  staticSvg?: PinnedFile;
  script: PinnedFile & { commit: string };
  plot: PlotSpec;
  notes?: string;
}

export interface FigureManifest {
  paper: string;
  generatedBy: string;
  figures: FigureEntry[];
}

export class ManifestError extends Error {}

/**
 * SHA-256 of a pinned file. Text files (no NUL byte) are hashed with CRLF normalised to LF, so a
 * Windows checkout (autocrlf) and a Linux CI checkout give the same hash. Any other byte change
 * alters the hash.
 */
export function sha256File(absPath: string): string {
  const buf = readFileSync(absPath);
  const data = buf.includes(0)
    ? buf
    : Buffer.from(buf.toString('latin1').replace(/\r\n/g, '\n'), 'latin1');
  return createHash('sha256').update(data).digest('hex');
}

export function loadManifest(absPath: string): FigureManifest {
  const m = JSON.parse(readFileSync(absPath, 'utf8')) as FigureManifest;
  if (!m || !Array.isArray(m.figures)) throw new ManifestError(`${absPath}: not a figure manifest`);
  for (const f of m.figures) {
    if (f.status !== 'preliminary')
      throw new ManifestError(`${f.id}: status must be "preliminary" (got ${String(f.status)})`);
  }
  return m;
}

const abs = (root: string, p: string) => (isAbsolute(p) ? p : resolve(root, p));

/**
 * Checks every pinned file against its SHA-256. Throws ManifestError listing all mismatches.
 * `repoRoot` is the directory the manifest paths are relative to.
 */
export function verifyManifest(m: FigureManifest, repoRoot: string): void {
  const problems: string[] = [];
  for (const f of m.figures) {
    const pins: [string, PinnedFile | undefined][] = [
      ['result', f.result],
      ['staticSvg', f.staticSvg],
      ['script', f.script],
    ];
    for (const [what, pin] of pins) {
      if (!pin) continue;
      let actual: string;
      try {
        actual = sha256File(abs(repoRoot, pin.path));
      } catch (e) {
        problems.push(`${f.id} ${what}: cannot read ${pin.path} (${(e as Error).message})`);
        continue;
      }
      if (actual !== pin.sha256)
        problems.push(
          `${f.id} ${what}: SHA-256 mismatch for ${pin.path}: manifest ${pin.sha256}, file ${actual}`,
        );
    }
  }
  if (problems.length)
    throw new ManifestError(
      `figure manifest "${m.paper}" failed verification:\n  ${problems.join('\n  ')}`,
    );
}

export function readResult(entry: FigureEntry, repoRoot: string): unknown {
  return JSON.parse(readFileSync(abs(repoRoot, entry.result.path), 'utf8'));
}
