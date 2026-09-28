// Client-side enhancement for server-rendered figures: hover + keyboard readouts.
// The SVG and the data table are complete without this script.
import { stepIndex } from './keys.ts';

export function enhanceFigures(root: ParentNode = document): void {
  for (const box of root.querySelectorAll<HTMLElement>('[data-nf-fig]')) {
    if (box.dataset.enhanced) continue;
    box.dataset.enhanced = '1';
    const marks = [...box.querySelectorAll<SVGElement>('[data-readout]')].sort(
      (a, b) => Number(a.dataset.i) - Number(b.dataset.i),
    );
    const out = box.querySelector<HTMLElement>('[data-readout-out]');
    if (!out || marks.length === 0) continue;
    out.hidden = false;
    box.tabIndex = 0;
    let active = -1;
    const show = (i: number) => {
      if (active >= 0) marks[active]?.classList.remove('active');
      active = i;
      const m = marks[i];
      if (!m) return;
      m.classList.add('active');
      out.textContent = `${out.dataset.label ? `${out.dataset.label}: ` : ''}${m.dataset.readout ?? ''}`;
    };
    box.addEventListener('keydown', (e) => {
      const next = stepIndex(active, e.key, marks.length);
      if (next === null) return;
      e.preventDefault();
      show(next);
    });
    box.addEventListener('pointerover', (e) => {
      const t = (e.target as Element | null)?.closest?.('[data-readout]');
      if (!t) return;
      const i = marks.indexOf(t as SVGElement);
      if (i >= 0) show(i);
    });
  }
}
