/**
 * DASHBOARD.HTML — EXACT PATCH INSTRUCTIONS
 * ──────────────────────────────────────────────────────────────────────────
 * Apply these changes to Dashboard.html to connect it to the real backend.
 * Changes are surgical — keep everything else (CSS, icons, components).
 * ──────────────────────────────────────────────────────────────────────────
 */

// ═══════════════════════════════════════════════════════════════════════════
// STEP 1: Add api.js BEFORE the babel script tag
// ═══════════════════════════════════════════════════════════════════════════

// FIND this line (near end of <head>):
//   <script src="https://unpkg.com/@babel/standalone..."></script>
//
// ADD this line BEFORE it:
//   <script src="js/api.js"></script>


// ═══════════════════════════════════════════════════════════════════════════
// STEP 2: Replace the entire MOCK DATA section
// ═══════════════════════════════════════════════════════════════════════════

// REMOVE everything between these two comments:
//   // ─── Mock data (mirroring backend models) ─────────────────────────────────
//   ...MOCK_PICKUPS, MOCK_GRADES constants...
//
// REMOVE also the NOW / minutesAgo / hoursAgo / daysAgo helpers
// (they'll be replaced by window.formatRelative from api.js)
//
// REPLACE WITH (paste inside the <script type="text/babel"> block):

const STATUS_LABELS = {
  pending: 'Menunggu', confirmed: 'Dikonfirmasi', grading: 'Sedang Dinilai',
  graded: 'Selesai Dinilai', completed: 'Selesai', cancelled: 'Dibatalkan',
};
const STATUS_CLASSES = {
  pending:   'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200/60',
  confirmed: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200/60',
  grading:   'bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-200/60',
  graded:    'bg-teal-50 text-teal-700 ring-1 ring-inset ring-teal-200/60',
  completed: 'bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-200/60',
  cancelled: 'bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-200/60',
};
const STATUS_DOT = {
  pending:'bg-amber-500', confirmed:'bg-blue-500', grading:'bg-violet-500',
  graded:'bg-teal-500', completed:'bg-brand-600', cancelled:'bg-rose-500',
};


// ═══════════════════════════════════════════════════════════════════════════
// STEP 3: Replace the Dashboard() component function entirely
// ═══════════════════════════════════════════════════════════════════════════

// FIND: function Dashboard() {
// REPLACE the entire function body with:

