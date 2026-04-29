'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { fetchPickup, getFileUrl, updatePickupStatus, isAuthenticated } from '@/lib/api'
import { Sidebar } from '@/components/Sidebar'
import { StatusBadge, GradeBadge } from '@/components/StatusBadge'
import { format } from 'date-fns'
import { id as localeId } from 'date-fns/locale'
import { ArrowLeft, MapPin, Recycle, Calendar, CheckCircle2, XCircle } from 'lucide-react'
import Link from 'next/link'
import Image from 'next/image'

type Grade = {
  grade: string
  confidence: number
  reasoning: string
  estimated_kg: number
  graded_by: string
  created_at: string
}

type File = {
  id: string
  file_path: string
  file_name: string
  created_at: string
  grade?: Grade
}

type Pickup = {
  id: string
  user_id: string
  location: string
  waste_type: string
  status: string
  notes: string | null
  estimated_weight: number | null
  created_at: string
  updated_at: string | null
  files: File[]
}

export default function PickupDetailPage() {
  const router = useRouter()
  const params = useParams()
  const id = params?.id as string

  const [pickup, setPickup] = useState<Pickup | null>(null)
  const [loading, setLoading] = useState(true)
  const [fileUrls, setFileUrls] = useState<Record<string, string>>({})
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    loadPickup()
  }, [id])

  async function loadPickup() {
    setLoading(true)
    try {
      const data = await fetchPickup(id)
      setPickup(data)

      // Load presigned URLs for each file
      const urls: Record<string, string> = {}
      for (const f of data.files) {
        try {
          urls[f.id] = await getFileUrl(f.id)
        } catch {
          urls[f.id] = ''
        }
      }
      setFileUrls(urls)
    } finally {
      setLoading(false)
    }
  }

  async function handleStatusChange(newStatus: string) {
    if (!pickup) return
    setUpdating(true)
    try {
      await updatePickupStatus(pickup.id, newStatus)
      await loadPickup()
    } finally {
      setUpdating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
        </main>
      </div>
    )
  }

  if (!pickup) {
    return (
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-gray-400">Pickup tidak ditemukan</p>
        </main>
      </div>
    )
  }

  const latestFile = pickup.files[pickup.files.length - 1]
  const grade = latestFile?.grade

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8 max-w-4xl">
        {/* Back */}
        <Link
          href="/pickups"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6"
        >
          <ArrowLeft className="w-4 h-4" /> Kembali ke daftar
        </Link>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              Pickup #{pickup.id.slice(0, 8).toUpperCase()}
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Dibuat {format(new Date(pickup.created_at), 'd MMMM yyyy, HH:mm', { locale: localeId })}
            </p>
          </div>
          <StatusBadge status={pickup.status} />
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Left: Pickup Info */}
          <div className="space-y-4">
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Informasi Pickup</h3>
              <dl className="space-y-3">
                <div className="flex items-start gap-3">
                  <MapPin className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <dt className="text-xs text-gray-400">Lokasi</dt>
                    <dd className="text-sm text-gray-800">{pickup.location}</dd>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Recycle className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <dt className="text-xs text-gray-400">Jenis Sampah</dt>
                    <dd className="text-sm text-gray-800">{pickup.waste_type}</dd>
                  </div>
                </div>
                {pickup.estimated_weight && (
                  <div className="flex items-start gap-3">
                    <Calendar className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <dt className="text-xs text-gray-400">Estimasi Berat</dt>
                      <dd className="text-sm text-gray-800">{pickup.estimated_weight} kg</dd>
                    </div>
                  </div>
                )}
              </dl>
            </div>

            {/* Operator Actions */}
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Aksi Operator</h3>
              <div className="space-y-2">
                {pickup.status === 'pending' && (
                  <button
                    onClick={() => handleStatusChange('confirmed')}
                    disabled={updating}
                    className="w-full btn-primary flex items-center justify-center gap-2 text-sm"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Konfirmasi Pickup
                  </button>
                )}
                {pickup.status === 'graded' && (
                  <button
                    onClick={() => handleStatusChange('completed')}
                    disabled={updating}
                    className="w-full btn-primary flex items-center justify-center gap-2 text-sm"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Tandai Selesai
                  </button>
                )}
                {!['completed', 'cancelled'].includes(pickup.status) && (
                  <button
                    onClick={() => handleStatusChange('cancelled')}
                    disabled={updating}
                    className="w-full btn-secondary flex items-center justify-center gap-2 text-sm text-red-500 hover:bg-red-50"
                  >
                    <XCircle className="w-4 h-4" />
                    Batalkan
                  </button>
                )}
                {['completed', 'cancelled'].includes(pickup.status) && (
                  <p className="text-sm text-gray-400 text-center py-2">
                    Tidak ada aksi tersedia
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Right: Photo + Grade */}
          <div className="space-y-4">
            {/* Photo */}
            {latestFile && (
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Foto Sampah</h3>
                {fileUrls[latestFile.id] ? (
                  <div className="relative w-full aspect-square rounded-lg overflow-hidden bg-gray-100">
                    <img
                      src={fileUrls[latestFile.id]}
                      alt="Waste photo"
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="w-full aspect-square rounded-lg bg-gray-100 flex items-center justify-center">
                    <p className="text-sm text-gray-400">Foto tidak tersedia</p>
                  </div>
                )}
              </div>
            )}

            {/* Grade Result */}
            {grade ? (
              <div className="card">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-700">Hasil Penilaian AI</h3>
                  <GradeBadge grade={grade.grade} />
                </div>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Keyakinan</dt>
                    <dd className="text-gray-800 font-medium">
                      {Math.round(grade.confidence * 100)}%
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Estimasi Berat</dt>
                    <dd className="text-gray-800 font-medium">{grade.estimated_kg} kg</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-400">Dinilai oleh</dt>
                    <dd className="text-gray-800">{grade.graded_by}</dd>
                  </div>
                  {grade.reasoning && (
                    <div className="pt-2 border-t border-gray-50">
                      <dt className="text-gray-400 mb-1">Catatan</dt>
                      <dd className="text-gray-700 text-xs leading-relaxed">{grade.reasoning}</dd>
                    </div>
                  )}
                </dl>
              </div>
            ) : (
              pickup.status === 'grading' && (
                <div className="card flex items-center gap-3">
                  <div className="w-5 h-5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                  <p className="text-sm text-gray-600">AI sedang menilai kualitas sampah...</p>
                </div>
              )
            )}

            {/* No photo yet */}
            {pickup.files.length === 0 && (
              <div className="card text-center py-8">
                <p className="text-sm text-gray-400">Belum ada foto diunggah</p>
                <p className="text-xs text-gray-300 mt-1">
                  User perlu mengirim foto via WhatsApp
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
