/*
 * Gate scanner for gate staff: reads ticket QR codes with the camera (or typed codes),
 * checks them with POST /api/gates/scan/ and shows a full-screen green/red result.
 *
 * QR decoding uses the browser's BarcodeDetector where available (Android Chrome), otherwise
 * the bundled jsQR library (iPhone, desktop). The camera only works on HTTPS or localhost.
 */
(function () {
  'use strict';
  const { api, auth, h, fmt } = window.SB;

  const STAFF_ROLES = ['gate_staff', 'organizer', 'admin'];
  const SCAN_INTERVAL_MS = 200;
  const SAME_CODE_COOLDOWN_MS = 4000;   // ignore the same QR held in front of the camera
  const AUTO_DISMISS_ALLOWED_MS = 2500; // denied results stay until staff tap "Next fan"
  const EVENT_KEY = 'sb_gate_event';

  let video, stream = null, detector = null, scanTimer = null;
  let canvas, ctx;
  let busy = false;            // a scan is being checked or a result is on screen
  let lastCode = '', lastCodeAt = 0;
  let dismissTimer = null;
  const counts = { allowed: 0, denied: 0 };

  /* ---------- Feedback: sound + vibration ---------- */

  let audio = null;
  function beep(ok) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = ok ? 'sine' : 'square';
      osc.frequency.value = ok ? 880 : 220;
      gain.gain.value = 0.15;
      osc.connect(gain).connect(audio.destination);
      osc.start();
      osc.stop(audio.currentTime + (ok ? 0.15 : 0.5));
    } catch (e) { /* sound is optional */ }
    if (navigator.vibrate) navigator.vibrate(ok ? 80 : [200, 100, 200]);
  }

  /* ---------- Result overlay ---------- */

  function showResult(kind, title, reason, ticket) {
    const overlay = document.getElementById('scan-result');
    overlay.className = `scan-result result-${kind}`;
    document.getElementById('result-icon').textContent = kind === 'allowed' ? '✓' : kind === 'denied' ? '✗' : '!';
    document.getElementById('result-title').textContent = title;
    document.getElementById('result-reason').textContent = reason;
    document.getElementById('result-ticket').replaceChildren(...(ticket ? [
      h('div', { class: 'result-seat' }, `Row ${ticket.row} · Seat ${ticket.seat_number}`),
      h('div', {}, `${ticket.category} · ${ticket.holder}`),
      h('div', { class: 'result-event' }, ticket.event),
    ] : []));
    overlay.hidden = false;
    document.getElementById('result-next').focus();

    clearTimeout(dismissTimer);
    if (kind === 'allowed') dismissTimer = setTimeout(dismissResult, AUTO_DISMISS_ALLOWED_MS);
  }

  function dismissResult() {
    clearTimeout(dismissTimer);
    document.getElementById('scan-result').hidden = true;
    busy = false;
    const manual = document.getElementById('manual-token');
    if (!stream) manual.focus();
  }

  function addRecent(kind, text) {
    const list = document.getElementById('recent-list');
    if (list.querySelector('.muted')) list.replaceChildren();
    const time = new Date().toLocaleTimeString('en-KE', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    list.prepend(h('li', { class: `recent-${kind}` }, h('span', { class: 'recent-time' }, time), text));
    while (list.children.length > 8) list.lastChild.remove();
  }

  function updateCounts() {
    document.getElementById('count-allowed').textContent = counts.allowed;
    document.getElementById('count-denied').textContent = counts.denied;
  }

  /* ---------- Checking a code ---------- */

  async function check(token) {
    token = (token || '').trim();
    if (!token || busy) return;
    busy = true;

    const eventId = document.getElementById('gate-event').value;
    let result;
    try {
      result = await api.post('/api/gates/scan/', eventId ? { token, event: Number(eventId) } : { token });
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        busy = false;
        stopCamera();
        document.getElementById('gate-denied-role').hidden = false;
        return;
      }
      // Network or server trouble is not a "denied": the fan's ticket may be fine.
      beep(false);
      showResult('error', 'Not checked', 'Could not reach the server. Check the connection and scan again.', null);
      return;
    }

    beep(result.allowed);
    const t = result.ticket;
    if (result.allowed) {
      counts.allowed += 1;
      showResult('allowed', 'ALLOWED', 'Enjoy the match!', t);
      addRecent('allowed', `Admitted · Row ${t.row} Seat ${t.seat_number} · ${t.holder}`);
    } else {
      counts.denied += 1;
      showResult('denied', 'DENIED', result.reason, t);
      addRecent('denied', `Denied · ${result.reason}`);
    }
    updateCounts();
  }

  /* ---------- Camera ---------- */

  function loadJsQR() {
    if (window.jsQR) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = document.getElementById('gate-script').dataset.jsqrSrc;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Could not load the QR reader.'));
      document.head.append(s);
    });
  }

  async function makeDetector() {
    if ('BarcodeDetector' in window) {
      try {
        const formats = await window.BarcodeDetector.getSupportedFormats();
        if (formats.includes('qr_code')) {
          const native = new window.BarcodeDetector({ formats: ['qr_code'] });
          return async (source) => {
            const codes = await native.detect(source);
            return codes.length ? codes[0].rawValue : null;
          };
        }
      } catch (e) { /* fall back to jsQR */ }
    }
    await loadJsQR();
    canvas = document.createElement('canvas');
    ctx = canvas.getContext('2d', { willReadFrequently: true });
    return async (source) => {
      const w = source.videoWidth, hgt = source.videoHeight;
      if (!w || !hgt) return null;
      // Decode a downscaled frame: much faster, and QR codes on phone screens are large.
      const scale = Math.min(1, 640 / Math.max(w, hgt));
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(hgt * scale);
      ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
      const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = window.jsQR(image.data, image.width, image.height, { inversionAttempts: 'dontInvert' });
      return code ? code.data : null;
    };
  }

  function cameraError(message) {
    const box = document.getElementById('camera-error');
    box.textContent = message;
    box.hidden = !message;
  }

  async function startCamera() {
    cameraError('');
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      cameraError('The camera only works over HTTPS (or on localhost). Open this page through your HTTPS/ngrok address, or type the ticket code below.');
      return;
    }
    const startBtn = document.getElementById('camera-start');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting…';
    try {
      detector = detector || await makeDetector();
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
    } catch (err) {
      startBtn.disabled = false;
      startBtn.textContent = 'Start camera';
      cameraError(err.name === 'NotAllowedError'
        ? 'Camera permission was refused. Allow camera access in your browser settings, or type the ticket code below.'
        : `Could not start the camera (${err.message || err.name}). You can type the ticket code below.`);
      return;
    }

    video.srcObject = stream;
    await video.play().catch(() => {});
    video.hidden = false;
    document.getElementById('camera-frame').hidden = false;
    document.getElementById('camera-idle').hidden = true;
    document.getElementById('camera-stop').hidden = false;
    startBtn.disabled = false;
    startBtn.textContent = 'Start camera';
    scanLoop();
  }

  function scanLoop() {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(async () => {
      if (!stream) return;
      if (!busy && video.readyState >= 2) {
        try {
          const code = await detector(video);
          const now = Date.now();
          if (code && !(code === lastCode && now - lastCodeAt < SAME_CODE_COOLDOWN_MS)) {
            lastCode = code;
            lastCodeAt = now;
            check(code);
          }
        } catch (e) { /* bad frame - keep going */ }
      }
      scanLoop();
    }, SCAN_INTERVAL_MS);
  }

  function stopCamera() {
    clearTimeout(scanTimer);
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
    video.hidden = true;
    video.srcObject = null;
    document.getElementById('camera-frame').hidden = true;
    document.getElementById('camera-idle').hidden = false;
    document.getElementById('camera-stop').hidden = true;
  }

  /* ---------- Event picker ---------- */

  async function loadEvents() {
    const select = document.getElementById('gate-event');
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    try {
      const data = await api.get(`/api/events/?event_date=${today}&ordering=event_time`);
      const todays = data.results.filter((e) => e.status !== 'cancelled');
      for (const e of todays) {
        select.append(h('option', { value: e.id }, `${e.title} · ${fmt.time(e.event_time)} · ${e.venue_name}`));
      }
      if (!todays.length) {
        select.firstElementChild.textContent = 'No events today';
      }
    } catch (e) { /* "Any event today" still works */ }

    try {
      const saved = localStorage.getItem(EVENT_KEY);
      if (saved && select.querySelector(`option[value="${CSS.escape(saved)}"]`)) select.value = saved;
    } catch (e) { /* ignore */ }
    select.addEventListener('change', () => {
      try { localStorage.setItem(EVENT_KEY, select.value); } catch (e) { /* ignore */ }
    });
  }

  /* ---------- Start ---------- */

  document.addEventListener('DOMContentLoaded', () => {
    if (!auth.requireLogin()) return;
    const user = auth.user();
    if (!STAFF_ROLES.includes(user.role)) {
      document.getElementById('gate-denied-role').hidden = false;
      document.querySelectorAll('.scanner-panel, .manual-entry, .gate-event, .recent').forEach((el) => { el.hidden = true; });
      return;
    }

    video = document.getElementById('camera-video');
    loadEvents();

    document.getElementById('camera-start').addEventListener('click', startCamera);
    document.getElementById('camera-stop').addEventListener('click', stopCamera);
    document.getElementById('result-next').addEventListener('click', dismissResult);
    document.getElementById('manual-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const input = document.getElementById('manual-token');
      check(input.value);
      input.value = '';
    });
    // Keyboard-wedge USB/Bluetooth scanners type the code and press Enter into the focused box.
    document.getElementById('manual-token').focus();

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !document.getElementById('scan-result').hidden) dismissResult();
    });
    document.addEventListener('visibilitychange', () => { if (document.hidden) stopCamera(); });
  });
})();
