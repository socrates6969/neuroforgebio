// Row 7 PASSING fixture (paired with row7-playground-good.html), trimmed from
// apps/web/src/scripts/playground.ts: the scrubber's listener calls draw(), which writes the time
// <output> and the scrubber's aria-valuetext; the neurons listener calls settingsChanged(), which
// writes the neurons <output> and the neurons aria-valuetext. One call level each.
function q<T extends Element>(root: ParentNode, sel: string): T {
  return root.querySelector(sel) as T;
}

class Playground {
  private t = 0;
  private ci = 4;
  private counts = [8, 16, 32, 64, 130];
  private ui: {
    scrub: HTMLInputElement;
    time: HTMLOutputElement;
    neurons: HTMLInputElement;
    neuronsOut: HTMLOutputElement;
  };

  constructor(private el: HTMLElement) {
    this.ui = {
      scrub: q(el, '[data-pg-scrub]'),
      time: q(el, '[data-pg-time]'),
      neurons: q(el, '[data-pg-neurons]'),
      neuronsOut: q(el, '[data-pg-neurons-out]'),
    };
    const ui = this.ui;
    ui.scrub.addEventListener('input', () => {
      this.t = Number(ui.scrub.value);
      this.draw();
    });
    ui.neurons.addEventListener('input', () => {
      this.ci = Number(ui.neurons.value);
      this.settingsChanged();
    });
  }

  private settingsChanged() {
    const n = this.counts[this.ci];
    const unit = this.el.dataset.neuronsUnit ?? '';
    this.ui.neuronsOut.textContent = String(n);
    this.ui.neurons.setAttribute('aria-valuetext', `${n} ${unit}`);
    this.draw();
  }

  private draw() {
    const secs = this.el.dataset.seconds ?? 's';
    this.ui.scrub.value = String(Math.round(this.t));
    this.ui.scrub.setAttribute(
      'aria-valuetext',
      `${(this.t / 1000).toFixed(2)} ${secs} / 1.20 ${secs}`,
    );
    this.ui.time.textContent = `${(this.t / 1000).toFixed(2)} / 1.20 ${secs}`;
  }
}

for (const el of document.querySelectorAll<HTMLElement>('[data-pg]')) new Playground(el);
