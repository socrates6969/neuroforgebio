// Pure state logic for the disclosure-style mobile navigation menu.

export interface MenuState {
  open: boolean;
}

export type MenuEvent =
  | { type: 'toggle' }
  | { type: 'key'; key: string }
  | { type: 'focusout'; insideMenu: boolean }
  | { type: 'resize'; desktop: boolean };

export interface MenuTransition {
  state: MenuState;
  /** Move focus back to the toggle button (after Escape). */
  focusToggle: boolean;
}

export function reduceMenu(state: MenuState, ev: MenuEvent): MenuTransition {
  switch (ev.type) {
    case 'toggle':
      return { state: { open: !state.open }, focusToggle: false };
    case 'key':
      if ((ev.key === 'Escape' || ev.key === 'Esc') && state.open) {
        return { state: { open: false }, focusToggle: true };
      }
      return { state, focusToggle: false };
    case 'focusout':
      if (state.open && !ev.insideMenu) return { state: { open: false }, focusToggle: false };
      return { state, focusToggle: false };
    case 'resize':
      if (ev.desktop && state.open) return { state: { open: false }, focusToggle: false };
      return { state, focusToggle: false };
  }
}
