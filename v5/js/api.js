/**
 * REGROW — SHARED API CLIENT  v1.2
 * ──────────────────────────────────────────────────────────────────────────
 * Drop-in replacement for the v1.1 api.js. Fully backwards-compatible.
 *
 * NEW in v1.2:
 *   • Retry with exponential back-off (network hiccups handled automatically)
 *   • Global loading state helpers  (window.API.ui.*)
 *   • Structured error class         (window.APIError)
 *   • Optimistic update helpers      (window.API.optimistic.*)
 *   • Event bus for cross-component reactivity (window.API.events.*)
 *   • WebSocket-ready feed polling   (window.API.feed.poll / .stopPoll)
 *
 * Usage — same as before, nothing breaks:
 *   const data = await window.API.pickups.list();
 *   await window.API.pickups.confirm(pickupId);
 * ──────────────────────────────────────────────────────────────────────────
 */

(function () {
  'use strict';

  // ── Config ────────────────────────────────────────────────────────────────
  const BASE_URL      = window.REGROW_API_URL || 'http://localhost:8001';
  const LOGIN_PAGE    = 'login.html';
  const RETRY_DELAYS  = [400, 1200, 3000];   // ms between retries (3 attempts)
  const RETRY_CODES   = new Set([408, 429, 500, 502, 503, 504]);

  // ── Custom error class ────────────────────────────────────────────────────
  class APIError extends Error {
    constructor(message, status, detail) {
      super(message);
      this.name    = 'APIError';
      this.status  = status;
      this.detail  = detail;
    }
  }
  window.APIError = APIError;

  // ── Token management ──────────────────────────────────────────────────────
  const Auth = {
    getToken()    { return localStorage.getItem('regrow_token'); },
    setToken(t)   { localStorage.setItem('regrow_token', t); },
    clearToken()  {
      localStorage.removeItem('regrow_token');
      localStorage.removeItem('regrow_user');
    },
    getUser() {
      try   { return JSON.parse(localStorage.getItem('regrow_user') || 'null'); }
      catch { return null; }
    },
    setUser(u)    { localStorage.setItem('regrow_user', JSON.stringify(u)); },
    isAuthenticated() { return !!this.getToken(); },
    requireAuth() {
      if (!this.isAuthenticated()) {
        window.location.href = LOGIN_PAGE;
        return false;
      }
      return true;
    },
    logout() {
      this.clearToken();
      window.location.href = LOGIN_PAGE;
    },
  };

  // ── Simple event bus (cross-component reactivity) ─────────────────────────
  // Usage:
  //   API.events.on('pickup_updated', handler)
  //   API.events.emit('pickup_updated', { id, status })
  //   API.events.off('pickup_updated', handler)
  const EventBus = (() => {
    const listeners = {};
    return {
      on(evt, fn)  {
        (listeners[evt] = listeners[evt] || []).push(fn);
        return () => this.off(evt, fn);   // returns unsubscribe
      },
      off(evt, fn) {
        listeners[evt] = (listeners[evt] || []).filter(f => f !== fn);
      },
      emit(evt, payload) {
        (listeners[evt] || []).forEach(fn => { try { fn(payload); } catch(e) { console.error(e); } });
        (listeners['*'] || []).forEach(fn => { try { fn(evt, payload); } catch(e) { console.error(e); } });
      },
    };
  })();

  // ── UI loading state helpers ──────────────────────────────────────────────
  // Usage:
  //   const stop = API.ui.loading('pickups')
  //   API.ui.isLoading('pickups')   // → true
  //   stop()
  const UI = (() => {
    const active = new Map();   // key → count
    const subs   = [];
    function notify() { subs.forEach(fn => fn(active)); }
    return {
      loading(key) {
        active.set(key, (active.get(key) || 0) + 1);
        notify();
        return () => {
          const n = (active.get(key) || 1) - 1;
          if (n <= 0) active.delete(key); else active.set(key, n);
          notify();
        };
      },
      isLoading(key) { return (active.get(key) || 0) > 0; },
      isAnyLoading() { return active.size > 0; },
      onChange(fn)   { subs.push(fn); return () => subs.splice(subs.indexOf(fn), 1); },
    };
  })();

  // ── Optimistic update helpers ─────────────────────────────────────────────
  // Usage:
  //   const rollback = API.optimistic.apply(setPickups, id, { status: 'confirmed' })
  //   try { await API.pickups.confirm(id) } catch { rollback() }
  const Optimistic = {
    /**
     * Immediately update an item in a React state array, return rollback fn.
     * @param {Function} setter  – React setState function
     * @param {string}   id      – item id to patch
     * @param {Object}   patch   – fields to merge
     */
    apply(setter, id, patch) {
      let prev;
      setter(items => {
        prev = items;
        return items.map(item => item.id === id ? { ...item, ...patch } : item);
      });
      return () => setter(prev);   // rollback
    },
  };

  // ── Core fetch with retry ─────────────────────────────────────────────────
  async function request(method, path, body = null, attempt = 0) {
    const token   = Auth.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const config = { method, headers };
    if (body && method !== 'GET') config.body = JSON.stringify(body);

    let res;
    try {
      res = await fetch(`${BASE_URL}${path}`, config);
    } catch (networkErr) {
      // Network failure (offline, DNS, timeout)
      if (attempt < RETRY_DELAYS.length) {
        await sleep(RETRY_DELAYS[attempt]);
        return request(method, path, body, attempt + 1);
      }
      throw new APIError('Tidak dapat terhubung ke server. Periksa koneksi Anda.', 0, networkErr.message);
    }

    if (res.status === 401) {
      Auth.clearToken();
      window.location.href = LOGIN_PAGE;
      throw new APIError('Sesi berakhir. Silakan login kembali.', 401);
    }

    if (res.status === 204) return null;   // DELETE / no content

    // Retryable server errors
    if (RETRY_CODES.has(res.status) && attempt < RETRY_DELAYS.length) {
      await sleep(RETRY_DELAYS[attempt]);
      return request(method, path, body, attempt + 1);
    }

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        detail = err.detail || err.message || detail;
      } catch {}
      throw new APIError(detail, res.status, detail);
    }

    return res.json();
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // Convenience wrappers — identical API to v1.1 ──────────────────────────
  const get = (path, params) => {
    const url = params
      ? `${path}?${new URLSearchParams(
          Object.entries(params).filter(([, v]) => v != null)
        )}`
      : path;
    return request('GET', url);
  };
  const post  = (path, body) => request('POST',   path, body);
  const patch = (path, body) => request('PATCH',  path, body);
  const del   = (path)       => request('DELETE', path);

  // ── Feed polling ──────────────────────────────────────────────────────────
  let _feedTimer  = null;
  let _feedEtag   = null;   // for future ETag-based polling

  const Feed = {
    list(params = {}) {
      return get('/api/feed', params);
    },
    /**
     * Start polling the feed every `intervalMs` (default 15 s).
     * Calls `onUpdate(events[])` when new events arrive.
     * Returns a stop function.
     */
    poll(onUpdate, intervalMs = 15_000) {
      if (_feedTimer) this.stopPoll();
      let latestId = null;

      const tick = async () => {
        try {
          const events = await this.list({ limit: 30 });
          if (!events || !events.length) return;

          const newest = events[0].id;
          if (newest !== latestId) {
            latestId = newest;
            onUpdate(events);
            EventBus.emit('feed_updated', events);
          }
        } catch { /* silent — keep polling */ }
      };

      tick();   // immediate first call
      _feedTimer = setInterval(tick, intervalMs);
      return () => this.stopPoll();
    },
    stopPoll() {
      clearInterval(_feedTimer);
      _feedTimer = null;
    },
  };

  // ── API object (fully backwards-compatible) ───────────────────────────────
  const API = {
    auth:        Auth,
    events:      EventBus,
    ui:          UI,
    optimistic:  Optimistic,

    // ── Pickups ──────────────────────────────────────────────────────────────
    pickups: {
      list(params = {}) {
        return get('/api/pickups', params);
        // Returns: { items: PickupListOut[], total, page, limit }
      },
      get(id)              { return get(`/api/pickups/${id}`); },
      confirm(id)          { return patch(`/api/pickups/${id}`, { status: 'confirmed' }); },
      complete(id)         { return patch(`/api/pickups/${id}`, { status: 'completed' }); },
      cancel(id)           { return patch(`/api/pickups/${id}`, { status: 'cancelled' }); },
      updateStatus(id, st) { return patch(`/api/pickups/${id}`, { status: st }); },
    },

    // ── Files & Grading ───────────────────────────────────────────────────────
    files: {
      getUrl(fileId)     { return get(`/api/files/${fileId}/url`); },
      getJobStatus(jobId){ return get(`/api/files/job/${jobId}`); },
      async upload(pickupId, file) {
        const token = Auth.getToken();
        const form  = new FormData();
        form.append('file', file);
        const res = await fetch(
          `${BASE_URL}/api/files/upload?pickup_id=${pickupId}`,
          { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form }
        );
        if (!res.ok) throw new APIError(`Upload gagal: ${res.status}`, res.status);
        return res.json();
      },
    },

    // ── Marketplace ───────────────────────────────────────────────────────────
    marketplace: {
      list(params = {})         { return get('/api/marketplace/listings', params); },
      create(body)              { return post('/api/marketplace/listings', body); },
      updateStatus(id, st, buyerId = null) {
        const body = { status: st };
        if (buyerId) body.buyer_id = buyerId;
        return patch(`/api/marketplace/listings/${id}`, body);
      },
      match(id, buyerId)        { return patch(`/api/marketplace/listings/${id}`, { status: 'matched', buyer_id: buyerId }); },
      complete(id)              { return patch(`/api/marketplace/listings/${id}`, { status: 'completed' }); },
    },

    // ── Community ─────────────────────────────────────────────────────────────
    community: {
      list()                           { return get('/api/communities'); },
      create(body)                     { return post('/api/communities', body); },
      getMembers(id)                   { return get(`/api/communities/${id}/members`); },
      addMember(id, userId, isAdmin=false) {
        return post(`/api/communities/${id}/members`, { user_id: userId, is_admin: isAdmin });
      },
      broadcast(id, message)           { return post(`/api/communities/${id}/broadcast`, { message }); },
    },

    // ── Channel ───────────────────────────────────────────────────────────────
    channel: {
      list(params = {})          { return get('/api/channel/posts', params); },
      create(body)               { return post('/api/channel/posts', body); },
      update(postId, body)       { return patch(`/api/channel/posts/${postId}`, body); },
      togglePin(postId, current) { return patch(`/api/channel/posts/${postId}`, { is_pinned: !current }); },
      delete(postId)             { return del(`/api/channel/posts/${postId}`); },
    },

    // ── Activity Feed ─────────────────────────────────────────────────────────
    feed: Feed,

    // ── Auth helpers ──────────────────────────────────────────────────────────
    login: async function (phone, password) {
      const data = await post('/api/auth/login', { phone, password });
      Auth.setToken(data.access_token);
      Auth.setUser({ id: data.user_id, role: data.role, phone });
      EventBus.emit('auth_login', { phone, role: data.role });
      return data;
    },
    logout: Auth.logout.bind(Auth),
  };

  // ── Global helpers ────────────────────────────────────────────────────────
  window.API = API;

  window.formatRelative = function (iso) {
    if (!iso) return '–';
    const diff = (Date.now() - new Date(iso)) / 1000;
    if (diff < 60)    return `${Math.floor(diff)} detik lalu`;
    if (diff < 3600)  return `${Math.floor(diff / 60)} mnt lalu`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} jam lalu`;
    return `${Math.floor(diff / 86400)} hari lalu`;
  };

  window.formatIDR = function (n) {
    if (!n) return '–';
    return 'Rp ' + Number(n).toLocaleString('id-ID');
  };

  window.formatDate = function (iso) {
    if (!iso) return '–';
    return new Date(iso).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  // ── Deep-link builder ─────────────────────────────────────────────────────
  // Used by WhatsApp handlers to send clickable app links.
  const APP_URL = window.REGROW_APP_URL || window.location.origin;
  window.buildDeepLink = function (type, id) {
    const routes = {
      pickup:    `Dashboard.html?pickup=${id}`,
      listing:   `Marketplace.html?listing=${id}`,
      community: `Channel.html?community=${id}`,
      feed:      `feed.html`,
    };
    return `${APP_URL}/${routes[type] || ''}`;
  };

  console.log('[Regrow API] v1.2 loaded. Auth:', Auth.isAuthenticated() ? '✓ logged in' : '✗ not logged in');
})();
