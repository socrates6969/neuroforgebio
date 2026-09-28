// Row 4 PLANTED FAILURE (paired with row4-bad-arena.html): trimmed from apps/web/src/scripts/arena.ts
// at 8e72f73. One click runs runOnce(), which writes the hidden status line AND calls renderCard(),
// which re-renders the (then also aria-live) visible card -- one event, announced twice.
function q<T extends Element>(root: ParentNode, sel: string): T {
  return root.querySelector(sel) as T;
}

class Arena {
  private ui: { button: HTMLButtonElement; live: HTMLElement; card: HTMLElement };

  constructor(el: HTMLElement) {
    this.ui = {
      button: q(el, '[data-arena-run]'),
      live: q(el, '[data-arena-live]'),
      card: q(el, '[data-arena-card]'),
    };
    this.ui.button.addEventListener('click', () => this.runOnce());
  }

  private runOnce() {
    this.ui.live.textContent = 'Running...';
    const meanR2 = 0.81;
    this.renderCard(meanR2);
    this.ui.live.textContent = `Run complete: mean R² ${meanR2.toFixed(2)}.`;
  }

  private renderCard(meanR2: number) {
    this.ui.card.innerHTML = `
      <dl class="arena-nums">
        <div><dt>Mean R² (x, y)</dt><dd class="big">${meanR2.toFixed(2)}</dd></div>
      </dl>`;
  }
}

for (const el of document.querySelectorAll<HTMLElement>('[data-arena]')) new Arena(el);
