// Row 7 PLANTED FAILURE (paired with row7-script-companion-bad.html): the listener writes the
// visible speed readout but never updates aria-valuetext, so a screen reader hears "1" while
// sighted users see "1.5×".
function q<T extends Element>(root: ParentNode, sel: string): T {
  return root.querySelector(sel) as T;
}

const SPEEDS = [0.5, 1, 1.5, 2];

class SpeedControl {
  private ui: { speed: HTMLInputElement; speedVal: HTMLElement };

  constructor(el: HTMLElement) {
    this.ui = {
      speed: q(el, '[data-speed]'),
      speedVal: q(el, '[data-speed-val]'),
    };
    this.ui.speed.addEventListener('input', () => {
      const s = SPEEDS[Number(this.ui.speed.value)];
      this.ui.speedVal.textContent = `${s}×`;
    });
  }
}

for (const el of document.querySelectorAll<HTMLElement>('[data-speed-widget]')) new SpeedControl(el);
