// Row 4 PASSING fixture (paired with row4-good-form.html): the error summary is written only by the
// submit path (showErrors), the saved confirmation only by the autosave path (autosave). No
// listener or method -- followed one call level -- writes both, so they are different events.
function q(root, sel) {
  return root.querySelector(sel);
}

class ProfileForm {
  constructor(el) {
    this.ui = {
      form: q(el, '[data-profile-form]'),
      errors: q(el, '[data-form-errors]'),
      saved: q(el, '[data-saved-status]'),
      name: q(el, '[data-name]'),
    };
    this.ui.form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.showErrors();
    });
    this.ui.name.addEventListener('change', () => this.autosave());
  }

  showErrors() {
    const problems = this.validate();
    this.ui.errors.textContent = problems.length ? `Fix before saving: ${problems.join('; ')}` : '';
  }

  autosave() {
    // (the draft would be stored here)
    this.ui.saved.textContent = 'Draft saved.';
  }

  validate() {
    return this.ui.name.value.trim() ? [] : ['Display name is required'];
  }
}

for (const el of document.querySelectorAll('[data-profile-form]')) new ProfileForm(el);
