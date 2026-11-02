import axios from 'axios'
import { i18n, serverText, t } from '../i18n'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

// A simple device fingerprint sent with every request (recorded in the audit trail).
function fingerprint() {
  let fp = null
  try { fp = localStorage.getItem('bh_fp') } catch { /* storage blocked */ }
  if (!fp) {
    const raw = [navigator.userAgent, screen.width, screen.height, Intl.DateTimeFormat().resolvedOptions().timeZone,
      navigator.language].join('|')
    let h = 0
    for (let i = 0; i < raw.length; i++) h = (Math.imul(31, h) + raw.charCodeAt(i)) | 0
    fp = 'fp-' + (h >>> 0).toString(16) + '-' + Math.random().toString(16).slice(2, 8)
    try { localStorage.setItem('bh_fp', fp) } catch { /* ignore */ }
  }
  return fp
}

const tokens = {
  get access() { try { return localStorage.getItem('bh_access') } catch { return null } },
  get refresh() { try { return localStorage.getItem('bh_refresh') } catch { return null } },
  set(access, refresh) {
    try {
      if (access) localStorage.setItem('bh_access', access); else localStorage.removeItem('bh_access')
      if (refresh) localStorage.setItem('bh_refresh', refresh); else localStorage.removeItem('bh_refresh')
    } catch { /* ignore */ }
  }
}

http.interceptors.request.use((config) => {
  if (tokens.access) config.headers.Authorization = `Bearer ${tokens.access}`
  config.headers['X-Device-Fingerprint'] = fingerprint()
  config.headers['Accept-Language'] = i18n.locale
  return config
})

let refreshing = null
let onLogout = () => {}

http.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config || {}
    const status = error.response?.status
    const isAuthCall = (original.url || '').startsWith('/auth/')
    if (status === 401 && !original._retried && !isAuthCall && tokens.refresh) {
      original._retried = true
      try {
        refreshing = refreshing || axios.post('/api/auth/refresh', { refresh_token: tokens.refresh })
        const { data } = await refreshing
        tokens.set(data.access_token, data.refresh_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return http(original)
      } catch (e) {
        tokens.set(null, null)
        onLogout()
      } finally {
        refreshing = null
      }
    } else if (status === 401 && !isAuthCall) {
      tokens.set(null, null)
      onLogout()
    }
    return Promise.reject(error)
  }
)

export function errorMessage(err) {
  const data = err?.response?.data
  if (data && typeof data === 'object' && data.message) return serverText(data.message)
  if (err?.response?.status === 413) return t('errors.tooLarge')
  if (err?.code === 'ERR_NETWORK' || (err?.response?.status >= 500 && !(data && data.message))) {
    return t('errors.noApi')
  }
  return err?.message || t('errors.generic')
}

// Download a protected file (PDF/CSV/ICS) using the JWT, then save it.
export async function downloadFile(url, fallbackName = 'download') {
  let res
  try {
    res = await http.get(url, { responseType: 'blob' })
  } catch (err) {
    const blob = err?.response?.data
    if (blob instanceof Blob) {
      try { err.response.data = JSON.parse(await blob.text()) } catch { /* not JSON */ }
    }
    window.dispatchEvent(new CustomEvent('bh:error', { detail: errorMessage(err) }))
    return false
  }
  const cd = res.headers['content-disposition'] || ''
  const match = /filename="?([^";]+)"?/i.exec(cd)
  const name = match ? match[1] : fallbackName
  const href = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 2000)
  return true
}

export function setLogoutHandler(fn) { onLogout = fn }
export { tokens }
export default http
