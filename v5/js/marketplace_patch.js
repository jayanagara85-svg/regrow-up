/**
 * MARKETPLACE.HTML — PATCH
 * Replace mock state + actions with real API calls.
 * All other code (icons, Sidebar, UI components, CSS) stays unchanged.
 */

// ─── STEP 1: Add <script src="js/api.js"></script> before babel script tag

// ─── STEP 2: Remove MOCK_LISTINGS, MOCK_BUYERS constants

// ─── STEP 3: Replace Marketplace() function with this:

function Marketplace() {
  const { useState, useEffect, useMemo } = React;

  // Auth guard
  useEffect(() => { window.API.auth.requireAuth(); }, []);

  // ── State ─────────────────────────────────────────────────────────────────
  const [listings,     setListings]     = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [statusFilter, setStatusFilter] = useState('open');
  const [typeFilter,   setTypeFilter]   = useState('all');
  const [search,       setSearch]       = useState('');
  const [matching,     setMatching]     = useState(null);   // listing being matched
  const [matchingId,   setMatchingId]   = useState(null);   // spinner target
  const [toast,        setToast]        = useState(null);
  const [composing,    setComposing]    = useState(false);  // new listing form

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  // ── Load listings ──────────────────────────────────────────────────────────
  const loadListings = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const data = await window.API.marketplace.list(params);
      setListings(data || []);
    } catch (e) {
      setError(e.message || 'Gagal memuat listing');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadListings(); }, [statusFilter]);

  // ── Filter locally ─────────────────────────────────────────────────────────
  const filtered = useMemo(() =>
    listings.filter(l =>
      (typeFilter === 'all' || l.waste_type?.toLowerCase().includes(typeFilter.toLowerCase())) &&
      (!search ||
        l.waste_type?.toLowerCase().includes(search.toLowerCase()) ||
        l.description?.toLowerCase().includes(search.toLowerCase()))
    ), [listings, typeFilter, search]
  );

  // ── Stats ─────────────────────────────────────────────────────────────────
  const stats = useMemo(() => ({
    open:      listings.filter(l => l.status === 'open').length,
    matched:   listings.filter(l => l.status === 'matched').length,
    completed: listings.filter(l => l.status === 'completed').length,
    totalKg:   listings.reduce((s, l) => s + (l.weight || 0), 0),
  }), [listings]);

  // ── Create listing ─────────────────────────────────────────────────────────
  const handleCreateListing = async ({ waste_type, weight, price_estimate, description }) => {
    try {
      const created = await window.API.marketplace.create({ waste_type, weight, price_estimate, description });
      setListings(prev => [created, ...prev]);
      setComposing(false);
      setToast({ kind:'success', msg:`Listing "${waste_type}" berhasil dibuat` });
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal membuat listing' });
    }
  };

  // ── Confirm match (operator selects buyer company name) ───────────────────
  const confirmMatch = async (listing, buyerName) => {
    setMatchingId(listing.id);
    try {
      const updated = await window.API.marketplace.updateStatus(listing.id, 'matched');
      // Note: buyer_name stored in description for now — see backend note below
      setListings(prev => prev.map(l =>
        l.id === listing.id ? { ...updated, buyer_name: buyerName } : l
      ));
      setMatching(null);
      setToast({ kind:'success', msg:`${listing.waste_type} dipasangkan ke ${buyerName}` });
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal pasangkan listing' });
    } finally {
      setMatchingId(null);
    }
  };

  // ── Mark as completed ─────────────────────────────────────────────────────
  const handleComplete = async (listingId) => {
    try {
      const updated = await window.API.marketplace.complete(listingId);
      setListings(prev => prev.map(l => l.id === listingId ? updated : l));
      setToast({ kind:'success', msg:'Listing ditandai selesai' });
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal update' });
    }
  };

  // ── Unique waste types for filter dropdown ────────────────────────────────
  const wasteTypes = useMemo(() =>
    ['all', ...new Set(listings.map(l => l.waste_type).filter(Boolean))],
    [listings]
  );

  if (loading && listings.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"/>
          <p className="text-sm text-gray-400">Memuat marketplace…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar active="marketplace"/>
      <main className="flex-1 min-w-0">

        <header className="h-16 px-8 bg-white/70 backdrop-blur border-b border-gray-100 flex items-center justify-between sticky top-0 z-20">
          <div>
            <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">
              {new Date().toLocaleDateString('id-ID', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}
            </div>
            <h1 className="text-[15px] font-semibold text-gray-900 leading-tight">Marketplace</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadListings} disabled={loading}
              className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1.5 text-gray-600">
              <RefreshCw size={12} className={loading ? 'spin' : ''}/>Refresh
            </button>
            <button onClick={() => setComposing(true)}
              className="px-3 py-1.5 text-xs bg-brand-600 hover:bg-brand-700 text-white rounded-lg flex items-center gap-1.5">
              <Plus size={12}/> Listing Baru
            </button>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* Stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label:'Tersedia',   value: stats.open,       color:'text-brand-600 bg-brand-50' },
              { label:'Dipasangkan',value: stats.matched,    color:'text-blue-600 bg-blue-50' },
              { label:'Selesai',    value: stats.completed,  color:'text-gray-600 bg-gray-50' },
              { label:'Total Kg',   value: `${stats.totalKg.toFixed(1)} kg`, color:'text-amber-600 bg-amber-50' },
            ].map(({ label, value, color }) => (
              <div key={label} className={`card p-4 ${color.split(' ')[1]}`}>
                <div className={`text-2xl font-bold ${color.split(' ')[0]} mb-1`}>{value}</div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
            ))}
          </div>

          {/* Filters */}
          <div className="card p-3 flex flex-wrap gap-3 items-center">
            {/* Status tabs */}
            <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
              {['open','matched','completed','all'].map(s => (
                <button key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition ${
                    statusFilter === s ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                  }`}>
                  {{open:'Tersedia', matched:'Dipasangkan', completed:'Selesai', all:'Semua'}[s]}
                </button>
              ))}
            </div>
            {/* Waste type */}
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-500">
              {wasteTypes.map(t => <option key={t} value={t}>{t === 'all' ? 'Semua Jenis' : t}</option>)}
            </select>
            {/* Search */}
            <div className="relative flex-1 min-w-[160px]">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"/>
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Cari listing…"
                className="w-full pl-7 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"/>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 flex items-center gap-2">
              <XCircle size={16}/> {error}
            </div>
          )}

          {/* Listings grid */}
          {loading && listings.length > 0 && (
            <div className="text-center py-4"><div className="w-5 h-5 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto"/></div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((listing, i) => (
              <ListingCard
                key={listing.id}
                listing={listing}
                index={i}
                onMatch={() => setMatching(listing)}
                onComplete={() => handleComplete(listing.id)}
                matching={matchingId === listing.id}
              />
            ))}
            {!loading && filtered.length === 0 && (
              <div className="col-span-full text-center py-16 text-sm text-gray-400">
                Tidak ada listing {statusFilter !== 'all' ? `dengan status "${statusFilter}"` : ''}
              </div>
            )}
          </div>
        </div>

        {/* Match modal */}
        {matching && (
          <MatchModal
            listing={matching}
            onClose={() => setMatching(null)}
            onConfirm={confirmMatch}
          />
        )}

        {/* Create listing modal */}
        {composing && (
          <CreateListingModal
            onClose={() => setComposing(false)}
            onSubmit={handleCreateListing}
          />
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

// ── ListingCard — updated to use real schema ──────────────────────────────────
// The real schema has: { id, user_id, waste_type, weight, price_estimate, status, created_at }
// No 'grade', 'origin', 'thumb' — we generate a color from waste_type hash

function ListingCard({ listing, index, onMatch, onComplete, matching }) {
  const STATUS_LABEL = { open:'Tersedia', matched:'Dipasangkan', completed:'Selesai', cancelled:'Dibatalkan' };
  const STATUS_COLOR = {
    open:      'bg-brand-50 text-brand-700 ring-brand-200/60',
    matched:   'bg-blue-50 text-blue-700 ring-blue-200/60',
    completed: 'bg-gray-50 text-gray-700 ring-gray-200/60',
    cancelled: 'bg-rose-50 text-rose-700 ring-rose-200/60',
  };
  const THUMB_COLORS = ['#a7f3d0','#bfdbfe','#fde68a','#fbcfe8','#ddd6fe','#fecaca','#d1fae5'];
  const thumbColor = THUMB_COLORS[listing.waste_type?.charCodeAt(0) % THUMB_COLORS.length] || '#e5e7eb';

  return (
    <div className="listing-card card overflow-hidden" style={{ animationDelay: `${index * 40}ms` }}>
      {/* Thumbnail placeholder */}
      <div className="h-32 flex items-center justify-center text-4xl textile-bg"
           style={{ background: `linear-gradient(135deg, ${thumbColor}55, ${thumbColor}22)` }}>
        ♻️
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">{listing.waste_type}</h3>
            <div className="text-xs text-gray-400 font-mono mt-0.5">{listing.id.slice(0,8).toUpperCase()}</div>
          </div>
          <span className={`badge ring-1 ring-inset ${STATUS_COLOR[listing.status] || 'bg-gray-50 text-gray-700 ring-gray-200/60'}`}>
            {STATUS_LABEL[listing.status] || listing.status}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs mb-3">
          <div className="text-gray-400">Berat</div>
          <div className="text-gray-700 font-medium text-right">{listing.weight ? `${listing.weight} kg` : '–'}</div>
          <div className="text-gray-400">Estimasi Harga</div>
          <div className="text-gray-700 font-medium text-right">{window.formatIDR(listing.price_estimate)}</div>
          <div className="text-gray-400">Dibuat</div>
          <div className="text-gray-400 text-right">{window.formatRelative(listing.created_at)}</div>
        </div>

        {listing.description && (
          <p className="text-[11px] text-gray-400 mb-3 truncate">{listing.description}</p>
        )}

        <div className="pt-2 border-t border-gray-50">
          {listing.status === 'open' && (
            <button onClick={onMatch} disabled={matching}
              className="w-full py-1.5 text-xs font-medium bg-brand-50 text-brand-700 hover:bg-brand-100 rounded-lg transition flex items-center justify-center gap-1.5">
              {matching ? <><RefreshCw size={10} className="spin"/>Memproses…</> : <><Sparkles size={10}/>Pasangkan Pembeli</>}
            </button>
          )}
          {listing.status === 'matched' && (
            <button onClick={onComplete}
              className="w-full py-1.5 text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg transition flex items-center justify-center gap-1.5">
              <CheckCircle size={10}/> Tandai Selesai
            </button>
          )}
          {listing.status === 'completed' && (
            <div className="text-center text-xs text-gray-400 py-1">Transaksi selesai</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── CreateListingModal ────────────────────────────────────────────────────────
function CreateListingModal({ onClose, onSubmit }) {
  const [form, setForm] = React.useState({ waste_type:'', weight:'', price_estimate:'', description:'' });
  const [submitting, setSubmitting] = React.useState(false);

  const handle = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        waste_type: form.waste_type,
        weight: form.weight ? parseFloat(form.weight) : null,
        price_estimate: form.price_estimate ? parseFloat(form.price_estimate) : null,
        description: form.description || null,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900 mb-4">Listing Baru</h3>
        <form onSubmit={handle} className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Jenis Sampah *</label>
            <input required value={form.waste_type} onChange={e => setForm(f => ({...f, waste_type: e.target.value}))}
              placeholder="Pakaian Bekas, Kain Perca, …"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"/>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Berat (kg)</label>
              <input type="number" step="0.1" value={form.weight} onChange={e => setForm(f => ({...f, weight: e.target.value}))}
                placeholder="0.0"
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"/>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Est. Harga (Rp)</label>
              <input type="number" value={form.price_estimate} onChange={e => setForm(f => ({...f, price_estimate: e.target.value}))}
                placeholder="0"
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"/>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Deskripsi</label>
            <textarea rows={2} value={form.description} onChange={e => setForm(f => ({...f, description: e.target.value}))}
              placeholder="Kondisi, asal, info tambahan…"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"/>
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Batal</button>
            <button type="submit" disabled={submitting}
              className="flex-1 py-2 text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg disabled:opacity-50">
              {submitting ? 'Membuat…' : 'Buat Listing'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── MatchModal — updated for real flow ────────────────────────────────────────
// Since we don't have a buyers table yet, operator types buyer name manually
function MatchModal({ listing, onClose, onConfirm }) {
  const [buyerName, setBuyerName] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  const SUGGESTED_BUYERS = [
    'CV Tekstil Berkah', 'Re-Wear Studio', 'PT Daur Serat', 'Tekstil Daur Hijau',
  ];

  const submit = async () => {
    if (!buyerName.trim()) return;
    setSubmitting(true);
    await onConfirm(listing, buyerName.trim());
    setSubmitting(false);
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-5" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900 mb-1">Pasangkan Pembeli</h3>
        <p className="text-xs text-gray-400 mb-4">{listing.waste_type} · {listing.weight || '?'} kg</p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Nama Pembeli</label>
            <input value={buyerName} onChange={e => setBuyerName(e.target.value)}
              placeholder="Ketik nama perusahaan pembeli…"
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"/>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_BUYERS.map(b => (
              <button key={b} onClick={() => setBuyerName(b)}
                className={`px-2.5 py-1 text-[11px] rounded-full border transition ${buyerName === b ? 'bg-brand-50 border-brand-300 text-brand-700' : 'border-gray-200 text-gray-500 hover:border-brand-200'}`}>
                {b}
              </button>
            ))}
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={onClose} className="flex-1 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Batal</button>
            <button disabled={!buyerName.trim() || submitting} onClick={submit}
              className="flex-1 py-2 text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg disabled:opacity-50">
              {submitting ? 'Memproses…' : 'Konfirmasi Match'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
