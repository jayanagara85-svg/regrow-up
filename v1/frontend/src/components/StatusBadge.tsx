type Status = 'pending' | 'confirmed' | 'grading' | 'graded' | 'completed' | 'cancelled'

const config: Record<Status, { label: string; classes: string }> = {
  pending:   { label: 'Menunggu',   classes: 'bg-yellow-100 text-yellow-700' },
  confirmed: { label: 'Dikonfirmasi', classes: 'bg-blue-100 text-blue-700' },
  grading:   { label: 'Dinilai',    classes: 'bg-purple-100 text-purple-700' },
  graded:    { label: 'Selesai Dinilai', classes: 'bg-teal-100 text-teal-700' },
  completed: { label: 'Selesai',    classes: 'bg-brand-100 text-brand-700' },
  cancelled: { label: 'Dibatalkan', classes: 'bg-red-100 text-red-700' },
}

export function StatusBadge({ status }: { status: string }) {
  const s = config[status as Status] ?? { label: status, classes: 'bg-gray-100 text-gray-700' }
  return (
    <span className={`badge ${s.classes}`}>{s.label}</span>
  )
}

export function GradeBadge({ grade }: { grade: string }) {
  const colors: Record<string, string> = {
    A: 'bg-green-100 text-green-700',
    B: 'bg-blue-100 text-blue-700',
    C: 'bg-yellow-100 text-yellow-700',
    D: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`badge text-sm font-bold ${colors[grade] || 'bg-gray-100 text-gray-700'}`}>
      Grade {grade}
    </span>
  )
}
