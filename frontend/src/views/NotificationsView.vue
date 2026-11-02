<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('notifications.title') }}</h1><p>{{ $t('notifications.subtitle') }}</p></div>
      <div class="actions">
        <label class="check"><input v-model="unreadOnly" type="checkbox" @change="load" />{{ $t('notifications.unreadOnly') }}</label>
        <button v-if="auth.can('meeting.update')" class="btn" @click="runReminders"><Icon name="refresh" />{{ $t('notifications.sendReminders') }}</button>
        <button class="btn" :disabled="!unread" @click="readAll">{{ $t('notifications.markAll') }}</button>
      </div>
    </div>
    <div class="card">
      <div v-if="!items.length" class="empty">{{ $t('notifications.caughtUp') }}</div>
      <ul v-else class="list">
        <li v-for="n in items" :key="n.id" class="row between" :style="{ opacity: n.read ? .65 : 1 }">
          <div class="row" style="align-items: flex-start; flex-wrap: nowrap">
            <span class="avatar" :style="{ background: n.read ? '#f1f5f9' : 'var(--primary-50)' }"><Icon :name="icon(n.kind)" :size="16" /></span>
            <div>
              <b>{{ notificationText(n.title) }}</b> <span v-if="!n.read" class="badge primary">{{ $t('notifications.new') }}</span>
              <div class="small">{{ notificationText(n.body) }}</div>
              <div class="small muted">{{ fmtDateTime(n.created_at) }} · {{ label(n.kind) }}</div>
            </div>
          </div>
          <div class="actions">
            <button v-if="n.link" class="btn sm" @click="open(n)">{{ $t('common.open') }}</button>
            <button v-if="!n.read" class="btn sm ghost" @click="markRead(n)">{{ $t('notifications.markRead') }}</button>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import Icon from '../components/Icon.vue'
import { notificationText, t } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { fmtDateTime, label } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const router = useRouter()
const items = ref([])
const unread = ref(0)
const unreadOnly = ref(false)
const icons = { invitation: 'calendar', reminder: 'bell', vote: 'vote', absence: 'absence', proxy: 'absence', minutes: 'log', document: 'file', cancellation: 'x', reschedule: 'calendar', live: 'video', attendance_alert: 'alert', waiting_room: 'users' }
const icon = (k) => icons[k] || 'bell'

async function load() {
  try {
    const { data } = await http.get('/notifications', { params: { unread: unreadOnly.value ? 1 : undefined, limit: 100 } })
    items.value = data.items
    unread.value = data.unread
  } catch (e) { toast.error(e) }
}
async function markRead(n) { await http.post(`/notifications/${n.id}/read`); load() }
async function readAll() { await http.post('/notifications/read-all'); load() }
async function open(n) { if (!n.read) await http.post(`/notifications/${n.id}/read`); router.push(n.link) }
async function runReminders() {
  try { const { data } = await http.post('/notifications/send-reminders'); toast.success(t('notifications.remindersSent', { n: data.sent })); load() } catch (e) { toast.error(e) }
}

onMounted(load)
</script>
