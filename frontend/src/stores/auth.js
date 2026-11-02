import { defineStore } from 'pinia'
import http, { tokens } from '../api/http'

export const useAuth = defineStore('auth', {
  state: () => ({ user: null, loaded: false }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    permissions: (s) => new Set(s.user?.permissions || []),
  },
  actions: {
    can(...perms) { return perms.every((p) => this.permissions.has(p)) },
    canAny(...perms) { return perms.some((p) => this.permissions.has(p)) },
    async init() {
      if (this.loaded) return
      if (tokens.access) {
        try { this.user = (await http.get('/auth/me')).data } catch { this.user = null }
      }
      this.loaded = true
    },
    setSession(data) {
      tokens.set(data.access_token, data.refresh_token)
      this.user = data.user
      this.loaded = true
    },
    async login(email, password) {
      const { data } = await http.post('/auth/login', { email, password })
      if (data.mfa_required) return data
      this.setSession(data)
      return data
    },
    async verifyMfa(mfaToken, code) {
      const { data } = await http.post('/auth/mfa/verify', { mfa_token: mfaToken, code })
      this.setSession(data)
      return data
    },
    async refreshMe() { this.user = (await http.get('/auth/me')).data },
    async logout() {
      try { await http.post('/auth/logout', { refresh_token: tokens.refresh }) } catch { /* ignore */ }
      this.clear()
    },
    clear() {
      tokens.set(null, null)
      this.user = null
    },
  },
})
