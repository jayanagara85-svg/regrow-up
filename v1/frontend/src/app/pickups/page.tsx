'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { fetchPickups, isAuthenticated } from '@/lib/api'
import { Sidebar } from '@/components/Sidebar'
import { StatusBadge } from '@/components/StatusBadge'
import { format } from 'date-fns'
import { id as localeId } from 'date-fns/locale'
import { RefreshCw, ChevronRight, Search } from 'lucide-react'

type Pickup = {
  id: string
  user_id: string
  location: string
  waste_type: string
  status: string
  created_at: string
}

type Paginated = {
  items: Pickup[]
  total: number
  page: number
  limit: number
}

const STATUS_OPTIONS = ['', 'pending', 'confirmed', 'grading', 'graded', 'completed', 'cancelled']
const STATUS_LABELS: Record<string, string> = {
  '': 'Semua',
  pending: 'Menunggu',
  confirmed: 'Dikonfirmasi',
  grading: 'Sedang Dinilai',
  graded: 'Selesai Dinilai',
  completed: 'Selesai',
  cancelled: 'Dibatalkan',
}

export default function PickupsPage() {
  const router = useRouter()
  const [data, setData] = useState<Paginated | null>(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login')
      return
    }
    loadPickups()
  }, [page, statusFilter])

  async function loadPickups() {
    setLoading(true)
    try {
      const result = await fetchPickups(page, statusFilter || undefined)
      setData(result)
    } catch {
      // redirect to login handled by api interceptor
    } finally {
      setLoading(false)
    }
  }

  const filtered = data?.items.filter(
    (p) =>
      !search ||
      p.location.toLowerCase().includes(search.toLowerCase()) ||
      p.waste_type.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Pickup Sampah</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {data?.total ?? 0} total pickup
            </p>
          </div>
          <button
            onClick={loadPickups}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6 flex-wrap">
          {/* Status filter tabs */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => { setStatusFilter(s); setPage(1) }}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari lokasi atau jenis..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-20 text-gray-400">
              <p className="text-lg">Tidak ada pickup</p>
              <p className="text-sm mt-1">Booking dari WhatsApp akan muncul di sini</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Lokasi</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Jenis Sampah</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Tanggal</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((pickup) => (
                  <tr key={pickup.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-400">
                      {pickup.id.slice(0, 8).toUpperCase()}
                    </td>
                    <td className="px-4 py-3 text-gray-700 max-w-[200px] truncate">
                      {pickup.location}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{pickup.waste_type}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={pickup.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {format(new Date(pickup.created_at), 'd MMM yyyy, HH:mm', { locale: localeId })}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/pickups/${pickup.id}`}
                        className="text-brand-600 hover:text-brand-700 flex items-center gap-1"
                      >
                        Detail <ChevronRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {data && data.total > data.limit && (
          <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
            <span>
              Showing {(page - 1) * data.limit + 1}–
              {Math.min(page * data.limit, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-40"
              >
                ← Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * data.limit >= data.total}
                className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
