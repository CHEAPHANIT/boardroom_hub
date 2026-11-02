<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('audit.title') }}</h1><p>{{ $t('audit.subtitle') }}</p></div>
      <div class="actions">
        <button class="btn" @click="verify"><Icon name="shield" />{{ $t('audit.verify') }}</button>
        <template v-if="auth.can('audit.export')">
          <button class="btn" @click="downloadFile(exportUrl('csv'), 'audit-trail.csv')"><Icon name="download" />{{ $t('audit.signedCsv') }}</button>
          <button class="btn" @click="downloadFile(exportUrl('pdf'), 'audit-trail.pdf')">{{ $t('audit.signedPdf') }}</button>
        </template>
      </div>
    </div>

    <div v-if="integrity" class="alert" :class="integrity.valid ? 'success' : 'danger'">
      <b>{{ integrity.valid ? $t('audit.intact') : $t('audit.tampered') }}</b> – {{ $t('audit.checked', { n: integrity.checked }) }}{{ integrity.valid ? '' : ' · ' + $t('audit.brokenAt', { id: integrity.broken_at }) }}
      <span v-if="integrity.head" class="small mono"> · {{ $t('audit.head') }} {{ integrity.head.slice(0, 24) }}…</span>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'logs' }" @click="tab = 'logs'">{{ $t('audit.logs') }}<span class="count">{{ total }}</span></button>
      <button class="tab" :class="{ active: tab === 'anomalies' }" @click="tab = 'anomalies'; loadAnomalies()">{{ $t('audit.anomalies') }}<span class="count">{{ openAnomalies }}</span></button>
      <button class="tab" :class="{ active: tab === 'archives' }" @click="tab = 'archives'; loadArchives()">{{ $t('audit.archives') }}</button>
    </div>

    <template v-if="tab === 'logs'">
      <div class="card">
        <div class="inline-form">
          <div class="field" style="flex: 1"><label>{{ $t('common.search') }}</label><input v-model="f.q" :placeholder="$t('audit.searchPh')" @keyup.enter="search" /></div>
          <div class="field"><label>{{ $t('audit.userEmail') }}</label><input v-model="f.user" :placeholder="$t('audit.contains')" @keyup.enter="search" /></div>
          <div class="field" style="min-width: 110px"><label>{{ $t('audit.meetingId') }}</label><input v-model="f.meeting_id" type="number" @keyup.enter="search" /></div>
          <div class="field"><label>{{ $t('audit.category') }}</label><select v-model="f.category" @change="search"><option value="">{{ $t('common.all') }}</option><option v-for="c in categories" :key="c" :value="c">{{ label(c) }}</option></select></div>
          <div class="field"><label>{{ $t('minutes.from') }}</label><input v-model="f.from" type="date" @change="search" /></div>
          <div class="field"><label>{{ $t('minutes.to') }}</label><input v-model="f.to" type="date" @change="search" /></div>
          <button class="btn primary" @click="search">{{ $t('common.filter') }}</button>
        </div>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>#</th><th>{{ $t('common.time') }}</th><th>{{ $t('users.user') }}</th><th>{{ $t('audit.category') }}</th><th>{{ $t('audit.action') }}</th><th>{{ $t('absences.meeting') }}</th><th>{{ $t('common.status') }}</th><th>{{ $t('audit.ipDevice') }}</th></tr></thead>
            <tbody>
              <tr v-for="l in logs" :key="l.id" class="clickable" @click="detail = l">
                <td class="mono">{{ l.id }}</td><td class="small">{{ fmtDateTime(l.created_at) }}</td>
                <td class="small">{{ l.user_email || $t('audit.anonymous') }}</td>
                <td><span class="badge" :class="l.category === 'security' ? 'danger' : 'info'">{{ label(l.category) }}</span></td>
                <td class="mono small">{{ l.action }}</td>
                <td>{{ l.meeting_id || '—' }}</td>
                <td><span class="badge" :class="l.status_code >= 400 ? 'danger' : 'success'">{{ l.status_code }}</span></td>
                <td class="small mono">{{ l.ip || '—' }}<div class="muted">{{ l.device_fp || '' }}</div></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="row between" style="margin-top: .75rem">
          <span class="small muted">{{ $t('common.pageOf', { page, pages, total }) }}</span>
          <div class="actions"><button class="btn sm" :disabled="page <= 1" @click="page--; load()">{{ $t('common.previous') }}</button><button class="btn sm" :disabled="page >= pages" @click="page++; load()">{{ $t('common.next') }}</button></div>
        </div>
      </div>
    </template>

    <div v-else-if="tab === 'anomalies'" class="card">
      <div v-if="!anomalies.length" class="empty">{{ $t('audit.noAnomalies') }}</div>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th>{{ $t('common.time') }}</th><th>{{ $t('audit.severity') }}</th><th>{{ $t('audit.type') }}</th><th>{{ $t('common.description') }}</th><th>{{ $t('users.user') }}</th><th>{{ $t('common.status') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in anomalies" :key="a.id">
              <td class="small">{{ fmtDateTime(a.created_at) }}</td><td><StatusBadge :status="a.severity" /></td>
              <td class="small">{{ label(a.kind) }}</td><td>{{ notificationText(a.description) }}</td><td class="small">{{ a.user_email || '—' }}</td>
              <td><StatusBadge :status="a.status" /></td>
              <td><button v-if="a.status === 'open'" class="btn sm" @click="ack(a)">{{ $t('audit.acknowledge') }}</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else class="card">
      <div class="card-head">
        <h2>{{ $t('audit.archivesTitle') }}</h2>
        <button v-if="auth.can('audit.archive')" class="btn primary sm" @click="archive"><Icon name="lock" />{{ $t('audit.lockArchive') }}</button>
      </div>
      <p class="small muted">{{ $t('audit.archivesInfo') }}</p>
      <div v-if="!archives.length" class="empty">{{ $t('audit.noArchives') }}</div>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th>#</th><th>{{ $t('audit.entries') }}</th><th>{{ $t('audit.range') }}</th><th>{{ $t('audit.batchHash') }}</th><th>{{ $t('common.notes') }}</th><th>{{ $t('audit.created') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in archives" :key="a.id">
              <td>{{ a.id }}</td><td>{{ a.entry_count }}</td><td class="mono small">#{{ a.from_id }} – #{{ a.to_id }}</td>
              <td class="mono small">{{ a.batch_hash.slice(0, 20) }}…</td><td>{{ a.note || '—' }}</td>
              <td class="small">{{ fmtDateTime(a.created_at) }}<div class="muted">{{ a.created_by?.full_name }}</div></td>
              <td><button class="btn sm" @click="verifyArchive(a)">{{ $t('audit.verifyShort') }}</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Modal v-if="detail" :title="$t('audit.entryTitle', { id: detail.id })" wide @close="detail = null">
      <dl class="dl">
        <dt>{{ $t('common.time') }}</dt><dd>{{ fmtDateTime(detail.created_at) }}</dd>
        <dt>{{ $t('users.user') }}</dt><dd>{{ detail.user_email || $t('audit.anonymous') }} (ID {{ detail.user_id ?? '—' }})</dd>
        <dt>{{ $t('audit.action') }}</dt><dd class="mono">{{ detail.action }}</dd>
        <dt>{{ $t('audit.category') }}</dt><dd>{{ label(detail.category) }}</dd>
        <dt>{{ $t('audit.entity') }}</dt><dd>{{ detail.entity || '—' }} {{ detail.entity_id || '' }}</dd>
        <dt>{{ $t('audit.request') }}</dt><dd class="mono small">{{ detail.method }} {{ detail.path }} → {{ detail.status_code }}</dd>
        <dt>{{ $t('audit.ip') }}</dt><dd class="mono">{{ detail.ip }}</dd>
        <dt>{{ $t('audit.device') }}</dt><dd class="mono">{{ detail.device_fp || '—' }}</dd>
        <dt>{{ $t('audit.userAgent') }}</dt><dd class="small">{{ detail.user_agent }}</dd>
        <dt>{{ $t('common.details') }}</dt><dd><pre class="mono small" style="margin: 0; white-space: pre-wrap">{{ JSON.stringify(detail.details, null, 2) }}</pre></dd>
        <dt>{{ $t('audit.prevHash') }}</dt><dd class="mono small" style="word-break: break-all">{{ detail.prev_hash }}</dd>
        <dt>{{ $t('audit.entryHash') }}</dt><dd class="mono small" style="word-break: break-all">{{ detail.hash }}</dd>
      </dl>
    </Modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import http, { downloadFile } from '../api/http'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { notificationText, t } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { fmtDateTime, label } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const route = useRoute()
const tab = ref(route.query.tab || 'logs')
const logs = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 25
const categories = ref([])
const anomalies = ref([])
const archives = ref([])
const integrity = ref(null)
const detail = ref(null)
const f = reactive({ q: '', user: '', meeting_id: '', category: '', from: '', to: '' })
const pages = computed(() => Math.max(1, Math.ceil(total.value / perPage)))
const openAnomalies = computed(() => anomalies.value.filter((a) => a.status === 'open').length)

function params() {
  return { q: f.q || undefined, user: f.user || undefined, meeting_id: f.meeting_id || undefined, category: f.category || undefined,
    from: f.from ? f.from + 'T00:00:00' : undefined, to: f.to ? f.to + 'T23:59:59' : undefined }
}
function exportUrl(format) {
  const p = new URLSearchParams(Object.entries({ ...params(), format }).filter(([, v]) => v !== undefined))
  return `/audit/export?${p}`
}
async function load() {
  try {
    const { data } = await http.get('/audit/logs', { params: { ...params(), page: page.value, per_page: perPage } })
    logs.value = data.items
    total.value = data.total
  } catch (e) { toast.error(e) }
}
function search() { page.value = 1; load() }
async function loadAnomalies() { try { anomalies.value = (await http.get('/audit/anomalies')).data } catch (e) { toast.error(e) } }
async function loadArchives() { try { archives.value = (await http.get('/audit/archives')).data } catch (e) { toast.error(e) } }
async function verify() { try { integrity.value = (await http.get('/audit/verify')).data; load() } catch (e) { toast.error(e) } }
async function ack(a) { try { await http.post(`/audit/anomalies/${a.id}/acknowledge`); loadAnomalies() } catch (e) { toast.error(e) } }
async function archive() {
  const note = prompt(t('audit.archiveNote'), '')
  if (note === null) return
  try { const { data } = await http.post('/audit/archives', { note }); toast.success(t('audit.archived', { n: data.entry_count })); loadArchives() } catch (e) { toast.error(e) }
}
async function verifyArchive(a) {
  try { const { data } = await http.get(`/audit/archives/${a.id}/verify`); data.valid ? toast.success(t('audit.archiveOk')) : toast.error(t('audit.archiveBad')) } catch (e) { toast.error(e) }
}

onMounted(async () => {
  load()
  loadAnomalies()
  if (tab.value === 'archives') loadArchives()
  try { categories.value = (await http.get('/audit/categories')).data } catch { /* ignore */ }
})
</script>
