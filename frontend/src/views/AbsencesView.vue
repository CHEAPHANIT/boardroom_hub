<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('absences.title') }}</h1><p>{{ $t('absences.subtitle') }}</p></div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'mine' }" @click="tab = 'mine'">{{ $t('absences.mine') }}<span class="count">{{ mine.length }}</span></button>
      <button v-if="auth.can('absence.approve')" class="tab" :class="{ active: tab === 'pending' }" @click="tab = 'pending'">{{ $t('absences.pending') }}<span class="count">{{ pending.length }}</span></button>
      <button class="tab" :class="{ active: tab === 'logs' }" @click="tab = 'logs'; loadLogs()">{{ $t('absences.history') }}</button>
    </div>

    <template v-if="tab === 'mine'">
      <div v-if="auth.can('absence.submit')" class="card">
        <h2>{{ $t('absences.submitTitle') }}</h2>
        <form class="form-grid" @submit.prevent="submit">
          <div class="field"><label>{{ $t('absences.meeting') }} *</label>
            <select v-model="form.meeting_id" required><option disabled value="">{{ $t('absences.chooseMeeting') }}</option>
              <option v-for="m in meetings" :key="m.id" :value="m.id">{{ m.title }} – {{ fmtDate(m.scheduled_start) }}</option></select>
          </div>
          <div class="field"><label>{{ $t('absences.reasonCode') }} *</label>
            <select v-model="form.reason_code" required><option v-for="r in reasons" :key="r" :value="r">{{ label(r) }}</option></select>
          </div>
          <div class="field full"><label>{{ $t('absences.explanation') }}</label><textarea v-model="form.reason_text" rows="2" :placeholder="$t('absences.explanationPh')" /></div>
          <div class="field"><label>{{ $t('absences.supportingDoc') }}</label><input ref="fileInput" type="file" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" /><small>{{ $t('absences.supportingHint') }}</small></div>
          <div class="right" style="align-self: end"><button class="btn primary" :disabled="busy">{{ $t('absences.submitButton') }}</button></div>
        </form>
      </div>
      <div class="card">
        <h2>{{ $t('absences.mine') }}</h2>
        <AbsenceTable :rows="mine" mine @changed="load" />
      </div>
    </template>

    <div v-else-if="tab === 'pending'" class="card">
      <h2>{{ $t('absences.awaiting') }}</h2>
      <AbsenceTable :rows="pending" approver @changed="load" />
    </div>

    <template v-else>
      <div class="card">
        <h2>{{ $t('absences.waivers') }}</h2>
        <AbsenceTable :rows="logs.absences" />
      </div>
      <div class="card">
        <h2>{{ $t('absences.proxyAuths') }}</h2>
        <div v-if="!logs.proxies.length" class="empty">{{ $t('participants.noProxies') }}</div>
        <div v-else class="table-wrap">
          <table class="table">
            <thead><tr><th>{{ $t('absences.meeting') }}</th><th>{{ $t('absences.absentMember') }}</th><th>{{ $t('participants.proxyHolder') }}</th><th>{{ $t('absences.assignedBy') }}</th><th>{{ $t('common.date') }}</th><th>{{ $t('common.status') }}</th></tr></thead>
            <tbody><tr v-for="p in logs.proxies" :key="p.id">
              <td><RouterLink :to="`/meetings/${p.meeting_id}`">{{ $t('absences.meetingN', { n: p.meeting_id }) }}</RouterLink></td>
              <td>{{ p.principal.full_name }}</td><td>{{ p.proxy.full_name }}</td><td>{{ p.assigned_by?.full_name }}</td>
              <td>{{ fmtDate(p.created_at) }}</td><td><span class="badge" :class="p.revoked ? '' : 'success'">{{ p.revoked ? $t('participants.revoked') : $t('absences.active') }}</span></td>
            </tr></tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { defineComponent, h, onMounted, reactive, ref, resolveComponent } from 'vue'
import { useRoute } from 'vue-router'
import http, { downloadFile } from '../api/http'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { bytes, fmtDate, fmtDateTime, label } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const route = useRoute()
const tab = ref(route.query.tab || 'mine')
const mine = ref([])
const pending = ref([])
const logs = ref({ absences: [], proxies: [] })
const meetings = ref([])
const reasons = ['medical', 'conflict', 'travel', 'personal', 'other']
const busy = ref(false)
const fileInput = ref(null)
const form = reactive({ meeting_id: route.query.meeting ? Number(route.query.meeting) : '', reason_code: 'conflict', reason_text: '' })

