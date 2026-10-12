/* Event list page: search, status filter and "load more" pagination. */
(function () {
  'use strict';
  const { api, h, fmt } = window.SB;

  let results, searchInput, statusSelect, loadMoreBtn;
  let nextUrl = null;
  let requestId = 0; // ignore responses that arrive after a newer search started

  function eventCard(event) {
    return h('a', { class: 'event-card', href: `/events/${event.id}/` },
      h('div', { class: 'event-date-strip' },
        h('span', {}, `${fmt.date(event.event_date)} · ${fmt.time(event.event_time)}`),
        event.status !== 'upcoming'
          ? h('span', { class: `badge badge-${event.status}` }, fmt.statusLabel(event.status))
          : null,
      ),
      h('div', { class: 'event-body' },
        h('h2', { class: 'event-title' }, event.title),
        h('div', { class: 'event-venue' }, `${event.venue_name}, ${event.venue_location}`),
        h('div', { class: 'event-foot' },
          event.price_from
            ? h('span', { class: 'price' }, `From ${fmt.kes(event.price_from)}`)
            : h('span', { class: 'muted' }, 'Prices TBA'),
          h('span', { class: 'btn btn-small' }, 'Pick seats'),
        ),
      ),
    );
  }

  function showState(...children) {
    results.replaceChildren(h('div', { class: 'state' }, ...children));
  }

  function render(data, append) {
    nextUrl = data.next;
    loadMoreBtn.hidden = !nextUrl;

    if (!append && data.results.length === 0) {
      const searching = searchInput.value.trim();
      showState(searching ? `No events match “${searching}”.` : 'No events to show right now. Check back soon.');
      return;
    }
    let grid = results.querySelector('.event-grid');
    if (!append || !grid) {
      grid = h('div', { class: 'event-grid' });
      results.replaceChildren(grid);
    }
    grid.append(...data.results.map(eventCard));
  }

  async function load(url, append = false) {
    const id = ++requestId;
    if (!append) showState(h('div', { class: 'spinner' }), 'Loading events…');
    loadMoreBtn.disabled = true;
    try {
      const data = await api.get(url);
      if (id === requestId) render(data, append);
    } catch (err) {
      if (id !== requestId) return;
      showState(
        h('p', {}, err.message || 'Could not load events.'),
        h('button', { class: 'btn btn-secondary', type: 'button', onclick: () => load(url, append) }, 'Try again'),
      );
    } finally {
      loadMoreBtn.disabled = false;
    }
  }

  function search() {
    const params = new URLSearchParams({ ordering: 'event_date' });
    if (statusSelect.value) params.set('status', statusSelect.value);
    if (searchInput.value.trim()) params.set('search', searchInput.value.trim());

    // Keep the filters in the address bar so refresh/back/share keep them.
    const pageParams = new URLSearchParams();
    if (searchInput.value.trim()) pageParams.set('q', searchInput.value.trim());
    if (statusSelect.value !== 'upcoming') pageParams.set('status', statusSelect.value);
    history.replaceState(null, '', pageParams.toString() ? `?${pageParams}` : location.pathname);

    load(`/api/events/?${params}`);
  }

  document.addEventListener('DOMContentLoaded', () => {
    results = document.getElementById('event-results');
    searchInput = document.getElementById('event-search');
    statusSelect = document.getElementById('event-status');
    loadMoreBtn = document.getElementById('load-more');

    const pageParams = new URLSearchParams(location.search);
    searchInput.value = pageParams.get('q') || '';
    if (pageParams.has('status')) statusSelect.value = pageParams.get('status');

    let debounce;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(search, 300);
    });
    statusSelect.addEventListener('change', search);
    loadMoreBtn.addEventListener('click', () => nextUrl && load(nextUrl, true));

    search();
  });
})();
