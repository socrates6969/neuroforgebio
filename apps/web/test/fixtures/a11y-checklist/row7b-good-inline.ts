// Row 7b PASSING fixture: arena.ts's actual pattern -- both the visible <output> write and the
// aria-valuetext update happen inline, in the same 'input' listener.
export class Demo {
  private ui: { units: HTMLInputElement; unitsOut: HTMLOutputElement };

  constructor(ui: { units: HTMLInputElement; unitsOut: HTMLOutputElement }) {
    this.ui = ui;
    const unitsUnit = 'units';
    this.ui.units.addEventListener('input', () => {
      const i = Number(this.ui.units.value);
      const n = i * 8;
      this.ui.unitsOut.value = String(n);
      this.ui.units.setAttribute('aria-valuetext', `${n} ${unitsUnit}`);
    });
  }
}