async function uploadDoc(id, file) {
  const fd = new FormData()
  fd.append('file', file)
  await http.post(`/absences/${id}/documents`, fd)
}

const AbsenceTable = defineComponent({
  props: { rows: Array, mine: Boolean, approver: Boolean },
  emits: ['changed'],
  setup(props, { emit }) {
    const RouterLink = resolveComponent('RouterLink')
    const act = async (fn, msg) => { try { await fn(); toast.success(msg); emit('changed') } catch (e) { toast.error(e) } }
    const attach = (a) => {
      const input = document.createElement('input')
      input.type = 'file'
      input.onchange = () => input.files[0] && act(() => uploadDoc(a.id, input.files[0]), t('absences.attached'))
      input.click()
    }
    return () => !props.rows.length ? h('div', { class: 'empty' }, t('common.nothingHere')) : h('div', { class: 'table-wrap' }, h('table', { class: 'table' }, [
      h('thead', h('tr', [t('absences.meeting'), props.mine ? null : t('common.member'), t('absences.reason'), t('absences.documents'), t('common.status'), t('absences.reviewed'), ''].filter((x) => x !== null).map((x) => h('th', x)))),
      h('tbody', props.rows.map((a) => h('tr', { key: a.id }, [
        h('td', [h(RouterLink, { to: `/meetings/${a.meeting.id}` }, () => a.meeting.title), h('div', { class: 'small muted' }, fmtDateTime(a.meeting.scheduled_start))]),
        props.mine ? null : h('td', a.user.full_name),
        h('td', [h('b', label(a.reason_code)), h('div', { class: 'small' }, a.reason_text)]),
        h('td', [...a.documents.map((d) => h('div', h('a', { href: '#', onClick: (e) => { e.preventDefault(); downloadFile(`/absences/documents/${d.id}/download`, d.filename) } }, `${d.filename} (${bytes(d.size)})`))),
          props.mine && a.status === 'pending' ? h('button', { class: 'btn sm ghost', onClick: () => attach(a) }, '+ ' + t('absences.attach')) : null]),
        h('td', [h(StatusBadge, { status: a.status }), a.proxy ? h('div', { class: 'small muted' }, t('absences.proxyLine', { name: a.proxy.proxy.full_name })) : null]),
        h('td', { class: 'small' }, a.reviewer ? [`${a.reviewer.full_name} · ${fmtDate(a.reviewed_at)}`, a.review_comment ? h('div', { class: 'muted' }, `“${a.review_comment}”`) : null] : '—'),
        h('td', { class: 'right' }, [
          props.approver && a.status === 'pending' && a.user.id !== auth.user.id ? [
            h('button', { class: 'btn sm success', onClick: () => act(() => http.post(`/absences/${a.id}/approve`, { comment: '' }), t('absences.approved')) }, t('common.approve')), ' ',
            h('button', { class: 'btn sm danger', onClick: () => { const c = prompt(t('absences.rejectReason')); if (c !== null) act(() => http.post(`/absences/${a.id}/reject`, { comment: c }), t('absences.rejected')) } }, t('common.reject'))] : null,
          props.mine && a.status === 'pending' ? h('button', { class: 'btn sm ghost', onClick: () => confirm(t('absences.confirmWithdraw')) && act(() => http.delete(`/absences/${a.id}`), t('absences.withdrawn')) }, t('absences.withdraw')) : null,
        ]),
      ].filter((x) => x !== null)))),
    ]))
  },
})

async function load() {
  try {
    mine.value = (await http.get('/absences', { params: { scope: 'mine' } })).data
    if (auth.can('absence.approve')) pending.value = (await http.get('/absences', { params: { scope: 'pending' } })).data
  } catch (e) { toast.error(e) }
}
async function loadLogs() { try { logs.value = (await http.get('/absences/logs')).data } catch (e) { toast.error(e) } }

async function submit() {
  busy.value = true
  try {
    const { data } = await http.post('/absences', form)
    const file = fileInput.value?.files[0]
    if (file) await uploadDoc(data.id, file)
    toast.success(t('absences.submitted'))
    form.reason_text = ''
    if (fileInput.value) fileInput.value.value = ''
    load()
  } catch (e) { toast.error(e) } finally { busy.value = false }
}

onMounted(async () => {
  load()
  if (tab.value === 'logs') loadLogs()
  try {
    if (auth.can('meeting.view')) meetings.value = (await http.get('/meetings', { params: { status: 'scheduled,live' } })).data
  } catch (e) { toast.error(e) }
})
</script>
