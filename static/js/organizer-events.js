/*
 * Organizer pages:
 *   /organizer/events/            - "My events" list (?mine=true: own events; admins see all)
 *   /organizer/events/new/        - create an event (the API makes you its organizer)
 *   /organizer/events/<id>/edit/  - edit one of your events, including cancelling it
 */
(function () {
  'use strict';
  const { api, auth, h, fmt, ApiError } = window.SB;

  const ROLES = ['organizer', 'admin'];

  async function getAll(url) {
    const items = [];
    while (url) {
      const page = await api.get(url);
      items.push(...page.results);
      url = page.next;
    }
    return items;
  }

  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  /* ---------- My events list ---------- */

  async function loadList(root) {
    const saved = new URLSearchParams(location.search).get('saved');
    let events;
    try {
      events = await getAll('/api/events/?mine=true&ordering=-event_date');
    } catch (err) {
      root.replaceChildren(h('div', { class: 'state' }, h('p', {}, err.message || 'Could not load your events.'),
        h('button', { class: 'btn btn-secondary', type: 'button', onclick: () => loadList(root) }, 'Try again')));
      return;
    }

    if (saved) {
      const event = events.find((e) => String(e.id) === saved);
      const note = document.getElementById('saved-note');
      note.replaceChildren(
        `Saved “${event ? event.title : 'your event'}”. `,
        h('a', { href: `/events/${saved}/` }, 'See it as fans do →'));
      note.hidden = false;
      history.replaceState(null, '', location.pathname);
    }

    if (!events.length) {
      root.replaceChildren(h('div', { class: 'state' },
        h('p', {}, "You haven't created any events yet."),
        h('a', { class: 'btn', href: '/organizer/events/new/' }, 'Create your first event')));
      return;
    }

    root.replaceChildren(h('div', { class: 'panel' },
      h('div', { class: 'table-scroll' },
        h('table', { class: 'data-table' },
          h('thead', {}, h('tr', {}, h('th', {}, 'Event'), h('th', {}, 'Date'), h('th', {}, 'Status'), h('th', { class: 'num' }, ''))),
          h('tbody', {}, events.map((e) => h('tr', {},
            h('td', {},
              h('a', { href: `/events/${e.id}/` }, e.title),
              h('div', { class: 'muted small' }, `${e.venue_name}, ${e.venue_location}`)),
            h('td', { class: 'nowrap' }, `${fmt.date(e.event_date)} · ${fmt.time(e.event_time)}`),
            h('td', {}, h('span', { class: `badge badge-${e.status}` }, fmt.statusLabel(e.status))),
            h('td', { class: 'num nowrap' },
              h('a', { class: 'btn btn-secondary btn-small', href: `/organizer/events/${e.id}/edit/` }, 'Edit')),
          ))),
        ),
      ),
      h('p', { class: 'muted small list-foot' }, 'Sales and attendance for these events are on the ',
        h('a', { href: '/reports/' }, 'Reports'), ' page.'),
    ));
  }

  /* ---------- Create / edit form ---------- */

  function clearErrors(form) {
    document.getElementById('form-error').hidden = true;
    form.querySelectorAll('[data-error-for]').forEach((el) => { el.textContent = ''; });
    form.querySelectorAll('[aria-invalid]').forEach((el) => el.removeAttribute('aria-invalid'));
  }

  function showErrors(form, err) {
    let inline = false;
    if (err instanceof ApiError && err.status === 400) {
      for (const [field, messages] of Object.entries(err.data)) {
        const slot = form.querySelector(`[data-error-for="${CSS.escape(field)}"]`);
        if (!slot) continue;
        slot.textContent = [].concat(messages).join(' ');
        if (form.elements[field]) form.elements[field].setAttribute('aria-invalid', 'true');
        inline = true;
      }
    }
    const banner = document.getElementById('form-error');
    if (!inline || err.data.detail || err.data.non_field_errors) {
      banner.textContent = err.status === 403
        ? 'You can only edit events you organise.'
        : (err.message || 'Could not save the event. Please try again.');
      banner.hidden = false;
    }
    const first = form.querySelector('[aria-invalid="true"]');
    if (first) first.focus();
  }

  function missingFields(form) {
    let missing = false;
    for (const name of ['title', 'venue', 'event_date', 'event_time']) {
      const input = form.elements[name];
      if (!input.value.trim()) {
        form.querySelector(`[data-error-for="${name}"]`).textContent = 'This field is required.';
        input.setAttribute('aria-invalid', 'true');
        missing = true;
      }
    }
    if (missing) form.querySelector('[aria-invalid="true"]').focus();
    return missing;
  }

  async function loadForm(card) {
    const form = document.getElementById('event-form');
    const eventId = card.dataset.eventId;
    const venueSelect = form.elements.venue;

    // Venues are shared and managed by administrators; organizers pick one.
    try {
      const venues = await getAll('/api/venues/');
      venueSelect.replaceChildren(
        h('option', { value: '' }, venues.length ? 'Choose a venue…' : 'No venues yet - ask an administrator to add one'),
        ...venues.map((v) => h('option', { value: v.id }, `${v.name}, ${v.location}`)));
    } catch (e) {
      venueSelect.replaceChildren(h('option', { value: '' }, 'Could not load venues'));
    }

    if (!eventId) {
      form.elements.event_date.min = today();
    } else {
      let event;
      try {
        event = await api.get(`/api/events/${eventId}/?mine=true`); // 404 unless it's yours (or you're an admin)
      } catch (err) {
        card.replaceChildren(h('h1', {}, 'Event not found'),
          h('p', {}, err.status === 404 ? "This event doesn't exist or you don't organise it." : err.message),
          h('a', { class: 'btn btn-secondary', href: '/organizer/events/' }, 'Back to my events'));
        return;
      }
      form.elements.title.value = event.title;
      form.elements.description.value = event.description;
      venueSelect.value = String(event.venue);
      form.elements.event_date.value = event.event_date;
      form.elements.event_time.value = event.event_time.slice(0, 5);
      form.elements.status.value = event.status;
      document.getElementById('status-field').hidden = false;
      document.title = `Edit ${event.title} · ${SB.siteName}`;

      form.elements.status.addEventListener('change', () => {
        document.getElementById('status-hint').textContent = form.elements.status.value === 'cancelled'
          ? 'Cancelling closes booking and ticket holders will be refused at the gate. Refunds must be arranged separately.'
          : 'Only upcoming events can be booked.';
      });
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(form);
      if (missingFields(form)) return;

      const data = {
        title: form.elements.title.value.trim(),
        description: form.elements.description.value.trim(),
        venue: Number(venueSelect.value),
        event_date: form.elements.event_date.value,
        event_time: form.elements.event_time.value,
      };
      if (eventId) data.status = form.elements.status.value;

      const button = document.getElementById('save-btn');
      const label = button.textContent;
      button.disabled = true;
      button.textContent = 'Saving…';
      try {
        const saved = eventId
          ? await api.patch(`/api/events/${eventId}/`, data)
          : await api.post('/api/events/', data);
        location.href = `/organizer/events/?saved=${saved.id}`;
      } catch (err) {
        showErrors(form, err);
        button.disabled = false;
        button.textContent = label;
      }
    });
  }

  /* ---------- Start ---------- */

  document.addEventListener('DOMContentLoaded', () => {
    if (!auth.requireLogin()) return;
    const list = document.getElementById('my-events');
    const card = document.getElementById('event-form-card');

    if (!ROLES.includes(auth.user().role)) {
      const denied = document.getElementById('organizer-denied');
      if (denied) {
        denied.hidden = false;
        document.getElementById('new-event-btn').hidden = true;
        list.replaceChildren();
      } else if (card) {
        card.replaceChildren(h('h1', {}, 'Organizers only'),
          h('p', {}, 'Ask an administrator to make your account an organizer.'));
      }
      return;
    }
    if (list) loadList(list);
    if (card) loadForm(card);
  });
})();
