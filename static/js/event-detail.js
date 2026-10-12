/*
 * Event detail page: event info, live seat availability and seat categories with prices
 * and view descriptions. The interactive seat map goes in #seat-map (next step).
 */
(function () {
  'use strict';
  const { api, h, fmt } = window.SB;

  function hero(event) {
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
    return h('div', { class: 'availability' },
      cell(summary.available, 'Available'),
      cell(summary.held, 'On hold'),
      cell(summary.booked, 'Booked'),
    );
  }

  function categories(venue) {
    if (!venue.categories.length) return h('p', { class: 'muted' }, 'Seat prices will be announced soon.');
    const sorted = [...venue.categories].sort((a, b) => Number(b.price) - Number(a.price));
    return h('ul', { class: 'category-list' }, sorted.map((c) =>
      h('li', {},
        h('div', { class: 'category-head' }, h('span', {}, c.name), h('span', { class: 'price' }, fmt.kes(c.price))),
        c.description ? h('div', { class: 'muted' }, c.description) : null,
      )));
  }

  function render(root, event, seats, venue) {
    const bookable = event.status === 'upcoming';
    root.replaceChildren(
      hero(event),
      h('div', { class: 'detail-grid' },
        h('section', { class: 'panel', 'aria-labelledby': 'seat-map-title' },
          h('h2', { id: 'seat-map-title' }, 'Choose your seat'),
          bookable
            ? h('div', { id: 'seat-map', class: 'seat-map-placeholder' },
                'The interactive seat map will appear here.')
            : h('div', { class: 'alert alert-info' }, 'Booking is closed for this event.'),
        ),
        h('aside', { class: 'panel' },
          h('h2', {}, 'Availability'),
          availability(seats.summary),
          h('h2', {}, 'Seat categories'),
          categories(venue),
        ),
      ),
    );
    document.title = `${event.title} · KenyaSeats`;
  }

  async function load(root) {
    const id = root.dataset.eventId;
    try {
      const [event, seats] = await Promise.all([
        api.get(`/api/events/${id}/`),
        api.get(`/api/events/${id}/seats/`),
      ]);
      const venue = await api.get(`/api/venues/${event.venue}/`);
      render(root, event, seats, venue);
    } catch (err) {
      root.replaceChildren(h('div', { class: 'state' },
        h('p', {}, err.status === 404 ? 'This event does not exist.' : (err.message || 'Could not load this event.')),
        h('a', { class: 'btn btn-secondary', href: '/events/' }, 'Back to events'),
      ));
    }
  }

  document.addEventListener('DOMContentLoaded', () => load(document.getElementById('event-detail')));
})();
