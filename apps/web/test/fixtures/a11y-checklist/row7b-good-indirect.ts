// Row 7b PASSING fixture: playground.ts's actual pattern -- the 'input' listener just calls
// this.settingsChanged(), and THAT method does both the visible <output> write and the
// aria-valuetext update. One level of `this.<method>()` indirection is exactly what
// scriptSyncsValuetext() follows.
export class Demo {
  private ci = 0;
  private ui: { neurons: HTMLInputElement; neuronsOut: HTMLOutputElement };

  constructor(ui: { neurons: HTMLInputElement; neuronsOut: HTMLOutputElement }) {
    this.ui = ui;
    this.ui.neurons.addEventListener('input', () => {
      this.ci = Number(this.ui.neurons.value);
      this.settingsChanged();
    });
  }

  private settingsChanged() {
    const n = this.ci * 8;
    const unit = 'units';
    this.ui.neuronsOut.textContent = String(n);
    this.ui.neurons.setAttribute('aria-valuetext', `${n} ${unit}`);
  }
}
