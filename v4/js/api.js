/**
 * REGROW — SHARED API CLIENT
 * ──────────────────────────────────────────────────────────────────────────
 * Include this BEFORE the <script type="text/babel"> tag in every HTML page.
 * Defines window.API which all React components use instead of MOCK data.
 *
 * Usage in Babel/React component:
 *   const data = await window.API.pickups.list();
 *   await window.API.pickups.confirm(pickupId);
 * ──────────────────────────────────────────────────────────────────────────
 */

(function () {
  'use strict';

  // ── Config ───────────────────────────────────────────────────────────────
  // Change this to your VPS domain in production:
  //   e.g. 'https://api.regrow.id'
  const BASE_URL = window.REGROW_API_URL || 'http://localhost:8001';
  const LOGIN_PAGE = 'login.html';

  // ── Token management (localStorage) ─────────────────────────────────────
  const Auth = {
    getToken() { return localStorage.getItem('regrow_token'); },
    setToken(t) { localStorage.setItem('regrow_token', t); },
    clearToken() { localStorage.removeItem('regrow_token'); localStorage.removeItem('regrow_user'); },
    getUser() {
      try { return JSON.parse(localStorage.getItem('regrow_user') || 'null'); }
      catch { return null; }
    },
    setUser(u) { localStorage.setItem('regrow_user', JSON.stringify(u)); },
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

  // ── Core fetch wrapper ───────────────────────────────────────────────────
  async function request(method, path, body = null, opts = {}) {
    const token = Auth.getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const config = { method, headers };
    if (body && method !== 'GET') config.body = JSON.stringify(body);

    const res = await fetch(`${BASE_URL}${path}`, config);

    if (res.status === 401) {
      Auth.clearToken();
      window.location.href = LOGIN_PAGE;
      throw new Error('Session expired');
    }
    if (res.status === 204) return null;   // DELETE with no content
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  const get    = (path, params) => {
    const url = params
      ? `${path}?${new URLSearchParams(Object.entries(params).filter(([,v]) => v != null)).toString()}`
      : path;
    return request('GET', url);
  };
  const post   = (path, body) => request('POST',   path, body);
  const patch  = (path, body) => request('PATCH',  path, body);
  const del    = (path)       => request('DELETE', path);

  // ── API methods ──────────────────────────────────────────────────────────
  const API = {
    auth: Auth,

    // ── Pickups ────────────────────────────────────────────────────────────
    pickups: {
      list(params = {}) {
        // params: { page, limit, status }
        return get('/api/pickups', params);
        // Returns: { items: [PickupListOut], total, page, limit }
        // PickupListOut: { id, user_id, user_phone, location, waste_type, status, created_at }
      },
      get(id) {
        return get(`/api/pickups/${id}`);
        // Returns: PickupOut with files[] and grade
      },
      confirm(id) {
        return patch(`/api/pickups/${id}`, { status: 'confirmed' });
      },
      complete(id) {
        return patch(`/api/pickups/${id}`, { status: 'completed' });
      },
      cancel(id) {
        return patch(`/api/pickups/${id}`, { status: 'cancelled' });
      },
      updateStatus(id, status) {
        return patch(`/api/pickups/${id}`, { status });
      },
    },

    // ── Files & Grading ────────────────────────────────────────────────────
    files: {
      getUrl(fileId) {
        return get(`/api/files/${fileId}/url`);
        // Returns: { url: string (presigned MinIO URL), expires_in }
      },
      getJobStatus(jobId) {
        return get(`/api/files/job/${jobId}`);
        // Returns: { job_id, status, result, error }
      },
      async upload(pickupId, file) {
        // file: File object from <input type="file">
        const token = Auth.getToken();
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(
          `${BASE_URL}/api/files/upload?pickup_id=${pickupId}`,
          { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form }
        );
        if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
        return res.json();
        // Returns: { file_id, job_id, message }
      },
    },

    // ── Marketplace ────────────────────────────────────────────────────────
    marketplace: {
      list(params = {}) {
        return get('/api/marketplace/listings', params);
        // Returns: ListingOut[]
      },
      create(body) {
        return post('/api/marketplace/listings', body);
      },
      updateStatus(listingId, status, buyerId = null) {
        const body = { status };
        if (buyerId) body.buyer_id = buyerId;
        return patch(`/api/marketplace/listings/${listingId}`, body);
      },
      match(listingId, buyerId) {
        return patch(`/api/marketplace/listings/${listingId}`, { status: 'matched', buyer_id: buyerId });
      },
      complete(listingId) {
        return patch(`/api/marketplace/listings/${listingId}`, { status: 'completed' });
      },
    },

    // ── Community ─────────────────────────────────────────────────────────
    community: {
      list() { return get('/api/communities'); },
      create(body) { return post('/api/communities', body); },
      getMembers(communityId) {
        return get(`/api/communities/${communityId}/members`);
        // Returns: [{ user_id, phone, name, is_admin, joined_at }]
      },
      addMember(communityId, userId, isAdmin = false) {
        return post(`/api/communities/${communityId}/members`, { user_id: userId, is_admin: isAdmin });
      },
      broadcast(communityId, message) {
        return post(`/api/communities/${communityId}/broadcast`, { message });
        // Returns: { sent_to: number, message }
      },
    },

    // ── Channel ───────────────────────────────────────────────────────────
    channel: {
      list(params = {}) { return get('/api/channel/posts', params); },
      create(body) { return post('/api/channel/posts', body); },
      update(postId, body) { return patch(`/api/channel/posts/${postId}`, body); },
      togglePin(postId, currentPinned) {
        return patch(`/api/channel/posts/${postId}`, { is_pinned: !currentPinned });
      },
      delete(postId) { return del(`/api/channel/posts/${postId}`); },
    },

    // ── Activity Feed ─────────────────────────────────────────────────────
    feed: {
      list(params = {}) {
        return get('/api/feed', params);
        // Returns: ActivityEventOut[]
      },
    },

    // ── Auth ──────────────────────────────────────────────────────────────
    login: async function (phone, password) {
      const data = await post('/api/auth/login', { phone, password });
      Auth.setToken(data.access_token);
      Auth.setUser({ id: data.user_id, role: data.role, phone });
      return data;
    },
    logout: Auth.logout.bind(Auth),
  };

  // ── Helpers exposed globally ─────────────────────────────────────────────
  window.API = API;

  // Format date helper used by all pages
  window.formatRelative = function (iso) {
    if (!iso) return '–';
    const diff = (Date.now() - new Date(iso)) / 1000;
    if (diff < 60)     return `${Math.floor(diff)} detik lalu`;
    if (diff < 3600)   return `${Math.floor(diff / 60)} mnt lalu`;
    if (diff < 86400)  return `${Math.floor(diff / 3600)} jam lalu`;
    return `${Math.floor(diff / 86400)} hari lalu`;
  };

  window.formatIDR = function (n) {
    if (!n) return '–';
    return 'Rp ' + Number(n).toLocaleString('id-ID');
  };

  window.formatDate = function (iso) {
    if (!iso) return '–';
    return new Date(iso).toLocaleDateString('id-ID', { day:'numeric', month:'short', year:'numeric' });
  };

  console.log('[Regrow API] Loaded. Auth:', Auth.isAuthenticated() ? 'logged in' : 'not logged in');
})();
