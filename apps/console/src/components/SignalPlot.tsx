import { useEffect, useRef } from 'react';
import type { Trace } from '../signal/window';

/** CSS custom property value from the theme tokens (canvas cannot read var() itself). */
function token(el: Element, name: string, fallback: string): string {
  const v = getComputedStyle(el).getPropertyValue(name).trim();
  return v || fallback;
}

export interface PlotGeometry {
  width: number;
  height: number;
  rows: number;
}

/** Map sample index/value of one trace to canvas coordinates within its row band. */
export function projector(trace: Trace, row: number, g: PlotGeometry, span: [number, number]) {
  const band = g.height / Math.max(1, g.rows);
  let lo = Infinity;
  let hi = -Infinity;
  const src = [trace.min ?? trace.mean, trace.max ?? trace.mean];
  for (const arr of src)
    for (const v of arr) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  if (!Number.isFinite(lo) || lo === hi) {
    lo = (Number.isFinite(lo) ? lo : 0) - 1;
    hi = lo + 2;
  }
  const pad = band * 0.1;
  const [t0, t1] = span;
  return {
    x: (i: number) => ((trace.t0 + i / trace.sfreq - t0) / (t1 - t0)) * g.width,
    y: (v: number) => row * band + pad + (1 - (v - lo) / (hi - lo)) * (band - 2 * pad),
    lo,
    hi,
  };
}

export function SignalPlot({
  traces,
  span,
  height = 320,
  label,
}: {
  traces: Trace[];
  span: [number, number];
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return; // jsdom / no canvas support: the text summary below still describes the data
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 800;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const ink = token(canvas, '--color-ink', '#0b2540');
    const accent = token(canvas, '--color-accent', '#0e7c86');
    const line = token(canvas, '--color-line', '#dde4ec');
    const g = { width, height, rows: traces.length };
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    for (let r = 1; r < traces.length; r++) {
      const y = (r * height) / traces.length;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
    traces.forEach((t, row) => {
      const p = projector(t, row, g, span);
      if (t.min && t.max) {
        ctx.fillStyle = accent;
        ctx.globalAlpha = 0.25;
        for (let i = 0; i < t.min.length; i++) {
          const x = p.x(i);
          const y0 = p.y(t.max[i]);
          const y1 = p.y(t.min[i]);
          ctx.fillRect(x, y0, Math.max(1, width / t.min.length), Math.max(1, y1 - y0));
        }
        ctx.globalAlpha = 1;
      }
      ctx.strokeStyle = ink;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < t.mean.length; i++) {
        const x = p.x(i);
        const y = p.y(t.mean[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.fillStyle = ink;
      ctx.font = `12px ${token(canvas, '--font-mono', 'monospace')}`;
      ctx.fillText(t.channel, 4, (row * height) / traces.length + 14);
    });
  }, [traces, span, height]);

  return (
    <figure className="plot">
      <canvas ref={ref} className="plot-canvas" height={height} role="img" aria-label={label} />
      <figcaption>
        <details>
          <summary>Values in this window</summary>
          <table className="table compact">
            <thead>
              <tr>
                <th scope="col">Channel</th>
                <th scope="col">Unit</th>
                <th scope="col">Points</th>
                <th scope="col">Min</th>
                <th scope="col">Max</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t) => {
                const lo = t.min ?? t.mean;
                const hi = t.max ?? t.mean;
                let a = Infinity;
                let b = -Infinity;
                for (const v of lo) a = Math.min(a, v);
                for (const v of hi) b = Math.max(b, v);
                return (
                  <tr key={t.channel}>
                    <td>{t.channel}</td>
                    <td>{t.unit}</td>
                    <td>{t.mean.length}</td>
                    <td>{Number.isFinite(a) ? a.toPrecision(4) : '–'}</td>
                    <td>{Number.isFinite(b) ? b.toPrecision(4) : '–'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </details>
      </figcaption>
    </figure>
  );
}
