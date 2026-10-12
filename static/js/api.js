/*
 * Shared frontend helpers, exposed as window.SB:
 *   SB.api    - fetch wrapper for /api/ that adds the JWT and refreshes it when it expires
 *   SB.auth   - login / register / logout / current user
 *   SB.h      - safe element builder (always uses textContent, never innerHTML)
 *   SB.fmt    - KES, date and time formatting
 */
(function () {
  'use strict';

  const ACCESS_KEY = 'sb_access';
  const REFRESH_KEY = 'sb_refresh';

  // localStorage can throw (private browsing, blocked storage) - never let that break a page.
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* ignore */ } },
    remove(key) { try { localStorage.removeItem(key); } catch (e) { /* ignore */ } },
  };

  function setTokens(access, refresh) {
    store.set(ACCESS_KEY, access);
    if (refresh) store.set(REFRESH_KEY, refresh);
  }

  function clearTokens() {
    store.remove(ACCESS_KEY);
    store.remove(REFRESH_KEY);
  }

  /* ---------- API ---------- */

  class ApiError extends Error {
    constructor(status, data) {
      super(messageFrom(data) || `Request failed (${status}).`);
      this.status = status;
      this.data = (data && typeof data === 'object') ? data : {};
    }
  }

  function messageFrom(data) {
    if (!data) return '';
    if (typeof data === 'string') return data.length < 200 ? data : '';
    if (data.detail) return String(data.detail);
    if (data.non_field_errors) return data.non_field_errors.join(' ');
    return '';
  }

  // Several requests can hit an expired token at once; they share one refresh call.
  let refreshing = null;

  function refreshAccessToken() {
    const refresh = store.get(REFRESH_KEY);
    if (!refresh) return Promise.resolve(false);
    if (!refreshing) {
      refreshing = fetch('/api/auth/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      })
        .then(async (res) => {
          if (!res.ok) return false;
          const data = await res.json();
          setTokens(data.access, data.refresh); // refresh tokens rotate
          return true;
        })
        .catch(() => false)
        .finally(() => { refreshing = null; });
    }
    return refreshing;
  }

  async function request(method, url, body, isRetry) {
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const token = store.get(ACCESS_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;

    let res;
    try {
      res = await fetch(url, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      throw new ApiError(0, { detail: 'Network error. Check your connection and try again.' });
    }

    // Expired access token: refresh once and retry. If refresh fails, log out and retry
    // anonymously (public pages still work; protected ones then get a clean 401).
    if (res.status === 401 && token && !isRetry) {
      if (!(await refreshAccessToken())) {
        clearTokens();
        updateNav();
      }
      return request(method, url, body, true);
    }

    const text = await res.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (e) { data = text; }
    }
    if (!res.ok) throw new ApiError(res.status, data);
    return data;
  }

  const api = {
    get: (url) => request('GET', url),
    post: (url, body = {}) => request('POST', url, body),
    patch: (url, body = {}) => request('PATCH', url, body),
    del: (url) => request('DELETE', url),
  };

  /* ---------- Auth ---------- */

  function decodeJwt(token) {
    try {
      const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(decodeURIComponent(
        atob(payload).split('').map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join('')
      ));
    } catch (e) {
      return null;
    }
  }

  const auth = {
    /** {username, role} if logged in (refresh token present and unexpired), else null. */
    user() {
      const claims = decodeJwt(store.get(REFRESH_KEY) || '');
      if (!claims || claims.exp * 1000 < Date.now()) return null;
      return { id: claims.user_id, username: claims.username, role: claims.role };
    },

    async login(username, password) {
      const data = await api.post('/api/auth/login/', { username, password });
      setTokens(data.access, data.refresh);
      return data.user;
    },

    async register(fields) {
      const data = await api.post('/api/auth/register/', fields);
      setTokens(data.access, data.refresh);
      return data.user;
    },

    async logout() {
      const refresh = store.get(REFRESH_KEY);
      if (refresh) {
        try { await api.post('/api/auth/logout/', { refresh }); } catch (e) { /* already invalid */ }
      }
      clearTokens();
    },

    /** Send logged-out visitors to the login page, then back here afterwards. */
    requireLogin() {
      if (auth.user()) return true;
      location.href = '/login/?next=' + encodeURIComponent(location.pathname + location.search);
      return false;
    },

    /** The ?next= target, only if it's a path on this site (prevents open redirects). */
    nextUrl(fallback = '/') {
      const next = new URLSearchParams(location.search).get('next') || '';
      return next.startsWith('/') && !next.startsWith('//') ? next : fallback;
    },
  };

  /* ---------- DOM helper ---------- */

  /**
   * h('a', {href: '/x', class: 'btn'}, 'text', childNode)
   * Text children are set with textContent, so data from the API can never inject HTML.
   */
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key.startsWith('on') && typeof value === 'function') {
        el.addEventListener(key.slice(2), value);
      } else if (key === 'dataset') {
        Object.assign(el.dataset, value);
      } else {
        el.setAttribute(key, value === true ? '' : value);
      }
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  /* ---------- Formatting ---------- */

  const fmt = {
    kes(amount) {
      const n = Number(amount);
      return 'KES ' + n.toLocaleString('en-KE', { maximumFractionDigits: n % 1 ? 2 : 0 });
    },
    /** '2026-10-19' -> 'Sat, 19 Oct 2026' (parsed as a local date, not UTC). */
    date(isoDate) {
      const [y, m, d] = isoDate.split('-').map(Number);
      return new Date(y, m - 1, d).toLocaleDateString('en-KE', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
      });
    },
    /** '15:00:00' -> '15:00' */
    time(isoTime) {
      return isoTime.slice(0, 5);
    },
    statusLabel(status) {
      return status.charAt(0).toUpperCase() + status.slice(1);
    },
  };

  /* ---------- Shared page chrome ---------- */

  function updateNav() {
    const user = auth.user();
    document.querySelectorAll('[data-auth="in"]').forEach((el) => { el.hidden = !user; });
    document.querySelectorAll('[data-auth="out"]').forEach((el) => { el.hidden = !!user; });
    document.querySelectorAll('[data-user-name]').forEach((el) => {
      el.textContent = user ? user.username : '';
    });
    document.querySelectorAll('[data-roles]').forEach((el) => {
      const roles = el.dataset.roles.split(' ');
      el.hidden = !(user && roles.includes(user.role));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    updateNav();

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        await auth.logout();
        location.href = '/';
      });
    }

    const menuBtn = document.getElementById('menu-btn');
    const nav = document.getElementById('site-nav');
    if (menuBtn && nav) {
      menuBtn.addEventListener('click', () => {
        const open = nav.classList.toggle('open');
        menuBtn.setAttribute('aria-expanded', String(open));
      });
    }
  });

  window.SB = { api, auth, h, fmt, ApiError };
})();
