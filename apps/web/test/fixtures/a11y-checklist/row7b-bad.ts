// Row 7b PLANTED FAILURE: the slider updates the visible <output> but never touches
// aria-valuetext -- the /arena "neurons" slider bug (docs/hive/A11Y-AUDIT.md row 7) before the fix.
export class Demo {
  private ui: { neurons: HTMLInputElement; neuronsOut: HTMLOutputElement };

  constructor(ui: { neurons: HTMLInputElement; neuronsOut: HTMLOutputElement }) {
    this.ui = ui;
    this.ui.neurons.addEventListener('input', () => {
      const n = Number(this.ui.neurons.value);
      this.ui.neuronsOut.textContent = String(n);
    });
  }
}
