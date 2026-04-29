'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/api'

export default function HomePage() {
  const router = useRouter()
  useEffect(() => {
    router.push(isAuthenticated() ? '/pickups' : '/login')
  }, [router])
  return null
}
