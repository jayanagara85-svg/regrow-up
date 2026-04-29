/**
 * CHANNEL.HTML + BROADCAST.HTML — PATCHES
 * Both pages need auth guard + real API calls.
 */


// ═══════════════════════════════════════════════════════════════════════════
// CHANNEL PAGE PATCH
// Replace ChannelPage() function body
// ═══════════════════════════════════════════════════════════════════════════

function ChannelPage() {
  const { useState, useEffect, useMemo } = React;

  useEffect(() => { window.API.auth.requireAuth(); }, []);

  const [posts,          setPosts]          = useState([]);
  const [loading,        setLoading]        = useState(true);
  const [composerOpen,   setComposerOpen]   = useState(false);
  const [editing,        setEditing]        = useState(null);
  const [confirm,        setConfirm]        = useState(null);
  const [removingIds,    setRemovingIds]    = useState(new Set());
  const [search,         setSearch]         = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [toast,          setToast]          = useState(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  // ── Load posts ──────────────────────────────────────────────────────────
  const loadPosts = async () => {
    setLoading(true);
    try {
      const data = await window.API.channel.list({ limit: 50 });
      setPosts(data || []);
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal memuat posts' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadPosts(); }, []);

  // ── Filter ──────────────────────────────────────────────────────────────
  const filtered = useMemo(() =>
    posts
      .filter(p => categoryFilter === 'all' || p.category === categoryFilter)
      .filter(p => !search ||
        p.title?.toLowerCase().includes(search.toLowerCase()) ||
        p.content?.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => {
        if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
        return new Date(b.created_at) - new Date(a.created_at);
      }),
    [posts, categoryFilter, search]
  );

  const stats = useMemo(() => ({
    total:  posts.length,
    pinned: posts.filter(p => p.is_pinned).length,
    views:  posts.reduce((s, p) => s + (p.views || 0), 0),
  }), [posts]);

  // ── Toggle pin ──────────────────────────────────────────────────────────
  const togglePin = async (post) => {
    try {
      const updated = await window.API.channel.togglePin(post.id, post.is_pinned);
      setPosts(prev => prev.map(p => p.id === post.id ? updated : p));
      setToast({ kind:'success', msg: post.is_pinned ? 'Post di-unpin' : 'Post berhasil di-pin' });
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal update pin' });
    }
  };

  // ── Delete ──────────────────────────────────────────────────────────────
  const requestDelete = (post) => {
    setConfirm({
      title: 'Hapus post?',
      body: `"${post.title}" akan dihapus permanen.`,
      danger: true,
      onConfirm: () => doDelete(post),
    });
  };

  const doDelete = async (post) => {
    setConfirm(null);
    setRemovingIds(prev => new Set(prev).add(post.id));
    try {
      await window.API.channel.delete(post.id);
      // Short delay for remove animation
      setTimeout(() => {
        setPosts(prev => prev.filter(p => p.id !== post.id));
        setRemovingIds(prev => { const n = new Set(prev); n.delete(post.id); return n; });
        setToast({ kind:'success', msg: 'Post berhasil dihapus' });
      }, 250);
    } catch (e) {
      setRemovingIds(prev => { const n = new Set(prev); n.delete(post.id); return n; });
      setToast({ kind:'error', msg: e.message || 'Gagal menghapus post' });
    }
  };

  // ── Create / Edit ────────────────────────────────────────────────────────
  const submitPost = async (data) => {
    const user = window.API.auth.getUser();
    try {
      if (editing) {
        const updated = await window.API.channel.update(editing.id, {
          title:     data.title,
          content:   data.content,   // backend uses 'content', not 'body'
          category:  data.category,
          is_pinned: data.is_pinned ?? editing.is_pinned,
        });
        setPosts(prev => prev.map(p => p.id === editing.id ? updated : p));
        setToast({ kind:'success', msg: 'Post berhasil diperbarui' });
        setEditing(null);
      } else {
        const created = await window.API.channel.create({
          title:     data.title,
          content:   data.content,
          category:  data.category || 'info',
          is_pinned: data.is_pinned || false,
          author_id: user?.id || null,
        });
        setPosts(prev => [created, ...prev]);
        setToast({ kind:'success', msg: 'Post berhasil dipublikasikan' });
      }
      setComposerOpen(false);
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal simpan post' });
    }
  };

  // ── Note on schema difference ────────────────────────────────────────────
  // Mock uses: { body, published_at, pinned, likes }
  // Real API uses: { content, created_at, is_pinned, views }
  // The PostCard component below adapts to real schema.

  return (
    <div className="flex min-h-screen">
      <Sidebar active="channel"/>
      <main className="flex-1 min-w-0">
        <header className="h-16 px-8 bg-white/70 backdrop-blur border-b border-gray-100 flex items-center justify-between sticky top-0 z-20">
          <div>
            <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">
              {new Date().toLocaleDateString('id-ID', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}
            </div>
            <h1 className="text-[15px] font-semibold text-gray-900 leading-tight">Channel</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden md:block">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari post…"
                className="w-64 pl-9 pr-3 py-2 text-sm bg-gray-50 border border-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white"/>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-6">
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Channel Berita</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                {stats.total} post · {stats.pinned} di-pin · {stats.views.toLocaleString('id-ID')} total views
              </p>
            </div>
            <button onClick={() => { setEditing(null); setComposerOpen(true); }}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition shadow-sm shadow-brand-600/20">
              <Plus size={14}/> Post Baru
            </button>
          </div>

          {/* Category filter */}
          <div className="card p-3 flex items-center gap-2 flex-wrap">
            {['all', 'announcement', 'tips', 'event', 'impact', 'info'].map(cat => (
              <button key={cat} onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                  categoryFilter === cat ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}>
                {{all:'Semua', announcement:'Pengumuman', tips:'Tips', event:'Acara', impact:'Dampak', info:'Info'}[cat] || cat}
              </button>
            ))}
          </div>

          {loading && posts.length === 0 && (
            <div className="text-center py-12">
              <div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"/>
              <p className="text-sm text-gray-400">Memuat posts…</p>
            </div>
          )}

          <div className="space-y-4">
            {filtered.map(post => (
              <PostCard
                key={post.id}
                post={post}
                removing={removingIds.has(post.id)}
                onTogglePin={() => togglePin(post)}
                onEdit={() => { setEditing(post); setComposerOpen(true); }}
                onDelete={() => requestDelete(post)}
              />
            ))}
            {!loading && filtered.length === 0 && (
              <div className="text-center py-16 text-sm text-gray-400">
                Belum ada post{categoryFilter !== 'all' ? ` dengan kategori "${categoryFilter}"` : ''}
              </div>
            )}
          </div>
        </div>

        {/* Composer modal — reuse existing PostComposer component (change body→content, published_at→created_at) */}
        {composerOpen && (
          <PostComposer
            post={editing}
            onClose={() => { setComposerOpen(false); setEditing(null); }}
            onSubmit={submitPost}
          />
        )}

        {/* Confirm dialog */}
        {confirm && (
          <ConfirmDialog {...confirm} onCancel={() => setConfirm(null)}/>
        )}

        {toast && (
          <div className={`fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm font-medium text-white shadow-lg toast z-50 ${toast.kind === 'success' ? 'bg-brand-600' : 'bg-rose-500'}`}>
            {toast.msg}
          </div>
        )}
      </main>
    </div>
  );
}

// ── PostCard — adapts mock fields to real schema ──────────────────────────────
// Mock: { body, published_at, pinned, likes }
// Real: { content, created_at, is_pinned, views }

function PostCard({ post, removing, onTogglePin, onEdit, onDelete }) {
  const CATEGORY_COLORS = {
    announcement: 'bg-amber-100 text-amber-800',
    tips:         'bg-blue-100 text-blue-800',
    event:        'bg-violet-100 text-violet-800',
    impact:       'bg-brand-100 text-brand-800',
    info:         'bg-gray-100 text-gray-700',
  };
  return (
    <div className={`card p-5 anim-in ${removing ? 'removing' : ''}`}>
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            {post.is_pinned && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                📌 Di-pin
              </span>
            )}
            <span className={`badge ${CATEGORY_COLORS[post.category] || 'bg-gray-100 text-gray-700'}`}>
              {post.category}
            </span>
            <span className="text-[11px] text-gray-400">{window.formatRelative(post.created_at)}</span>
          </div>
          <h3 className="font-semibold text-gray-900 mb-1">{post.title}</h3>
          <p className="text-sm text-gray-500 line-clamp-2">{post.content}</p>
          <div className="flex items-center gap-3 mt-3 text-[11px] text-gray-400">
            <span>{post.views || 0} views</span>
            {post.author && <span>oleh {post.author?.name || 'Admin'}</span>}
          </div>
        </div>
        <div className="flex flex-col gap-1.5 flex-shrink-0">
          <button onClick={onTogglePin}
            className={`p-1.5 rounded-lg text-xs transition ${post.is_pinned ? 'bg-amber-50 text-amber-600 hover:bg-amber-100' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'}`}
            title={post.is_pinned ? 'Unpin' : 'Pin'}>
            📌
          </button>
          <button onClick={onEdit} className="p-1.5 rounded-lg bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600 text-xs transition" title="Edit">
            ✏️
          </button>
          <button onClick={onDelete} className="p-1.5 rounded-lg bg-gray-50 text-gray-400 hover:bg-rose-50 hover:text-rose-500 text-xs transition" title="Hapus">
            🗑️
          </button>
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════
// BROADCAST PAGE PATCH
// ═══════════════════════════════════════════════════════════════════════════

function BroadcastPage() {
  const { useState, useEffect, useMemo } = React;

  useEffect(() => { window.API.auth.requireAuth(); }, []);

  // ── State ─────────────────────────────────────────────────────────────────
  const [communities,  setCommunities]  = useState([]);
  const [selectedId,   setSelectedId]   = useState(null);
  const [history,      setHistory]      = useState([]);   // local history (no endpoint)
  const [loading,      setLoading]      = useState(true);
  const [sending,      setSending]      = useState(false);
  const [text,         setText]         = useState('');
  const [toast,        setToast]        = useState(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  // ── Load communities ──────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await window.API.community.list();
        setCommunities(data || []);
        if (data?.length) setSelectedId(data[0].id);
      } catch (e) {
        setToast({ kind:'error', msg: e.message || 'Gagal memuat komunitas' });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selected = communities.find(c => c.id === selectedId);

  // ── Send broadcast ────────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!text.trim() || !selectedId) return;
    setSending(true);
    try {
      const result = await window.API.community.broadcast(selectedId, text.trim());
      // result: { sent_to: number, message: string }
      const entry = {
        id: 'b' + Date.now(),
        community_id: selectedId,
        community_name: selected?.name || selectedId,
        text: text.trim(),
        sent_at: new Date().toISOString(),
        delivered: result.sent_to,
        read: 0,
      };
      setHistory(h => [entry, ...h]);
      setText('');
      setToast({ kind:'success', msg: `Broadcast terkirim ke ${result.sent_to} anggota` });
    } catch (e) {
      setToast({ kind:'error', msg: e.message || 'Gagal kirim broadcast' });
    } finally {
      setSending(false);
    }
  };

  const filteredHistory = history
    .filter(h => !selectedId || h.community_id === selectedId)
    .sort((a, b) => new Date(b.sent_at) - new Date(a.sent_at));

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin"/>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar active="broadcast"/>
      <main className="flex-1 min-w-0">
        <header className="h-16 px-8 bg-white/70 backdrop-blur border-b border-gray-100 flex items-center justify-between sticky top-0 z-20">
          <div>
            <div className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">
              {new Date().toLocaleDateString('id-ID', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}
            </div>
            <h1 className="text-[15px] font-semibold text-gray-900 leading-tight">Broadcast</h1>
          </div>
        </header>

        <div className="p-8 space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Broadcast Pesan</h2>
            <p className="text-sm text-gray-500 mt-0.5">Kirim pesan WhatsApp massal ke anggota komunitas</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

            {/* Compose form */}
            <div className="lg:col-span-5 card p-5 space-y-4">
              <h3 className="text-sm font-semibold text-gray-800">Kirim Broadcast Baru</h3>

              {/* Community selector */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1.5">Komunitas Tujuan</label>
                {communities.length === 0 ? (
                  <p className="text-xs text-gray-400">Belum ada komunitas. Buat komunitas dahulu.</p>
                ) : (
                  <div className="space-y-2">
                    {communities.map(c => (
                      <button key={c.id} onClick={() => setSelectedId(c.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm border transition ${
                          selectedId === c.id
                            ? 'border-brand-300 bg-brand-50 text-brand-800'
                            : 'border-gray-200 hover:border-brand-200 text-gray-700'
                        }`}>
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-base ${selectedId === c.id ? 'bg-brand-100' : 'bg-gray-100'}`}>
                          🏘️
                        </div>
                        <div className="flex-1 text-left min-w-0">
                          <div className="text-xs font-semibold truncate">{c.name}</div>
                          <div className="text-[10px] text-gray-400">{c.area || 'Area tidak diset'}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Message */}
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1.5">Pesan</label>
                <textarea rows={4} value={text} onChange={e => setText(e.target.value)}
                  placeholder="Tulis pesan WhatsApp yang akan dikirim ke semua anggota…"
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"/>
                <div className="text-right text-[11px] text-gray-400 mt-1">{text.length} karakter</div>
              </div>

              <button disabled={!text.trim() || !selectedId || sending} onClick={handleSend}
                className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold rounded-lg flex items-center justify-center gap-2 disabled:opacity-40 transition">
                {sending ? (
                  <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"/> Mengirim…</>
                ) : (
                  <><Megaphone size={14}/> Kirim ke {selected?.name || '–'}</>
                )}
              </button>
            </div>

            {/* History */}
            <div className="lg:col-span-7 card overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-50">
                <h3 className="text-sm font-semibold text-gray-800">
                  Riwayat Broadcast
                  <span className="ml-2 text-xs font-normal text-gray-400">(sesi ini)</span>
                </h3>
              </div>
              {filteredHistory.length === 0 ? (
                <div className="text-center py-12 text-sm text-gray-400">
                  Belum ada broadcast terkirim
                </div>
              ) : (
                <div className="divide-y divide-gray-50">
                  {filteredHistory.map(entry => (
                    <div key={entry.id} className="px-5 py-4">
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div className="text-xs font-medium text-gray-500">{entry.community_name}</div>
                        <div className="text-[11px] text-gray-400 whitespace-nowrap">{window.formatRelative(entry.sent_at)}</div>
                      </div>
                      <p className="text-sm text-gray-700 mb-2">{entry.text}</p>
                      <div className="flex items-center gap-3 text-[11px] text-gray-400">
                        <span className="inline-flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-brand-500 inline-block"/>
                          Terkirim ke {entry.delivered}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {toast && (
          <div className={`fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm font-medium text-white shadow-lg toast z-50 ${toast.kind === 'success' ? 'bg-brand-600' : 'bg-rose-500'}`}>
            {toast.msg}
          </div>
        )}
      </main>
    </div>
  );
}
