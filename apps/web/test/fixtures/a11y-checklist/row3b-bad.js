// Row 3b PLANTED FAILURE: the live region ("live", hooked to [data-run-live]) gets its whole
// subtree replaced on every run -- a screen reader would announce the entire block each time.
class Demo {
  constructor(el) {
    this.ui = {
      live: q(el, '[data-run-live]'),
    };
  }

  runOnce() {
    this.ui.live.innerHTML = `<strong>Run complete</strong>: mean R2 0.81.`;
  }
}
