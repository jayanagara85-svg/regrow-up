import axios from 'axios'
import Cookies from 'js-cookie'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
})

// ─── Auth helpers ─────────────────────────────────────────────────────────────

export function getToken(): string | undefined {
  return Cookies.get('regrow_token')
}

export function setToken(token: string) {
  Cookies.set('regrow_token', token, { expires: 1 }) // 1 day
}

export function clearToken() {
  Cookies.remove('regrow_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

// ─── Axios interceptor — attach JWT ───────────────────────────────────────────

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearToken()
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

// ─── API calls ────────────────────────────────────────────────────────────────

export async function login(phone: string, password: string) {
  const res = await api.post('/api/auth/login', { phone, password })
  return res.data
}

export async function fetchPickups(page = 1, status?: string) {
  const params: Record<string, unknown> = { page, limit: 20 }
  if (status) params.status = status
  const res = await api.get('/api/pickups', { params })
  return res.data
}

export async function fetchPickup(id: string) {
  const res = await api.get(`/api/pickups/${id}`)
  return res.data
}

export async function updatePickupStatus(id: string, status: string) {
  const res = await api.patch(`/api/pickups/${id}`, { status })
  return res.data
}

export async function getFileUrl(fileId: string): Promise<string> {
  const res = await api.get(`/api/files/${fileId}/url`)
  return res.data.url
}

export async function getJobStatus(jobId: string) {
  const res = await api.get(`/api/files/job/${jobId}`)
  return res.data
}
