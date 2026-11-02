import { acceptHMRUpdate, defineStore } from 'pinia'
import { errorMessage } from '../api/http'

let nextId = 1
const timers = new Map()

// Toast messages close automatically: success/info after 4 s, errors after 6 s.
// Each toast also stores its expiry time, so App.vue can remove any toast whose
// timer was lost (e.g. after a hot reload or when the tab was asleep).
export const useToast = defineStore('toast', {
  state: () => ({ items: [] }),
  actions: {
    push(message, type = 'success', timeout = 4000) {
      const id = nextId++
      this.items.push({ id, message, type, timeout, expires: Date.now() + timeout })
      timers.set(id, setTimeout(() => this.dismiss(id), timeout))
      if (this.items.length > 4) this.dismiss(this.items[0].id)
    },
    success(message) { this.push(message, 'success') },
    error(errOrMessage) {
      this.push(typeof errOrMessage === 'string' ? errOrMessage : errorMessage(errOrMessage), 'error', 6000)
    },
    info(message) { this.push(message, 'info') },
    dismiss(id) {
      clearTimeout(timers.get(id)); timers.delete(id)
      this.items = this.items.filter((t) => t.id !== id)
    },
    prune() {
      const now = Date.now()
      if (this.items.some((t) => t.expires <= now)) this.items.filter((t) => t.expires <= now).forEach((t) => this.dismiss(t.id))
    },
    clear() { [...this.items].forEach((t) => this.dismiss(t.id)) },
  },
})

if (import.meta.hot) import.meta.hot.accept(acceptHMRUpdate(useToast, import.meta.hot))
