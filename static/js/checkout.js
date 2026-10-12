/*
 * Checkout: shows the held seat with a countdown, sends the M-Pesa payment request, waits
 * for the result and then shows the ticket.
 *
 * States: pay form -> waiting for M-Pesa -> success (ticket) | failed (back to pay form)
 *         or: hold expired / booking cancelled.
 */
(function () {
  'use strict';
  const { api, auth, h, fmt } = window.SB;

  const POLL_MS = 3000;
  const ASK_MPESA_EVERY = 4;        // every 4th poll asks Daraja directly (works without a callback URL)
  const GIVE_UP_AFTER_POLLS = 50;   // ~2.5 minutes
  const MIN_SECONDS_TO_PAY = 45;    // don't start a payment that can't finish before the hold ends

  let root, bookingId, booking;
  let deadline = 0;
  let countdownTimer = null;
  let pollTimer = null;

  /* ---------- Helpers ---------- */

  function secondsLeft() {
    return Math.max(0, Math.round((deadline - Date.now()) / 1000));
  }

  function mmss(total) {
    const m = Math.floor(total / 60);
    const s = String(total % 60).padStart(2, '0');
    return `${m}:${s}`;
  }

  /** '254712345678' -> '0712345678' for display in the phone box. */
  function localPhone(phone) {
    return phone && phone.startsWith('254') ? '0' + phone.slice(3) : (phone || '');
  }

  function summary() {
    return h('div', { class: 'checkout-summary' },
      h('div', { class: 'summary-event' }, booking.event_title),
      h('div', { class: 'muted' },
        `${fmt.date(booking.event_date)} · ${fmt.time(booking.event_time)} · ${booking.venue}`),
      h('dl', { class: 'summary-grid' },
        h('div', {}, h('dt', {}, 'Seat'), h('dd', {}, `Row ${booking.row}, Seat ${booking.seat_number}`)),
        h('div', {}, h('dt', {}, 'Category'), h('dd', {}, booking.category)),
        h('div', {}, h('dt', {}, 'Total'), h('dd', { class: 'price' }, fmt.kes(booking.price))),
      ),
    );
  }

  function countdown() {
    return h('div', { class: 'countdown', id: 'countdown', role: 'timer' },
      h('span', {}, 'Seat held for'),
      h('strong', { id: 'countdown-time' }, mmss(secondsLeft())),
    );
  }

  function card(...children) {
    root.replaceChildren(h('div', { class: 'checkout-card' }, ...children));
  }

  function startCountdown(onExpire) {
    clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      const left = secondsLeft();
      const el = document.getElementById('countdown-time');
      if (el) {
        el.textContent = mmss(left);
        document.getElementById('countdown').classList.toggle('urgent', left <= 60);
      }
      const payBtn = document.getElementById('pay-btn');
      if (payBtn && left < MIN_SECONDS_TO_PAY) {
        payBtn.disabled = true;
        document.getElementById('pay-hint').textContent =
          'Not enough time left to complete an M-Pesa payment. Please pick your seat again.';
      }
      if (left === 0) {
        clearInterval(countdownTimer);
        if (onExpire) onExpire();
      }
    }, 1000);
  }

  /* ---------- States ---------- */

  async function showPayForm(errorText) {
    let phone = '';
    try { phone = localPhone((await api.get('/api/auth/me/')).phone); } catch (e) { /* type it in */ }

    const form = h('form', { class: 'pay-form', novalidate: true },
      h('div', { class: 'field' },
        h('label', { for: 'phone' }, 'M-Pesa phone number'),
        h('input', {
          id: 'phone', name: 'phone', type: 'tel', inputmode: 'tel', autocomplete: 'tel',
          placeholder: '0712 345 678', value: phone, required: true,
        }),
        h('div', { class: 'field-error', id: 'phone-error' }),
      ),
      h('button', { class: 'btn btn-block', id: 'pay-btn', type: 'submit' }, `Pay ${fmt.kes(booking.price)} with M-Pesa`),
      h('p', { class: 'muted pay-hint', id: 'pay-hint' }, 'You will get a prompt on your phone to enter your M-Pesa PIN.'),
    );
    form.addEventListener('submit', (e) => { e.preventDefault(); pay(form); });

    card(
      h('h1', {}, 'Complete your booking'),
      countdown(),
      errorText ? h('div', { class: 'alert alert-error', role: 'alert' }, errorText) : null,
      summary(),
      form,
      h('button', { class: 'link-btn release-btn', type: 'button', onclick: release }, 'Cancel and choose another seat'),
    );
    startCountdown(showExpired);
  }

  async function pay(form) {
    const button = form.querySelector('#pay-btn');
    const errorSlot = form.querySelector('#phone-error');
    const phone = form.elements.phone.value.trim();
    errorSlot.textContent = '';
    if (!phone) {
      errorSlot.textContent = 'Enter the M-Pesa number to charge.';
      form.elements.phone.focus();
      return;
    }
    button.disabled = true;
    button.textContent = 'Sending request…';
    try {
      const payment = await api.post('/api/payments/', { booking: booking.id, phone });
      showWaiting(payment);
    } catch (err) {
      button.disabled = false;
      button.textContent = `Pay ${fmt.kes(booking.price)} with M-Pesa`;
      if (err.data && err.data.phone) {
        errorSlot.textContent = [].concat(err.data.phone).join(' ');
        form.elements.phone.focus();
      } else {
        showPayForm(err.message || 'Could not start the payment. Please try again.');
      }
    }
  }

  function showWaiting(payment) {
    card(
      h('h1', {}, 'Check your phone'),
      countdown(),
      h('div', { class: 'waiting' },
        h('div', { class: 'spinner' }),
        h('p', {}, `We sent an M-Pesa request for ${fmt.kes(payment.amount)} to ${localPhone(payment.phone)}.`),
        h('p', { class: 'muted' }, 'Enter your M-Pesa PIN on your phone. This page updates automatically.'),
      ),
      summary(),
    );
    startCountdown(null); // keep waiting even if the timer runs out; the result decides
    poll(payment.id, 1);
  }

  function poll(paymentId, attempt) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(async () => {
      let payment;
      try {
        payment = attempt % ASK_MPESA_EVERY === 0
          ? await api.post(`/api/payments/${paymentId}/refresh/`)
          : await api.get(`/api/payments/${paymentId}/`);
      } catch (e) {
        poll(paymentId, attempt + 1); // network hiccup - keep trying
        return;
      }

      if (payment.status === 'completed') return showSuccess();
      if (payment.status === 'failed') {
        booking = await api.get(`/api/bookings/${bookingId}/`).catch(() => booking);
        if (booking.status !== 'pending') return showClosed();
        return showPayForm(`Payment was not completed: ${payment.result_desc || 'cancelled or timed out'}. You can try again.`);
      }
      if (payment.status === 'refund_due') return showRefundDue();

      if (attempt >= GIVE_UP_AFTER_POLLS) return showStillWaiting(paymentId);
      poll(paymentId, attempt + 1);
    }, POLL_MS);
  }

  function showStillWaiting(paymentId) {
    card(
      h('h1', {}, 'Still waiting for M-Pesa'),
      h('p', {}, "We haven't received confirmation of your payment yet. If you entered your PIN, it may take a moment."),
      h('button', { class: 'btn btn-block', type: 'button', onclick: () => {
        card(h('div', { class: 'state' }, h('div', { class: 'spinner' }), 'Checking with M-Pesa…'));
        poll(paymentId, ASK_MPESA_EVERY - 1); // next poll asks Daraja directly
      } }, 'Check again'),
      summary(),
    );
  }

  async function showSuccess() {
    clearInterval(countdownTimer);
    card(h('div', { class: 'state' }, h('div', { class: 'spinner' }), 'Payment received! Loading your ticket…'));

    let ticket = null;
    try {
      const list = await api.get(`/api/tickets/?booking=${bookingId}`);
      if (list.results.length) ticket = await api.get(`/api/tickets/${list.results[0].id}/`);
    } catch (e) { /* show confirmation without QR */ }

    card(
      h('div', { class: 'success-head' },
        h('div', { class: 'success-icon', 'aria-hidden': 'true' }, '✓'),
        h('h1', {}, 'You\'re going!'),
        h('p', { class: 'muted' }, 'Your seat is confirmed. Show this QR code at the gate.'),
      ),
      ticket
        ? h('figure', { class: 'ticket-qr' },
            h('img', { src: ticket.qr_code, alt: `QR code for ticket ${ticket.id}`, width: 240, height: 240 }),
            h('figcaption', { class: 'muted' }, `Ticket #${ticket.id} · also sent to your email`))
        : h('div', { class: 'alert alert-info' }, 'Your ticket is being prepared and will be emailed to you.'),
      summary(),
      h('a', { class: 'btn btn-secondary btn-block', href: '/events/' }, 'Browse more events'),
    );
  }

  function showRefundDue() {
    clearInterval(countdownTimer);
    card(
      h('h1', {}, 'Payment received too late'),
      h('div', { class: 'alert alert-error' },
        'Your M-Pesa payment arrived after your seat hold had ended, so the seat could not be confirmed. ' +
        'Your money will be refunded. Please contact the organiser if you have questions.'),
      summary(),
      h('a', { class: 'btn btn-block', href: `/events/${booking.event}/` }, 'Choose another seat'),
    );
  }

  function showExpired() {
    clearInterval(countdownTimer);
    card(
      h('h1', {}, 'Your hold has ended'),
      h('p', {}, 'The 10-minute hold on this seat ran out, so it has been released for other fans.'),
      summary(),
      h('a', { class: 'btn btn-block', href: `/events/${booking.event}/` }, 'Pick a seat again'),
    );
  }

  function showClosed() {
    if (booking.status === 'expired') return showExpired();
    clearInterval(countdownTimer);
    card(
      h('h1', {}, 'This booking was cancelled'),
      summary(),
      h('a', { class: 'btn btn-block', href: `/events/${booking.event}/` }, 'Pick a seat'),
    );
  }

  async function release() {
    try {
      await api.del(`/api/bookings/${bookingId}/`);
    } catch (err) {
      return showPayForm(err.message || 'Could not cancel this booking.');
    }
    location.href = `/events/${booking.event}/`;
  }

  /* ---------- Start ---------- */

  async function load() {
    try {
      booking = await api.get(`/api/bookings/${bookingId}/`);
    } catch (err) {
      card(
        h('h1', {}, err.status === 404 ? 'Booking not found' : 'Something went wrong'),
        h('p', {}, err.status === 404 ? 'This booking does not exist or belongs to another account.' : err.message),
        h('a', { class: 'btn btn-secondary', href: '/events/' }, 'Back to events'),
      );
      return;
    }

    deadline = Date.now() + (booking.hold_seconds_remaining || 0) * 1000;

    if (booking.status === 'confirmed') return showSuccess();
    if (booking.status !== 'pending') return showClosed();

    // Came back to the page while a payment was in progress? Resume waiting for it.
    try {
      const pending = await api.get(`/api/payments/?booking=${bookingId}&status=pending`);
      if (pending.results.length) return showWaiting(pending.results[0]);
    } catch (e) { /* fall through to the form */ }

    showPayForm();
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!auth.requireLogin()) return;
    root = document.getElementById('checkout');
    bookingId = root.dataset.bookingId;
    load();
  });
})();
