/*
 * Event detail page: event info, the interactive seat map, the selected seat's details and
 * view preview, and the "Hold this seat" action. Seat statuses refresh every 15 seconds.
 */
(function () {
  'use strict';
  const { api, auth, h, fmt } = window.SB;

  const REFRESH_MS = 15000;

  let eventId, event, venue, map;
  let refreshTimer = null;
  let holding = false;

  /* ---------- Static sections ---------- */

  function hero() {
    return h('section', { class: 'event-hero' },
      h('h1', {}, event.title),
      event.status !== 'upcoming'
        ? h('span', { class: `badge badge-${event.status}` }, fmt.statusLabel(event.status))
        : null,
      h('div', { class: 'event-meta' },
        h('span', {}, `📅 ${fmt.date(event.event_date)}`),
        h('span', {}, `🕒 ${fmt.time(event.event_time)}`),
        h('span', {}, `📍 ${event.venue_name}, ${event.venue_location}`),
      ),
      event.description ? h('p', { class: 'muted event-desc' }, event.description) : null,
    );
  }

  function availability(summary) {
    const cell = (count, label) => h('div', {}, h('strong', {}, count), h('span', {}, label));
    return h('div', { class: 'availability', id: 'availability' },
      cell(summary.available, 'Available'),
      cell(summary.held, 'On hold'),
      cell(summary.booked, 'Booked'),
    );
  }

  function categoryDescription(categoryId) {
    const cat = venue.categories.find((c) => c.id === categoryId);
    return cat ? cat.description : '';
  }

  /* ---------- Selected seat ---------- */

  function showMessage(text, kind = 'error') {
    const box = document.getElementById('seat-message');
    box.className = `alert alert-${kind}`;
    box.textContent = text;
    box.hidden = !text;
  }

  function renderSelection(seat) {
    const panel = document.getElementById('selection');
    const bar = document.getElementById('selection-bar');

    // Remember the pick in the URL so it survives the login redirect and page refresh.
    const url = new URL(location.href);
    if (seat) url.searchParams.set('seat', seat.id); else url.searchParams.delete('seat');
    history.replaceState(null, '', url);

    if (!seat) {
      panel.replaceChildren(h('p', { class: 'muted' }, 'Tap an available seat on the map to see its price and view.'));
      bar.hidden = true;
      return;
    }

    const holdButton = () => h('button', { class: 'btn hold-btn', type: 'button', onclick: hold },
      auth.user() ? 'Hold this seat' : 'Log in to hold this seat');

    panel.replaceChildren(
      h('div', { class: 'selected-seat' },
        h('div', {},
          h('div', { class: 'selected-title' }, `Row ${seat.row} · Seat ${seat.number}`),
          h('div', { class: 'muted' }, seat.category),
        ),
        h('div', { class: 'price selected-price' }, fmt.kes(seat.price)),
      ),
      h('h3', {}, 'View from this seat'),
      SB.seatMap.viewPreview(seat, categoryDescription(seat.category_id)),
      holdButton(),
      h('p', { class: 'hold-note muted' }, 'We hold the seat for you for 10 minutes while you pay with M-Pesa.'),
    );

    // Compact bar pinned to the bottom of the screen on phones.
    bar.replaceChildren(
      h('div', {},
        h('strong', {}, `Row ${seat.row} · Seat ${seat.number}`),
        h('div', { class: 'muted' }, `${seat.category} · ${fmt.kes(seat.price)}`),
      ),
      holdButton(),
    );
    bar.hidden = false;
  }

  async function hold() {
    const seat = map && map.selected;
    if (!seat || holding) return;
    if (!auth.requireLogin()) return;

    holding = true;
    document.querySelectorAll('.hold-btn').forEach((b) => { b.disabled = true; b.textContent = 'Holding…'; });
    try {
      const booking = await api.post('/api/bookings/', { event: event.id, seat: seat.id });
      location.href = `/checkout/${booking.id}/`;
    } catch (err) {
      holding = false;
      if (err.status === 401) {
        auth.requireLogin();
        return;
      }
      if (err.status === 409) {
        map.setStatus(seat.id, 'held');
        showMessage('Sorry, someone has just taken that seat. Please pick another.');
      } else {
        renderSelection(seat);
        showMessage(err.message || 'Could not hold this seat. Please try again.');
      }
    }
  }

  /** If the fan is already holding a seat for this event, offer to continue to checkout. */
  async function showExistingHold() {
    if (!auth.user()) return;
    try {
      const data = await api.get(`/api/bookings/?event=${event.id}&status=pending`);
      const booking = data.results[0];
      if (!booking) return;
      const banner = document.getElementById('existing-hold');
      banner.replaceChildren(
        h('span', {}, `You're holding Row ${booking.row}, Seat ${booking.seat_number}. `),
        h('a', { href: `/checkout/${booking.id}/` }, 'Continue to payment →'),
      );
      banner.hidden = false;
    } catch (e) { /* not essential */ }
  }

  /* ---------- Live refresh ---------- */

  async function refreshSeats() {
    try {
      const data = await api.get(`/api/events/${eventId}/seats/`);
      const lostSelection = map.update(data.seats);
      document.getElementById('availability').replaceWith(availability(data.summary));
      if (lostSelection) showMessage('The seat you picked has just been taken. Please choose another.');
    } catch (e) { /* try again next tick */ }
  }

  function startRefreshing() {
    stopRefreshing();
    refreshTimer = setInterval(refreshSeats, REFRESH_MS);
  }

  function stopRefreshing() {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }

  /* ---------- Page ---------- */

  function render(root, seats) {
    const bookable = event.status === 'upcoming';

    root.replaceChildren(
      hero(),
      h('div', { class: 'alert alert-info', id: 'existing-hold', hidden: true }),
      h('div', { class: 'detail-grid' },
        h('section', { class: 'panel', 'aria-labelledby': 'seat-map-title' },
          h('h2', { id: 'seat-map-title' }, bookable ? 'Choose your seat' : 'Seating plan'),
          bookable ? null : h('div', { class: 'alert alert-info' }, 'Booking is closed for this event.'),
          h('div', { class: 'alert', id: 'seat-message', role: 'alert', hidden: true }),
          h('div', { id: 'seat-map' }),
        ),
        h('aside', { class: 'side-panels' },
          bookable ? h('section', { class: 'panel', 'aria-labelledby': 'selection-title' },
            h('h2', { id: 'selection-title' }, 'Your seat'),
            h('div', { id: 'selection', 'aria-live': 'polite' }),
          ) : null,
          h('section', { class: 'panel' },
            h('h2', {}, 'Availability'),
            availability(seats.summary),
          ),
        ),
      ),
      h('div', { class: 'selection-bar', id: 'selection-bar', hidden: true }),
    );
    document.title = `${event.title} · KenyaSeats`;

    map = SB.seatMap.create(document.getElementById('seat-map'), seats.seats, {
      onSelect(seat) {
        showMessage('');
        if (bookable) renderSelection(seat);
      },
    });
    if (!bookable) return;

    // Read ?seat= before renderSelection(null) clears it from the URL.
    const preselect = Number(new URLSearchParams(location.search).get('seat'));
    if (!preselect || !map.select(preselect)) renderSelection(null);

    showExistingHold();
    startRefreshing();
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopRefreshing();
      } else {
        refreshSeats();
        startRefreshing();
      }
    });
  }

  async function load(root) {
    eventId = root.dataset.eventId;
    try {
      const [eventData, seats] = await Promise.all([
        api.get(`/api/events/${eventId}/`),
        api.get(`/api/events/${eventId}/seats/`),
      ]);
      event = eventData;
      venue = await api.get(`/api/venues/${event.venue}/`);
      render(root, seats);
    } catch (err) {
      root.replaceChildren(h('div', { class: 'state' },
        h('p', {}, err.status === 404 ? 'This event does not exist.' : (err.message || 'Could not load this event.')),
        h('a', { class: 'btn btn-secondary', href: '/events/' }, 'Back to events'),
      ));
    }
  }

  document.addEventListener('DOMContentLoaded', () => load(document.getElementById('event-detail')));
})();
