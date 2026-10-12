/* Login and registration forms. */
(function () {
  'use strict';
  const { auth, ApiError } = window.SB;

  function clearErrors(form) {
    document.getElementById('form-error').hidden = true;
    form.querySelectorAll('[data-error-for]').forEach((el) => { el.textContent = ''; });
    form.querySelectorAll('[aria-invalid]').forEach((el) => el.removeAttribute('aria-invalid'));
  }

  /** Put each API field error under its input; anything else goes in the banner. */
  function showErrors(form, err) {
    let shownInline = false;
    if (err instanceof ApiError && err.status === 400) {
      for (const [field, messages] of Object.entries(err.data)) {
        const slot = form.querySelector(`[data-error-for="${CSS.escape(field)}"]`);
        if (!slot) continue;
        slot.textContent = [].concat(messages).join(' ');
        if (form.elements[field]) form.elements[field].setAttribute('aria-invalid', 'true');
        shownInline = true;
      }
    }

    let bannerText = '';
    if (err.status === 401) bannerText = 'Wrong username or password.';
    else if (err.data && (err.data.detail || err.data.non_field_errors)) bannerText = err.message;
    else if (!shownInline) bannerText = err.message || 'Something went wrong. Please try again.';

    const banner = document.getElementById('form-error');
    banner.textContent = bannerText;
    banner.hidden = !bannerText;

    const firstInvalid = form.querySelector('[aria-invalid="true"]');
    if (firstInvalid) firstInvalid.focus();
  }

  /** Browser-side checks for empty required fields, so obvious mistakes don't need a round trip. */
  function missingFields(form) {
    let missing = false;
    form.querySelectorAll('[required]').forEach((input) => {
      if (!input.value.trim()) {
        form.querySelector(`[data-error-for="${input.name}"]`).textContent = 'This field is required.';
        input.setAttribute('aria-invalid', 'true');
        missing = true;
      }
    });
    if (missing) form.querySelector('[aria-invalid="true"]').focus();
    return missing;
  }

  function wire(form, submit) {
    if (!form) return;
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      if (missingFields(form)) return;
      const button = form.querySelector('button[type="submit"]');
      const label = button.textContent;
      button.disabled = true;
      button.textContent = 'Please wait…';
      try {
        await submit(Object.fromEntries(new FormData(form)));
        location.href = auth.nextUrl('/events/');
      } catch (err) {
        showErrors(form, err);
        button.disabled = false;
        button.textContent = label;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Already logged in? Skip the form.
    if (auth.user()) {
      location.replace(auth.nextUrl('/events/'));
      return;
    }

    // Carry ?next= across the "Log in" <-> "Create account" links.
    const next = new URLSearchParams(location.search).get('next');
    if (next) {
      document.querySelectorAll('[data-keep-next]').forEach((a) => {
        a.href += '?next=' + encodeURIComponent(next);
      });
    }

    wire(document.getElementById('login-form'), (data) => auth.login(data.username.trim(), data.password));
    wire(document.getElementById('register-form'), (data) => {
      for (const key of ['username', 'email', 'first_name', 'last_name', 'phone']) data[key] = data[key].trim();
      return auth.register(data);
    });
  });
})();