function Dashboard() {
  const { useState, useEffect, useMemo } = React;

  // ── Auth guard ──────────────────────────────────────────────────────────
  useEffect(() => { window.API.auth.requireAuth(); }, []);

  // ── State ───────────────────────────────────────────────────────────────
  const [pickups,    setPickups]    = useState([]);
  const [total,      setTotal]      = useState(0);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [toast,      setToast]      = useState(null);
  const [confirming, setConfirming] = useState(null);
  const [viewingGrade, setViewingGrade] = useState(null);
  const [search,     setSearch]     = useState('');
  const [statusFilter, setStatusFilter] = useState('');  // '' = all
  const [page,       setPage]       = useState(1);
  const [feed,       setFeed]       = useState([]);

  // ── Toast auto-dismiss ──────────────────────────────────────────────────
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(t);
  }, [toast]);

  // ── Load pickups ────────────────────────────────────────────────────────
  const loadPickups = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, limit: 20 };
      if (statusFilter) params.status = statusFilter;
      const data = await window.API.pickups.list(params);
      setPickups(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e.message || 'Gagal memuat data');
    } finally {
      setLoading(false);
    }
  };

  // ── Load activity feed ───────────────────────────────────────────────────
  const loadFeed = async () => {
    try {
      const data = await window.API.feed.list({ limit: 8 });
      setFeed(data || []);
    } catch (_) {
      // Feed is optional — don't block UI if it fails
    }
  };

  useEffect(() => {
    loadPickups();
    loadFeed();
  }, [page, statusFilter]);

  // ── Actions ─────────────────────────────────────────────────────────────
  const handleConfirm = async (id) => {
    setConfirming(id);
    try {
      await window.API.pickups.confirm(id);
      setPickups(prev => prev.map(p => p.id === id ? { ...p, status: 'confirmed' } : p));
      setToast({ kind: 'success', msg: 'Pickup berhasil dikonfirmasi' });
      loadFeed(); // refresh feed
    } catch (e) {
      setToast({ kind: 'error', msg: e.message || 'Gagal konfirmasi' });
    } finally {
      setConfirming(null);
    }
  };

  const handleViewGrade = async (pickup) => {
    // Fetch real grade from pickup's files
    try {
      const detail = await window.API.pickups.get(pickup.id);
      const lastFile = detail.files?.[detail.files.length - 1];
      if (lastFile?.grade) {
        setViewingGrade({ pickup: detail, grade: lastFile.grade });
      } else {
        setToast({ kind: 'error', msg: 'Belum ada hasil grading untuk pickup ini' });
      }
    } catch (e) {
      setToast({ kind: 'error', msg: e.message || 'Gagal memuat grade' });
    }
  };

  const handleRefresh = async () => {
    await loadPickups();
    await loadFeed();
    setToast({ kind: 'success', msg: 'Data diperbarui' });
  };

  // ── Derived stats ────────────────────────────────────────────────────────
  const stats = useMemo(() => ({
    pending:   pickups.filter(p => p.status === 'pending').length,
    grading:   pickups.filter(p => p.status === 'grading').length,
    graded:    pickups.filter(p => p.status === 'graded').length,
    completed: pickups.filter(p => p.status === 'completed').length,
    totalKg:   pickups.reduce((s, p) => s + (p.estimated_weight || 0), 0),
  }), [pickups]);

  const filtered = useMemo(() =>
    pickups.filter(p =>
      !search || p.location?.toLowerCase().includes(search.toLowerCase()) ||
      p.waste_type?.toLowerCase().includes(search.toLowerCase()) ||
      p.user_phone?.includes(search)
    ), [pickups, search]
  );

  // ── Loading screen ──────────────────────────────────────────────────────
  if (loading && pickups.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"/>
          <p className="text-sm text-gray-400">Memuat dashboard…</p>
        </div>
      </div>
    );
  }

  // ── Error screen ─────────────────────────────────────────────────────────
  if (error && pickups.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center max-w-sm">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <XCircle size={24} className="text-red-500"/>
          </div>
          <p className="text-sm text-gray-600 mb-4">{error}</p>
          <button onClick={loadPickups}
            className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700">
            Coba Lagi
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar active="dashboard"/>
      <main className="flex-1 min-w-0">

        {/* ── Top bar ── */}
        <header className="h-16 px-8 bg-white/70 backdrop-blur border-b border-gray-100 flex items-center justify-between sticky top-0 z-20">
          <div>
            <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">
              {new Date().toLocaleDateString('id-ID', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}
            </div>
            <h1 className="text-[15px] font-semibold text-gray-900 leading-tight">Dashboard</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleRefresh} disabled={loading}
              className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1.5 text-gray-600 disabled:opacity-50">
              <RefreshCw size={12} className={loading ? 'spin' : ''}/>
              Refresh
            </button>
            <button onClick={() => window.API.logout()}
              className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1.5 text-red-500">
              <LogOut size={12}/> Keluar
            </button>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* ── Stat cards ── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label:'Menunggu',      value: stats.pending,   color:'text-amber-600',  bg:'bg-amber-50' },
              { label:'Sedang Dinilai',value: stats.grading,   color:'text-violet-600', bg:'bg-violet-50' },
              { label:'Selesai Dinilai',value: stats.graded,   color:'text-teal-600',   bg:'bg-teal-50' },
              { label:'Total est. Kg', value: `${stats.totalKg.toFixed(1)} kg`, color:'text-brand-600', bg:'bg-brand-50' },
            ].map(({ label, value, color, bg }) => (
              <div key={label} className="card p-4">
                <div className={`text-2xl font-bold ${color} mb-1`}>{value}</div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

            {/* ── Pickups table ── */}
            <div className="lg:col-span-8 card overflow-hidden">
              {/* Table header */}
              <div className="px-5 py-4 border-b border-gray-50 flex items-center gap-3">
                <h2 className="text-sm font-semibold text-gray-900 flex-1">Pickup Terbaru</h2>
                <div className="relative">
                  <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"/>
                  <input value={search} onChange={e => setSearch(e.target.value)}
                    placeholder="Cari lokasi, jenis..."
                    className="pl-7 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 w-52"/>
                </div>
                {/* Status filter */}
                <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
                  className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-500">
                  <option value="">Semua Status</option>
                  {Object.entries(STATUS_LABELS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>

              {/* Loading overlay */}
              {loading && (
                <div className="absolute inset-0 bg-white/60 flex items-center justify-center z-10">
                  <div className="w-5 h-5 border-2 border-brand-600 border-t-transparent rounded-full animate-spin"/>
                </div>
              )}

              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left px-5 py-2.5 text-xs font-medium text-gray-500">Pengguna</th>
                    <th className="text-left px-3 py-2.5 text-xs font-medium text-gray-500 hidden md:table-cell">Lokasi</th>
                    <th className="text-left px-3 py-2.5 text-xs font-medium text-gray-500">Jenis</th>
                    <th className="text-left px-3 py-2.5 text-xs font-medium text-gray-500">Status</th>
                    <th className="text-left px-3 py-2.5 text-xs font-medium text-gray-500 hidden lg:table-cell">Waktu</th>
                    <th className="px-3 py-2.5"/>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filtered.length === 0 && !loading && (
                    <tr><td colSpan="6" className="text-center py-12 text-sm text-gray-400">
                      {error ? error : 'Tidak ada pickup'}
                    </td></tr>
                  )}
                  {filtered.map(pickup => (
                    <tr key={pickup.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-5 py-3">
                        <div className="text-xs font-medium text-gray-800">
                          {pickup.user_phone || pickup.user_id?.slice(0,8)}
                        </div>
                        <div className="text-[11px] text-gray-400 font-mono">{pickup.id.slice(0,8).toUpperCase()}</div>
                      </td>
                      <td className="px-3 py-3 hidden md:table-cell">
                        <div className="text-xs text-gray-600 max-w-[160px] truncate">{pickup.location}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="text-xs text-gray-700">{pickup.waste_type}</div>
                        {pickup.estimated_weight && (
                          <div className="text-[11px] text-gray-400">{pickup.estimated_weight} kg</div>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge status={pickup.status}/>
                      </td>
                      <td className="px-3 py-3 hidden lg:table-cell">
                        <div className="text-[11px] text-gray-400">{window.formatRelative(pickup.created_at)}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5 justify-end">
                          {pickup.status === 'pending' && (
                            <button
                              disabled={confirming === pickup.id}
                              onClick={() => handleConfirm(pickup.id)}
                              className="px-2.5 py-1 text-[11px] font-medium bg-brand-50 text-brand-700 hover:bg-brand-100 rounded-md flex items-center gap-1 disabled:opacity-50">
                              {confirming === pickup.id
                                ? <><RefreshCw size={10} className="spin"/>Memproses</>
                                : <><CheckCircle size={10}/>Konfirmasi</>
                              }
                            </button>
                          )}
                          {pickup.status === 'graded' && (
                            <button
                              onClick={() => handleViewGrade(pickup)}
                              className="px-2.5 py-1 text-[11px] font-medium bg-teal-50 text-teal-700 hover:bg-teal-100 rounded-md flex items-center gap-1">
                              <Eye size={10}/> Lihat Grade
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {total > 20 && (
                <div className="px-5 py-3 border-t border-gray-50 flex items-center justify-between">
                  <span className="text-xs text-gray-400">
                    {(page-1)*20+1}–{Math.min(page*20, total)} dari {total} pickup
                  </span>
                  <div className="flex gap-1.5">
                    <button disabled={page===1} onClick={()=>setPage(p=>p-1)}
                      className="px-2.5 py-1 text-xs border border-gray-200 rounded disabled:opacity-40">← Prev</button>
                    <button disabled={page*20>=total} onClick={()=>setPage(p=>p+1)}
                      className="px-2.5 py-1 text-xs border border-gray-200 rounded disabled:opacity-40">Next →</button>
                  </div>
                </div>
              )}
            </div>

            {/* ── Activity feed ── */}
            <div className="lg:col-span-4 card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-50">
                <h2 className="text-sm font-semibold text-gray-900">Aktivitas Terbaru</h2>
              </div>
              <div className="divide-y divide-gray-50">
                {feed.length === 0 && (
                  <div className="text-center py-10 text-xs text-gray-400">Belum ada aktivitas</div>
                )}
                {feed.map(event => (
                  <FeedItem key={event.id} event={event}/>
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* Grade modal */}
        {viewingGrade && (
          <GradeModal data={viewingGrade} onClose={() => setViewingGrade(null)}/>
        )}

        {/* Toast */}
        {toast && (
          <div className={`fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm font-medium text-white shadow-lg toast z-50 ${toast.kind === 'success' ? 'bg-brand-600' : 'bg-rose-500'}`}>
            {toast.msg}
          </div>
        )}
      </main>
    </div>
  );
}


// ─── FeedItem component ─────────────────────────────────────────────────────

function FeedItem({ event }) {
  const ICONS = {
    pickup_created:  { emoji:'📦', color:'text-amber-500 bg-amber-50' },
    pickup_confirmed:{ emoji:'✅', color:'text-blue-500 bg-blue-50' },
    grade_completed: { emoji:'🎯', color:'text-teal-500 bg-teal-50' },
    listing_created: { emoji:'🏪', color:'text-brand-600 bg-brand-50' },
    listing_matched: { emoji:'🤝', color:'text-brand-700 bg-brand-100' },
    broadcast_sent:  { emoji:'📣', color:'text-violet-600 bg-violet-50' },
  };
  const cfg = ICONS[event.event_type] || { emoji:'•', color:'text-gray-500 bg-gray-50' };
  return (
    <div className="px-5 py-3 flex items-start gap-3">
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${cfg.color}`}>
        {cfg.emoji}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-gray-800 truncate">{event.title}</div>
        {event.subtitle && <div className="text-[11px] text-gray-400 truncate">{event.subtitle}</div>}
        <div className="text-[10px] text-gray-300 mt-0.5">{window.formatRelative(event.created_at)}</div>
      </div>
    </div>
  );
}


// ─── GradeModal component ───────────────────────────────────────────────────

function GradeModal({ data, onClose }) {
  const { pickup, grade } = data;
  const [imgUrl, setImgUrl] = React.useState(null);

  React.useEffect(() => {
    const lastFile = pickup.files?.[pickup.files.length - 1];
    if (lastFile) {
      window.API.files.getUrl(lastFile.id)
        .then(d => setImgUrl(d.url))
        .catch(() => {});
    }
  }, [pickup]);

  const GRADE_COLOR = { A:'text-brand-600 bg-brand-50', B:'text-blue-600 bg-blue-50', C:'text-amber-600 bg-amber-50', D:'text-rose-600 bg-rose-50' };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full overflow-hidden" onClick={e => e.stopPropagation()}>
        {imgUrl && (
          <div className="aspect-video w-full overflow-hidden bg-gray-100">
            <img src={imgUrl} alt="Waste photo" className="w-full h-full object-cover"/>
          </div>
        )}
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Hasil Grading AI</h3>
            <span className={`px-3 py-1 rounded-full text-lg font-bold ${GRADE_COLOR[grade.grade] || 'bg-gray-100 text-gray-700'}`}>
              {grade.grade}
            </span>
          </div>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-400">Keyakinan AI</dt>
              <dd className="font-medium">{Math.round((grade.confidence||0)*100)}%</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Estimasi berat</dt>
              <dd className="font-medium">{grade.estimated_kg || '–'} kg</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-400">Dinilai oleh</dt>
              <dd className="font-medium">{grade.graded_by || 'AI'}</dd>
            </div>
            {grade.reasoning && (
              <div className="pt-2 border-t border-gray-100">
                <dt className="text-gray-400 mb-1">Catatan</dt>
                <dd className="text-xs text-gray-600 leading-relaxed">{grade.reasoning}</dd>
              </div>
            )}
          </dl>
          <button onClick={onClose}
            className="mt-4 w-full py-2 text-sm font-medium text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg">
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}
