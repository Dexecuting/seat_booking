/*
 * "My tickets" pages:
 *   /tickets/       - list (upcoming and past) plus any unpaid seat holds
 *   /tickets/<id>/  - one ticket with a large QR code for the gate
 */
(function () {
  'use strict';
  const { api, auth, h, fmt } = window.SB;

  /** Local date as 'YYYY-MM-DD', to compare with event dates from the API. */
  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  /** '2026-10-19' -> 'Oct' */
  function monthShort(isoDate) {
    const [y, m] = isoDate.split('-').map(Number);
    return new Date(y, m - 1, 1).toLocaleDateString('en-KE', { month: 'short' });
  }

  function usedAtText(ticket) {
    const used = new Date(ticket.used_at);
    return `Used ${used.toLocaleDateString('en-KE', { day: 'numeric', month: 'short' })} at ` +
      used.toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  function statusBadge(ticket, isPast) {
    if (ticket.is_used) return h('span', { class: 'badge badge-completed' }, 'Used');
    if (isPast) return h('span', { class: 'badge badge-completed' }, 'Expired');
    return h('span', { class: 'badge badge-upcoming' }, 'Valid');
  }

  /** Follow DRF pagination so fans with many tickets still see them all. */
  async function getAll(url) {
    const items = [];
    while (url) {
      const page = await api.get(url);
      items.push(...page.results);
      url = page.next;
    }
    return items;
  }

  /* ---------- List page ---------- */

  function ticketCard(ticket, isPast) {
    return h('a', { class: `ticket-card${isPast || ticket.is_used ? ' is-past' : ''}`, href: `/tickets/${ticket.id}/` },
      h('div', { class: 'ticket-date' },
        h('span', { class: 'ticket-day' }, ticket.event_date.slice(8, 10)),
        h('span', { class: 'ticket-month' }, monthShort(ticket.event_date)),
      ),
      h('div', { class: 'ticket-info' },
        h('div', { class: 'ticket-title' }, ticket.event_title),
        h('div', { class: 'muted' }, `${fmt.date(ticket.event_date)} · ${fmt.time(ticket.event_time)} · ${ticket.venue}`),
        h('div', { class: 'ticket-seat' }, `Row ${ticket.row}, Seat ${ticket.seat_number} · ${ticket.category}`),
      ),
      h('div', { class: 'ticket-side' },
        statusBadge(ticket, isPast),
        isPast || ticket.is_used ? null : h('span', { class: 'ticket-open' }, 'Show QR →'),
      ),
    );
  }

  async function showPendingHolds() {
    try {
      const holds = await getAll('/api/bookings/?status=pending');
      if (!holds.length) return;
      document.getElementById('pending-holds').replaceChildren(...holds.map((b) =>
        h('div', { class: 'alert alert-info hold-alert' },
          h('span', {}, `Unpaid: ${b.event_title}, Row ${b.row} Seat ${b.seat_number}. `),
          h('a', { href: `/checkout/${b.id}/` }, 'Complete payment →'),
        )));
    } catch (e) { /* not essential */ }
  }

  async function loadList(root) {
    showPendingHolds();
    let tickets;
    try {
      tickets = await getAll('/api/tickets/');
    } catch (err) {
      root.replaceChildren(h('div', { class: 'state' },
        h('p', {}, err.message || 'Could not load your tickets.'),
        h('button', { class: 'btn btn-secondary', type: 'button', onclick: () => loadList(root) }, 'Try again')));
      return;
    }

    if (!tickets.length) {
      root.replaceChildren(h('div', { class: 'state' },
        h('p', {}, "You don't have any tickets yet."),
        h('a', { class: 'btn', href: '/events/' }, 'Find an event')));
      return;
    }

    const now = today();
    const upcoming = tickets.filter((t) => t.event_date >= now);
    // Most recent past events first.
    const past = tickets.filter((t) => t.event_date < now).reverse();

    const section = (title, list, isPast) => list.length
      ? h('section', { class: 'ticket-section' },
          h('h2', {}, `${title} (${list.length})`),
          h('div', { class: 'ticket-list' }, list.map((t) => ticketCard(t, isPast))))
      : null;

    root.replaceChildren(
      section('Upcoming', upcoming, false) ||
        h('p', { class: 'muted' }, 'No upcoming tickets. ', h('a', { href: '/events/' }, 'Find an event')),
      section('Past', past, true),
    );
  }

  /* ---------- Detail page ---------- */

  async function resend(button, note) {
    button.disabled = true;
    button.textContent = 'Sending…';
    try {
      const res = await api.post(`/api/tickets/${button.dataset.ticketId}/resend/`);
      note.className = 'alert alert-success';
      note.textContent = res.detail;
    } catch (err) {
      note.className = 'alert alert-error';
      note.textContent = err.message || 'Could not send the email.';
    }
    note.hidden = false;
    button.disabled = false;
    button.textContent = 'Email me this ticket';
  }

  async function loadDetail(root) {
    let ticket;
    try {
      ticket = await api.get(`/api/tickets/${root.dataset.ticketId}/`);
    } catch (err) {
      root.replaceChildren(h('div', { class: 'state' },
        h('p', {}, err.status === 404 ? 'Ticket not found.' : (err.message || 'Could not load this ticket.')),
        h('a', { class: 'btn btn-secondary', href: '/tickets/' }, 'Back to my tickets')));
      return;
    }

    const isPast = ticket.event_date < today();
    const usable = !ticket.is_used && !isPast;
    const note = h('div', { class: 'alert', role: 'status', hidden: true });
    const resendBtn = h('button', {
      class: 'btn btn-secondary btn-block', type: 'button', dataset: { ticketId: ticket.id },
      onclick: (e) => resend(e.currentTarget, note),
    }, 'Email me this ticket');

    root.replaceChildren(h('article', { class: 'ticket-pass' },
      h('header', { class: 'pass-head' },
        h('div', { class: 'pass-event' }, ticket.event_title),
        h('div', {}, `${fmt.date(ticket.event_date)} · ${fmt.time(ticket.event_time)}`),
        h('div', {}, ticket.venue),
      ),
      h('div', { class: `pass-qr${usable ? '' : ' is-void'}` },
        h('img', { src: ticket.qr_code, alt: `QR code for ticket ${ticket.id}`, width: 280, height: 280 }),
        usable ? null : h('div', { class: 'void-stamp' }, ticket.is_used ? 'USED' : 'EXPIRED'),
      ),
      h('p', { class: 'pass-status' },
        usable
          ? 'Show this code at the gate. Turn your screen brightness up for faster scanning.'
          : ticket.is_used ? `${usedAtText(ticket)}. This ticket can't be used again.` : 'This event has passed.'),
      h('dl', { class: 'pass-details' },
        h('div', {}, h('dt', {}, 'Row'), h('dd', {}, ticket.row)),
        h('div', {}, h('dt', {}, 'Seat'), h('dd', {}, ticket.seat_number)),
        h('div', {}, h('dt', {}, 'Category'), h('dd', {}, ticket.category)),
        h('div', {}, h('dt', {}, 'Ticket'), h('dd', {}, `#${ticket.id}`)),
      ),
      h('footer', { class: 'pass-foot' },
        note,
        usable ? resendBtn : null,
        h('a', { class: 'pass-link', href: `/events/${ticket.event}/` }, 'View event & seating plan'),
      ),
    ));
    document.title = `Ticket #${ticket.id} · KenyaSeats`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!auth.requireLogin()) return;
    const list = document.getElementById('ticket-list');
    const detail = document.getElementById('ticket-detail');
    if (list) loadList(list);
    if (detail) loadDetail(detail);
  });
})();
