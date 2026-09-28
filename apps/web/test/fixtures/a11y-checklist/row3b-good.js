// Row 3b PASSING fixture: the live region gets a short textContent update, not a full innerHTML
// re-render (the /arena and /playground pattern: `this.ui.live.textContent = ...`).
class Demo {
  constructor(el) {
    this.ui = {
      live: q(el, '[data-run-live]'),
      card: q(el, '[data-run-card]'),
    };
  }

  runOnce() {
    this.ui.live.textContent = 'Run complete: mean R2 0.81.';
    // The visible card CAN re-render in full -- it is not itself aria-live, so this is fine.
    this.ui.card.innerHTML = `<dl><dt>R2</dt><dd>0.81</dd></dl>`;
  }
}
