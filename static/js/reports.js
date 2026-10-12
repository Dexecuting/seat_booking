/*
 * Organizer reports dashboard (/reports/), drawn with plain SVG and HTML.
 *
 *   KPI tiles          - revenue (hero), tickets sold, average price, refunds due
 *   Revenue per day    - single-series column chart, hover/keyboard tooltip, table view
 *   Revenue by category- horizontal bars with values at the tip
 *   Events             - table with occupancy meters (all-time)
 *   Seat popularity    - heatmap for one venue, 4-step blue scale + grey "never sold", table view
 *
 * Data: GET /api/reports/dashboard/?days=..&venue=.. ; the filter row re-scopes everything.
 */
(function () {
  'use strict';
  const { api, auth, h, fmt } = window.SB;

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const BLUE = '#2a78d6';
  // Heatmap: grey for "never sold", then four validated blue steps (light -> dark).
  const HEAT = ['#d6dae0', '#86b6ef', '#3987e5', '#1c5cab', '#0d366b'];
  const HEAT_LABELS = ['Never sold', 'Up to 25%', '26–50%', '51–75%', 'Over 75%'];
  const ROLES = ['organizer', 'admin'];

  let root, daysSelect, venueSelect;
  let requestId = 0;
  let venuesLoaded = false;
  let initialVenue = ''; // from ?venue= in the URL, applied once the venue list arrives

  /* ---------- Small helpers ---------- */

  function svg(tag, attrs, ...children) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
    }
    for (const c of children.flat()) {
      if (c !== null && c !== undefined) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }

  /** 1234 -> '1.2K', 15000 -> '15K', 2500000 -> '2.5M' (axis ticks). */
  function compact(n) {
    const abs = Math.abs(n);
    if (abs >= 1e6) return `${+(n / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `${+(n / 1e3).toFixed(1)}K`;
    return String(Math.round(n));
  }

  /** '2026-10-12' -> '12 Oct' */
  function shortDate(iso) {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('en-KE', { day: 'numeric', month: 'short' });
  }

  /** A "nice" axis maximum and step, about 4 gridlines. */
  function niceScale(max) {
    if (max <= 0) return { max: 1, step: 1 };
    const rough = max / 4;
    const mag = 10 ** Math.floor(Math.log10(rough));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= rough);
    return { max: Math.ceil(max / step) * step, step };
  }

  function card(title, subtitle, ...body) {
    return h('section', { class: 'report-card' },
      h('div', { class: 'report-card-head' },
        h('h2', {}, title),
        subtitle ? h('p', { class: 'muted' }, subtitle) : null,
      ),
      ...body,
    );
  }

  /** <details> with a plain table: every chart's accessible, tooltip-free twin. */
  function tableView(summary, headers, rows, alignRight = []) {
    return h('details', { class: 'table-view' },
      h('summary', {}, summary),
      h('div', { class: 'table-scroll' },
        h('table', { class: 'data-table' },
          h('thead', {}, h('tr', {}, headers.map((t, i) => h('th', { class: alignRight.includes(i) ? 'num' : null }, t)))),
          h('tbody', {}, rows.map((r) => h('tr', {}, r.map((c, i) => h('td', { class: alignRight.includes(i) ? 'num' : null }, c))))),
        ),
      ),
    );
  }

  /* ---------- Tooltip (one per chart) ---------- */

  function makeTooltip(container) {
    const tip = h('div', { class: 'chart-tooltip', role: 'status', hidden: true });
    container.append(tip);
    return {
      show(x, y, value, ...lines) {
        tip.replaceChildren(h('strong', {}, value), ...lines.map((l) => h('div', {}, l)));
        tip.hidden = false;
        const w = tip.offsetWidth;
        tip.style.left = `${Math.min(Math.max(x - w / 2, 4), container.scrollWidth - w - 4)}px`;
        tip.style.top = `${Math.max(y - tip.offsetHeight - 10, 4)}px`;
      },
      hide() { tip.hidden = true; },
    };
  }

  /* ---------- KPI tiles ---------- */

  function kpis(data) {
    const s = data.summary;
    const refunds = s.refunds_due.count;
    return h('div', { class: 'kpi-row' },
      h('div', { class: 'kpi kpi-hero' },
        h('div', { class: 'kpi-label' }, 'Revenue'),
        h('div', { class: 'kpi-value' }, fmt.kes(s.revenue)),
        h('div', { class: 'kpi-note' }, `Completed M-Pesa payments, ${periodText(data.period)}`),
      ),
      h('div', { class: 'kpi' },
        h('div', { class: 'kpi-label' }, 'Tickets sold'),
        h('div', { class: 'kpi-value' }, s.tickets_sold.toLocaleString('en-KE')),
      ),
      h('div', { class: 'kpi' },
        h('div', { class: 'kpi-label' }, 'Average ticket price'),
        h('div', { class: 'kpi-value' }, s.average_price ? fmt.kes(s.average_price) : '—'),
      ),
      h('div', { class: `kpi${refunds ? ' kpi-warning' : ''}` },
        h('div', { class: 'kpi-label' }, 'Refunds due'),
        refunds
          ? h('div', { class: 'kpi-value' }, h('span', { class: 'status-icon', 'aria-hidden': 'true' }, '⚠'), ` ${refunds}`)
          : h('div', { class: 'kpi-value' }, '0'),
        h('div', { class: 'kpi-note' }, refunds
          ? `${fmt.kes(s.refunds_due.amount)} paid after the seat hold ended`
          : 'No late payments to refund'),
      ),
    );
  }

  function periodText(p) {
    return p.days === 1 ? `on ${shortDate(p.start)}` : `${shortDate(p.start)} – ${shortDate(p.end)}`;
  }

  /* ---------- Revenue per day: column chart ---------- */

  /** Long periods are grouped by week so columns stay readable. */
  function bucket(daily) {
    if (daily.length <= 92) return daily.map((d) => ({ ...d, label: shortDate(d.date), revenue: Number(d.revenue) }));
    const weeks = [];
    for (let i = 0; i < daily.length; i += 7) {
      const chunk = daily.slice(i, i + 7);
      weeks.push({
        date: chunk[0].date,
        label: `Week of ${shortDate(chunk[0].date)}`,
        revenue: chunk.reduce((s, d) => s + Number(d.revenue), 0),
        tickets: chunk.reduce((s, d) => s + d.tickets, 0),
      });
    }
    return weeks;
  }

  function revenueChart(data) {
    const points = bucket(data.daily);
    const weekly = data.daily.length > 92;
    const total = points.reduce((s, p) => s + p.revenue, 0);

    const W = 720, H = 260, M = { top: 24, right: 12, bottom: 30, left: 52 };
    const plotW = W - M.left - M.right, plotH = H - M.top - M.bottom;
    const { max, step } = niceScale(Math.max(...points.map((p) => p.revenue)));
    const band = plotW / points.length;
    const barW = Math.max(1, Math.min(24, band * 0.7)); // <= 24px, the rest of the slot is air
    const y = (v) => M.top + plotH - (v / max) * plotH;

    const chart = svg('svg', {
      viewBox: `0 0 ${W} ${H}`, class: 'chart-svg', tabindex: 0, role: 'img',
      style: 'min-width:520px', // keep axis text readable on phones; the box scrolls instead
      'aria-label': `Revenue per ${weekly ? 'week' : 'day'}, ${periodText(data.period)}. Total ${fmt.kes(total)}. ` +
        'Use left and right arrow keys to read each value, or open the table below.',
    });

    // Gridlines + y ticks (hairline, solid, recessive)
    for (let v = 0; v <= max + 1e-9; v += step) {
      chart.append(
        svg('line', { class: v === 0 ? 'axis-line' : 'grid-line', x1: M.left, x2: W - M.right, y1: y(v), y2: y(v) }),
        svg('text', { class: 'tick', x: M.left - 8, y: y(v) + 4, 'text-anchor': 'end' }, compact(v)),
      );
    }

    // X labels: about six, evenly spaced
    const every = Math.max(1, Math.ceil(points.length / 6));
    points.forEach((p, i) => {
      if (i % every === 0) {
        chart.append(svg('text', { class: 'tick', x: M.left + band * (i + 0.5), y: H - 8, 'text-anchor': 'middle' },
          weekly ? shortDate(p.date) : p.label));
      }
    });

    // Columns: 4px rounded cap, square at the baseline
    const bars = points.map((p, i) => {
      const x = M.left + band * i + (band - barW) / 2;
      const top = y(p.revenue);
      const hgt = M.top + plotH - top;
      if (hgt <= 0) return null;
      const r = Math.min(4, barW / 2, hgt);
      const d = `M${x},${top + hgt} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${top + hgt} Z`;
      const bar = svg('path', { class: 'bar', d, fill: BLUE });
      chart.append(bar);
      return bar;
    });

    // Direct label: the single highest column only
    const peak = points.reduce((best, p, i) => (p.revenue > points[best].revenue ? i : best), 0);
    if (points[peak].revenue > 0) {
      chart.append(svg('text', { class: 'value-label', x: M.left + band * (peak + 0.5), y: y(points[peak].revenue) - 6, 'text-anchor': 'middle' },
        compact(points[peak].revenue)));
    }

    // Hover / keyboard layer: whole band is the hit target
    const wrap = h('div', { class: 'chart-wrap' }, chart);
    const tip = makeTooltip(wrap);
    let active = -1;
    function activate(i) {
      if (active >= 0 && bars[active]) bars[active].classList.remove('active');
      active = i;
      if (i < 0) { tip.hide(); return; }
      if (bars[i]) bars[i].classList.add('active');
      const p = points[i];
      const scale = chart.getBoundingClientRect().width / W;
      tip.show((M.left + band * (i + 0.5)) * scale, Math.min(y(p.revenue), M.top + plotH - 4) * scale,
        fmt.kes(p.revenue), p.label, `${p.tickets} ticket${p.tickets === 1 ? '' : 's'} sold`);
    }
    points.forEach((p, i) => {
      const hit = svg('rect', { class: 'hit', x: M.left + band * i, y: M.top, width: band, height: plotH });
      hit.addEventListener('pointerenter', () => activate(i));
      chart.append(hit);
    });
    chart.addEventListener('pointerleave', () => activate(-1));
    chart.addEventListener('blur', () => activate(-1));
    chart.addEventListener('focus', () => activate(active >= 0 ? active : points.length - 1));
    chart.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') activate(Math.max(0, active - 1));
      else if (e.key === 'ArrowRight') activate(Math.min(points.length - 1, active + 1));
      else if (e.key === 'Home') activate(0);
      else if (e.key === 'End') activate(points.length - 1);
      else return;
      e.preventDefault();
    });

    return card(
      `Revenue per ${weekly ? 'week' : 'day'}`,
      total > 0 ? `${fmt.kes(total)} in total, ${periodText(data.period)}` : 'No sales in this period yet.',
      wrap,
      tableView('Show as table', [weekly ? 'Week starting' : 'Date', 'Revenue', 'Tickets'],
        points.map((p) => [weekly ? shortDate(p.date) : fmt.date(p.date), fmt.kes(p.revenue), p.tickets]), [1, 2]),
    );
  }

  /* ---------- Revenue by category: horizontal bars ---------- */

  function categoryChart(data) {
    const rows = data.by_category;
    if (!rows.length) return card('Revenue by seat category', null, h('p', { class: 'muted' }, 'No sales in this period yet.'));
    const max = Math.max(...rows.map((r) => Number(r.revenue)), 1);
    return card('Revenue by seat category', `Which price levels bring in the money, ${periodText(data.period)}`,
      h('div', { class: 'hbar-list' }, rows.map((r) =>
        h('div', { class: 'hbar-row' },
          h('div', { class: 'hbar-label' }, h('strong', {}, r.category), h('span', { class: 'muted' }, ` · ${r.tickets} tickets`)),
          h('div', { class: 'hbar-track' },
            h('div', { class: 'hbar', style: `width:${Math.max(0.5, (Number(r.revenue) / max) * 75)}%` }),
            h('span', { class: 'hbar-value' }, fmt.kes(r.revenue)),
          ),
        ))),
    );
  }

  /* ---------- Events table ---------- */

  function eventsTable(data) {
    if (!data.events.length) {
      return card('Events', null, h('p', { class: 'muted' }, 'No events yet. ',
        h('a', { href: '/organizer/events/new/' }, 'Create an event')));
    }
    return card('Events', 'All-time sales and attendance per event (not limited to the sales period)',
      h('div', { class: 'table-scroll' },
        h('table', { class: 'data-table events-table' },
          h('thead', {}, h('tr', {},
            h('th', {}, 'Event'), h('th', {}, 'Date'), h('th', {}, 'Occupancy'),
            h('th', { class: 'num' }, 'Sold'), h('th', { class: 'num' }, 'Checked in'), h('th', { class: 'num' }, 'Revenue'))),
          h('tbody', {}, data.events.map((e) => h('tr', {},
            h('td', {},
              h('a', { href: `/events/${e.id}/` }, e.title),
              h('div', { class: 'muted small' }, e.venue, e.status !== 'upcoming' ? ` · ${fmt.statusLabel(e.status)}` : '')),
            h('td', { class: 'nowrap' }, fmt.date(e.date)),
            h('td', {},
              h('div', { class: 'meter', role: 'meter', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': e.occupancy,
                'aria-label': `${e.occupancy}% of seats sold` },
                h('div', { class: 'meter-fill', style: `width:${e.occupancy}%` })),
              h('div', { class: 'small' }, `${e.occupancy}%`, e.held ? h('span', { class: 'muted' }, ` · ${e.held} on hold`) : null)),
            h('td', { class: 'num' }, `${e.sold.toLocaleString('en-KE')} / ${e.capacity.toLocaleString('en-KE')}`),
            h('td', { class: 'num' }, e.sold ? `${e.checked_in} (${Math.round((e.checked_in / e.sold) * 100)}%)` : '—'),
            h('td', { class: 'num nowrap' }, fmt.kes(e.revenue)),
          ))),
        ),
      ),
    );
  }

  /* ---------- Seat popularity heatmap ---------- */

  function heatBin(rate) {
    if (rate <= 0) return 0;
    if (rate <= 0.25) return 1;
    if (rate <= 0.5) return 2;
    if (rate <= 0.75) return 3;
    return 4;
  }

  function heatmap(data) {
    const title = 'Seat popularity';
    if (!data.heatmap) {
      return card(title, null, h('p', { class: 'muted' }, 'Choose a venue in the filters above to see which seats sell best.'));
    }
    const hm = data.heatmap;
    if (!hm.events_with_sales) {
      return card(`${title} · ${hm.venue.name}`, null, h('p', { class: 'muted' }, 'No seats sold at this venue in this period.'));
    }

    const rowsMap = new Map();
    for (const s of hm.seats) {
      if (!rowsMap.has(s.row)) rowsMap.set(s.row, []);
      rowsMap.get(s.row).push(s);
    }
    const rows = [...rowsMap.keys()].sort((a, b) => a - b).map((r) => rowsMap.get(r).sort((a, b) => a.number - b.number));
    const maxCols = Math.max(...rows.map((r) => r.length));
    const CELL = 16, STEP = 18, LABEL = 26, PITCH = 30, GAP = 14;
    const W = LABEL * 2 + maxCols * STEP, H = PITCH + GAP + rows.length * STEP;

    const chart = svg('svg', { viewBox: `0 0 ${W} ${H}`, class: 'heatmap-svg', role: 'img',
      'aria-label': `Seat popularity heatmap for ${hm.venue.name}. Open the table below for row-by-row figures.`,
      style: `min-width:${Math.round(W * 0.7)}px` });
    chart.append(
      svg('rect', { class: 'hm-pitch', x: LABEL, y: 0, width: maxCols * STEP, height: PITCH, rx: 4 }),
      svg('text', { class: 'hm-pitch-label', x: LABEL + 10, y: PITCH / 2 + 4 }, 'PITCH'),
    );

    const wrap = h('div', { class: 'chart-wrap heatmap-scroll' }, chart);
    const tip = makeTooltip(wrap);

    rows.forEach((row, i) => {
      const yy = PITCH + GAP + i * STEP;
      const offset = ((maxCols - row.length) * STEP) / 2;
      chart.append(svg('text', { class: 'tick', x: LABEL / 2, y: yy + CELL - 3, 'text-anchor': 'middle' }, row[0].row));
      row.forEach((s, j) => {
        const x = LABEL + offset + j * STEP;
        const cell = svg('rect', { class: 'hm-cell', x, y: yy, width: CELL, height: CELL, rx: 3, fill: HEAT[heatBin(s.rate)] });
        cell.addEventListener('pointerenter', () => {
          cell.classList.add('active');
          const scale = wrap.querySelector('svg').getBoundingClientRect().width / W;
          tip.show((x + CELL / 2) * scale, yy * scale,
            `${Math.round(s.rate * 100)}%`, `Row ${s.row}, Seat ${s.number} · ${s.category}`,
            `Sold for ${s.sold} of ${hm.events_with_sales} match${hm.events_with_sales === 1 ? '' : 'es'}`);
        });
        cell.addEventListener('pointerleave', () => { cell.classList.remove('active'); tip.hide(); });
        chart.append(cell);
      });
    });

    const legend = h('div', { class: 'heat-legend', 'aria-label': 'Colour scale' },
      HEAT.map((c, i) => h('span', { class: 'legend-item' }, h('span', { class: 'swatch', style: `background:${c}` }), HEAT_LABELS[i])));

    const rowTable = rows.map((row) => {
      const avg = row.reduce((s, x) => s + x.rate, 0) / row.length;
      const best = row.reduce((b, x) => (x.rate > b.rate ? x : b), row[0]);
      return [`Row ${row[0].row}`, row[0].category, `${Math.round(avg * 100)}%`,
        best.rate > 0 ? `Seat ${best.number} (${Math.round(best.rate * 100)}%)` : '—'];
    });

    return card(`${title} · ${hm.venue.name}`,
      `How often each seat sold across the ${hm.events_with_sales} match${hm.events_with_sales === 1 ? '' : 'es'} at this venue with sales ${periodText(data.period)}`,
      legend, wrap,
      tableView('Show row-by-row table', ['Row', 'Category', 'Average sold', 'Most popular seat'], rowTable, [2]),
    );
  }

  /* ---------- Page ---------- */

  async function load() {
    const id = ++requestId;
    const params = new URLSearchParams({ days: daysSelect.value });
    const venue = venuesLoaded ? venueSelect.value : initialVenue;
    if (venue) params.set('venue', venue);
    history.replaceState(null, '', `?${params}`);
    root.classList.add('loading'); // keep the previous render, dimmed - no flash

    let data;
    try {
      data = await api.get(`/api/reports/dashboard/?${params}`);
    } catch (err) {
      if (id !== requestId) return;
      root.classList.remove('loading');
      if (err.status === 403) {
        document.getElementById('reports-denied').hidden = false;
        document.getElementById('report-filters').hidden = true;
        root.replaceChildren();
        return;
      }
      root.replaceChildren(h('div', { class: 'state' }, h('p', {}, err.message || 'Could not load reports.'),
        h('button', { class: 'btn btn-secondary', type: 'button', onclick: load }, 'Try again')));
      return;
    }
    if (id !== requestId) return;

    // Venue options (first load only), keeping the current choice.
    if (!venuesLoaded) {
      for (const v of data.venues) venueSelect.append(h('option', { value: v.id }, v.name));
      venueSelect.value = data.venue ? String(data.venue.id) : '';
      venuesLoaded = true;
    }
    document.getElementById('filter-note').textContent =
      `${periodText(data.period)} · ${data.scope === 'mine' ? 'your events only' : 'all organizers’ events'}`;

    root.replaceChildren(
      kpis(data),
      h('div', { class: 'report-grid' }, revenueChart(data), categoryChart(data)),
      heatmap(data),
      eventsTable(data),
    );
    root.classList.remove('loading');
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (!auth.requireLogin()) return;
    root = document.getElementById('report');
    daysSelect = document.getElementById('filter-days');
    venueSelect = document.getElementById('filter-venue');

    if (!ROLES.includes(auth.user().role)) {
      document.getElementById('reports-denied').hidden = false;
      document.getElementById('report-filters').hidden = true;
      root.replaceChildren();
      return;
    }

    const params = new URLSearchParams(location.search);
    if (params.get('days') && daysSelect.querySelector(`option[value="${CSS.escape(params.get('days'))}"]`)) {
      daysSelect.value = params.get('days');
    }
    initialVenue = params.get('venue') || '';

    daysSelect.addEventListener('change', load);
    venueSelect.addEventListener('change', load);
    document.getElementById('report-filters').addEventListener('submit', (e) => e.preventDefault());
    load();
  });
})();
