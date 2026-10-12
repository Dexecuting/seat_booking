/*
 * Interactive SVG seat map, exposed as SB.seatMap.
 *
 *   const map = SB.seatMap.create(container, seats, { onSelect(seat) {...} });
 *   map.update(seats);        // apply fresh statuses from /api/events/<id>/seats/
 *   map.select(seatId);       // preselect (e.g. from ?seat= in the URL)
 *   map.setStatus(id, 'held');
 *
 * Layout: a top-down view of one stand. The pitch runs along the top; row 1 is nearest the
 * pitch. Available seats are coloured by price category; held/booked seats are greyed out.
 * Keyboard: Tab into the map, arrow keys move between seats, Enter/Space selects.
 */
(function () {
  'use strict';
  const { h, fmt } = window.SB;

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const PALETTE = ['#b8860b', '#0a7d3b', '#2563eb', '#7c3aed', '#0f766e']; // by price, high -> low
  const SEAT = 18;       // seat square size
  const STEP = 22;       // seat pitch (size + gap)
  const LABEL = 30;      // room for row numbers on each side
  const PITCH_H = 64;
  const PITCH_GAP = 24;

  const STATUS_TEXT = { available: 'available', held: 'on hold', booked: 'booked' };

  /** Like SB.h but for SVG elements. */
  function svg(tag, attrs, ...children) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value !== null && value !== undefined && value !== false) el.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child !== null && child !== undefined) {
        el.append(child instanceof Node ? child : document.createTextNode(String(child)));
      }
    }
    return el;
  }

  /** Categories present in the seat list, most expensive first, each with a colour. */
  function categoriesOf(seats) {
    const byId = new Map();
    for (const seat of seats) {
      byId.set(seat.category_id, { id: seat.category_id, name: seat.category, price: Number(seat.price) });
    }
    return [...byId.values()]
      .sort((a, b) => b.price - a.price)
      .map((cat, i) => ({ ...cat, color: PALETTE[i % PALETTE.length] }));
  }

  function legend(categories) {
    const swatch = (cls, color) => h('span', { class: `swatch ${cls}`, style: color ? `background:${color}` : null });
    return h('div', { class: 'seat-legend' },
      categories.map((c) => h('span', { class: 'legend-item' }, swatch('', c.color), `${c.name} · ${fmt.kes(c.price)}`)),
      h('span', { class: 'legend-item' }, swatch('swatch-selected'), 'Your pick'),
      h('span', { class: 'legend-item' }, swatch('swatch-held'), 'On hold'),
      h('span', { class: 'legend-item' }, swatch('swatch-booked'), 'Booked'),
    );
  }

  function create(container, seatList, { onSelect = () => {} } = {}) {
    const categories = categoriesOf(seatList);
    const colorOf = new Map(categories.map((c) => [c.id, c.color]));

    // Group seats into rows (front row first), seats left to right.
    const rowMap = new Map();
    for (const seat of seatList) {
      if (!rowMap.has(seat.row)) rowMap.set(seat.row, []);
      rowMap.get(seat.row).push({ ...seat });
    }
    const rows = [...rowMap.keys()].sort((a, b) => a - b).map((r) => rowMap.get(r).sort((a, b) => a.number - b.number));
    const maxCols = Math.max(...rows.map((r) => r.length));
    const standWidth = maxCols * STEP;
    const width = LABEL * 2 + standWidth;
    const height = PITCH_H + PITCH_GAP + rows.length * STEP + 4;

    const seats = new Map(); // id -> seat (with layout info and element)
    let selectedId = null;
    let focusId = null;

    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      class: 'seat-map-svg',
      role: 'group',
      'aria-label': 'Seat map. Use arrow keys to move between seats and Enter to choose one.',
      // Keep seats tappable on phones: never shrink below ~16px per seat, scroll instead.
      style: `min-width:${Math.round(width * 0.75)}px`,
    });

    // Pitch along the top, with the halfway line at the centre of the stand.
    const pitchX = LABEL;
    const midX = LABEL + standWidth / 2;
    root.append(
      svg('rect', { class: 'pitch', x: pitchX, y: 0, width: standWidth, height: PITCH_H, rx: 6 }),
      svg('line', { class: 'pitch-line', x1: midX, y1: 0, x2: midX, y2: PITCH_H }),
      svg('circle', { class: 'pitch-line', cx: midX, cy: PITCH_H / 2, r: PITCH_H * 0.3 }),
      svg('text', { class: 'pitch-label', x: pitchX + 12, y: PITCH_H / 2 + 4 }, 'PITCH'),
    );

    rows.forEach((row, i) => {
      const y = PITCH_H + PITCH_GAP + i * STEP;
      const offset = ((maxCols - row.length) * STEP) / 2; // centre shorter rows
      const labelY = y + STEP / 2 + 4;
      root.append(
        svg('text', { class: 'row-label', x: LABEL / 2, y: labelY, 'text-anchor': 'middle' }, row[0].row),
        svg('text', { class: 'row-label', x: width - LABEL / 2, y: labelY, 'text-anchor': 'middle' }, row[0].row),
      );

      row.forEach((seat, j) => {
        const x = LABEL + offset + j * STEP;
        Object.assign(seat, {
          rowIndex: i,
          colIndex: j,
          cx: x + STEP / 2,
          // Position within the stand, 0..1, used for the view preview.
          fx: (x + STEP / 2 - LABEL) / standWidth,
          fy: rows.length > 1 ? i / (rows.length - 1) : 0,
          totalRows: rows.length,
          color: colorOf.get(seat.category_id),
        });
        seat.el = svg('rect', {
          class: 'seat',
          x: x + (STEP - SEAT) / 2,
          y: y + (STEP - SEAT) / 2,
          width: SEAT,
          height: SEAT,
          rx: 4,
          fill: seat.color,
          role: 'button',
          tabindex: -1,
          'data-id': seat.id,
        });
        root.append(seat.el);
        seats.set(seat.id, seat);
        applyStatus(seat);
      });
    });

    function label(seat) {
      const state = seat.id === selectedId ? 'selected' : STATUS_TEXT[seat.status] || seat.status;
      return `Row ${seat.row}, seat ${seat.number}, ${seat.category}, ${fmt.kes(seat.price)}, ${state}`;
    }

    function applyStatus(seat) {
      const el = seat.el;
      el.classList.toggle('held', seat.status === 'held');
      el.classList.toggle('booked', seat.status === 'booked');
      el.classList.toggle('selected', seat.id === selectedId);
      el.setAttribute('aria-disabled', String(seat.status !== 'available'));
      el.setAttribute('aria-pressed', String(seat.id === selectedId));
      el.setAttribute('aria-label', label(seat));
      // Native tooltip on hover.
      let title = el.querySelector('title');
      if (!title) { title = svg('title'); el.append(title); }
      title.textContent = label(seat);
    }

    function moveFocus(id, focus = true) {
      if (focusId !== null && seats.has(focusId)) seats.get(focusId).el.setAttribute('tabindex', '-1');
      focusId = id;
      const seat = seats.get(id);
      seat.el.setAttribute('tabindex', '0');
      if (focus) {
        seat.el.focus();
        seat.el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      }
    }

    function select(id, { notify = true } = {}) {
      const seat = seats.get(id);
      if (!seat || seat.status !== 'available') return false;
      const previous = selectedId;
      selectedId = id;
      if (previous !== null && seats.has(previous)) applyStatus(seats.get(previous));
      applyStatus(seat);
      moveFocus(id, false);
      if (notify) onSelect(seat);
      return true;
    }

    function clearSelection({ notify = true } = {}) {
      if (selectedId === null) return;
      const seat = seats.get(selectedId);
      selectedId = null;
      if (seat) applyStatus(seat);
      if (notify) onSelect(null);
    }

    function setStatus(id, status) {
      const seat = seats.get(id);
      if (!seat || seat.status === status) return;
      seat.status = status;
      if (id === selectedId && status !== 'available') {
        clearSelection();
      } else {
        applyStatus(seat);
      }
    }

    /** Apply a fresh seat list from the API. Returns true if the selected seat was taken. */
    function update(freshSeats) {
      const hadSelection = selectedId;
      for (const fresh of freshSeats) setStatus(fresh.id, fresh.status);
      return hadSelection !== null && selectedId === null;
    }

    // Mouse / touch
    root.addEventListener('click', (e) => {
      const el = e.target.closest('.seat');
      if (!el) return;
      const id = Number(el.dataset.id);
      if (id === selectedId) clearSelection();
      else select(id);
    });

    // Keyboard: arrows move between seats (including unavailable ones, so screen reader
    // users hear every seat); Enter/Space selects.
    root.addEventListener('keydown', (e) => {
      const el = e.target.closest('.seat');
      if (!el) return;
      const seat = seats.get(Number(el.dataset.id));
      let target = null;
      if (e.key === 'ArrowLeft') target = rows[seat.rowIndex][seat.colIndex - 1];
      else if (e.key === 'ArrowRight') target = rows[seat.rowIndex][seat.colIndex + 1];
      else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        const row = rows[seat.rowIndex + (e.key === 'ArrowUp' ? -1 : 1)];
        if (row) target = row.reduce((best, s) => (Math.abs(s.cx - seat.cx) < Math.abs(best.cx - seat.cx) ? s : best));
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (seat.id === selectedId) clearSelection();
        else select(seat.id);
        return;
      } else {
        return;
      }
      e.preventDefault();
      if (target) moveFocus(target.id);
    });

    // First Tab stop: the first available seat.
    const firstAvailable = seatList.find((s) => s.status === 'available') || seatList[0];
    if (firstAvailable) moveFocus(firstAvailable.id, false);

    container.replaceChildren(
      legend(categories),
      h('div', { class: 'seat-map-scroll' }, root),
    );

    return {
      update,
      select,
      setStatus,
      clear: clearSelection,
      get selected() { return selectedId === null ? null : seats.get(selectedId); },
    };
  }

  /**
   * "View from your seat": a mini top-down diagram with the sightline to the pitch, plus a
   * plain-language description derived from the seat's row depth and position along the stand.
   */
  function viewPreview(seat, categoryDescription) {
    const W = 200, PITCH_TOP = 8, PITCH_BOTTOM = 78, STAND_TOP = 88, STAND_BOTTOM = 128;
    const x = 10 + 180 * seat.fx;
    const y = STAND_TOP + 4 + (STAND_BOTTOM - STAND_TOP - 8) * seat.fy;

    const diagram = svg('svg', { viewBox: `0 0 ${W} 136`, class: 'view-preview', 'aria-hidden': 'true' },
      svg('rect', { class: 'pitch', x: 10, y: PITCH_TOP, width: 180, height: PITCH_BOTTOM - PITCH_TOP, rx: 4 }),
      svg('line', { class: 'pitch-line', x1: 100, y1: PITCH_TOP, x2: 100, y2: PITCH_BOTTOM }),
      svg('circle', { class: 'pitch-line', cx: 100, cy: (PITCH_TOP + PITCH_BOTTOM) / 2, r: 14 }),
      svg('rect', { class: 'pitch-line', x: 10, y: 28, width: 22, height: 30 }),
      svg('rect', { class: 'pitch-line', x: 168, y: 28, width: 22, height: 30 }),
      svg('rect', { class: 'stand', x: 10, y: STAND_TOP, width: 180, height: STAND_BOTTOM - STAND_TOP, rx: 4 }),
      svg('polygon', { class: 'sightline', points: `${x},${y} 10,${PITCH_TOP} 190,${PITCH_TOP}` }),
      svg('line', { class: 'sightline-centre', x1: x, y1: y, x2: 100, y2: (PITCH_TOP + PITCH_BOTTOM) / 2 }),
      svg('circle', { class: 'you', cx: x, cy: y, r: 5 }),
    );

    let depth;
    if (seat.fy < 0.34) depth = 'Front section: close to the action, at pitch level.';
    else if (seat.fy < 0.67) depth = 'Middle section: a good balance of closeness and overview.';
    else depth = 'Upper section: an elevated view of the whole pitch.';

    let position;
    const offCentre = seat.fx - 0.5;
    if (Math.abs(offCentre) < 0.15) position = 'Level with the halfway line, the best angle for following play.';
    else if (Math.abs(offCentre) < 0.35) position = `Between the halfway line and the ${offCentre < 0 ? 'left' : 'right'} goal.`;
    else position = `Near the ${offCentre < 0 ? 'left' : 'right'} goal end: close views of goalmouth action.`;

    return h('div', { class: 'view-box' },
      diagram,
      h('ul', { class: 'view-notes' },
        h('li', {}, position),
        h('li', {}, `${depth} (Row ${seat.row} of ${seat.totalRows})`),
        categoryDescription ? h('li', {}, categoryDescription) : null,
      ),
    );
  }

  window.SB.seatMap = { create, viewPreview };
})();
