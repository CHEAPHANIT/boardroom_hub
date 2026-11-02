<template>
  <div v-if="roster" class="stack">
    <div class="grid grid-4">
      <div class="card kpi">
        <span class="kpi-label">{{ $t('overview.quorum') }}</span>
        <span class="kpi-value" :style="{ color: roster.quorum.met ? 'var(--success)' : 'var(--danger)' }">{{ roster.quorum.percent }}%</span>
        <div class="progress"><span :style="{ width: Math.min(100, roster.quorum.percent) + '%', background: roster.quorum.met ? 'var(--success)' : 'var(--danger)' }" /></div>
        <span class="kpi-note">{{ $t('participants.quorumNote', { present: roster.quorum.present, eligible: roster.quorum.eligible, required: roster.quorum.required_percent }) }} · {{ roster.quorum.met ? $t('participants.met') : $t('participants.notMet') }}</span>
      </div>
      <div class="card kpi"><span class="kpi-label">{{ $t('participants.connectedNow') }}</span><span class="kpi-value">{{ roster.summary.connected }}</span><span class="kpi-note">{{ $t('participants.inWaiting', { n: roster.summary.waiting }) }}</span></div>
      <div class="card kpi"><span class="kpi-label">{{ $t('participants.rsvp') }}</span><span class="kpi-value">{{ roster.summary.by_rsvp.accepted }}/{{ roster.summary.total }}</span><span class="kpi-note">{{ $t('participants.rsvpNote', { declined: roster.summary.by_rsvp.declined, pending: roster.summary.by_rsvp.pending }) }}</span></div>
      <div class="card kpi"><span class="kpi-label">{{ $t('participants.alerts') }}</span><span class="kpi-value">{{ roster.summary.late + roster.summary.early }}</span><span class="kpi-note">{{ $t('participants.alertsNote', { late: roster.summary.late, early: roster.summary.early }) }}</span></div>
    </div>

    <div class="card">
      <div class="card-head">
        <h2>{{ $t('participants.roster') }}</h2>
        <div class="actions">
          <template v-if="auth.can('export.data')">
            <button class="btn sm" @click="downloadFile(`/attendance/${meeting.id}/sheet?format=pdf`, 'attendance.pdf')"><Icon name="download" />{{ $t('participants.sheetPdf') }}</button>
            <button class="btn sm" @click="downloadFile(`/attendance/${meeting.id}/sheet?format=csv`, 'attendance.csv')">CSV</button>
          </template>
          <button v-if="auth.can('meeting.update') && ['scheduled', 'live'].includes(meeting.status)" class="btn sm primary" @click="openAdd"><Icon name="plus" />{{ $t('participants.add') }}</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>{{ $t('common.member') }}</th><th>{{ $t('common.role') }}</th><th>{{ $t('participants.rsvp') }}</th><th>{{ $t('participants.attendance') }}</th><th>{{ $t('participants.connection') }}</th><th>{{ $t('participants.activeMin') }}</th><th>{{ $t('participants.flags') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="p in roster.participants" :key="p.id">
              <td><Person :user="p.user" :sub="p.user.title" /></td>
              <td>{{ label(p.meeting_role) }}<div class="small muted">{{ p.is_voting ? $t('participants.voting') : $t('participants.nonVoting') }}</div></td>
              <td><StatusBadge :status="p.rsvp" /></td>
              <td>
                <select v-if="auth.can('attendance.manage')" :value="p.attendance_status" style="width: 150px" @change="setStatus(p, $event.target.value)">
                  <option v-for="s in statuses" :key="s" :value="s">{{ label(s) }}</option>
                </select>
                <StatusBadge v-else :status="p.attendance_status" />
              </td>
              <td>
                <span v-if="p.connected" class="badge success"><span class="live-dot" style="background:#16a34a" />{{ $t('participants.online') }}</span>
                <span v-else-if="p.in_waiting_room" class="badge warning">{{ $t('overview.waitingRoom') }}</span>
                <span v-else class="badge">{{ $t('participants.offline') }}</span>
                <div class="small muted">{{ p.first_join_at ? $t('participants.joinedAt', { time: fmtTime(p.first_join_at) }) : '' }}{{ p.last_leave_at ? ' · ' + $t('participants.leftAt', { time: fmtTime(p.last_leave_at) }) : '' }}</div>
              </td>
              <td>{{ p.active_minutes }}</td>
              <td><span v-if="p.late_flag" class="badge warning">{{ $t('participants.late') }}</span> <span v-if="p.early_flag" class="badge danger">{{ $t('participants.leftEarly') }}</span></td>
              <td class="right">
                <button v-if="p.in_waiting_room && meeting.is_host" class="btn sm success" @click="admit(p)">{{ $t('participants.admit') }}</button>
                <button v-if="auth.can('meeting.update') && meeting.status === 'scheduled' && p.user.id !== meeting.host?.id" class="btn sm ghost" :title="$t('common.remove')" @click="remove(p)"><Icon name="x" /></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <div class="card-head"><h2>{{ $t('participants.absenceRequests') }}</h2><RouterLink v-if="auth.can('absence.submit')" class="btn sm" :to="`/absences?meeting=${meeting.id}`">{{ $t('participants.requestAbsence') }}</RouterLink></div>
        <div v-if="!absences.length" class="empty">{{ $t('participants.noAbsences') }}</div>
        <ul v-else class="list">
          <li v-for="a in absences" :key="a.id">
            <div class="row between"><Person :user="a.user" :sub="label(a.reason_code)" /><StatusBadge :status="a.status" /></div>
            <div v-if="a.reason_text" class="small" style="margin-top: .3rem">{{ a.reason_text }}</div>
            <div v-if="a.status === 'pending' && auth.can('absence.approve') && a.user.id !== auth.user.id" class="actions" style="margin-top: .4rem">
              <button class="btn sm success" @click="decide(a, 'approve')">{{ $t('common.approve') }}</button>
              <button class="btn sm danger" @click="decide(a, 'reject')">{{ $t('common.reject') }}</button>
            </div>
          </li>
        </ul>
      </div>

      <div class="card">
        <h2>{{ $t('participants.proxies') }}</h2>
        <ul v-if="proxies.length" class="list">
          <li v-for="x in proxies" :key="x.id" class="row between">
            <span><b>{{ x.principal.full_name }}</b> → {{ x.proxy.full_name }} <span v-if="x.revoked" class="badge">{{ $t('participants.revoked') }}</span></span>
            <button v-if="!x.revoked && auth.can('proxy.assign') && ['scheduled', 'live'].includes(meeting.status)" class="btn sm ghost" @click="revoke(x)">{{ $t('participants.revoke') }}</button>
          </li>
        </ul>
        <p v-else class="muted small">{{ $t('participants.noProxies') }}</p>
        <form v-if="auth.can('proxy.assign') && ['scheduled', 'live'].includes(meeting.status)" class="inline-form" style="margin-top: .75rem" @submit.prevent="assignProxy">
          <div class="field"><label>{{ $t('participants.absentDirector') }}</label>
            <select v-model="proxyForm.principal_id" required>
              <option disabled value="">{{ $t('common.choose') }}</option>
              <option v-for="a in approvedAbsent" :key="a.user.id" :value="a.user.id">{{ a.user.full_name }}</option>
            </select>
          </div>
          <div class="field"><label>{{ $t('participants.proxyHolder') }}</label>
            <select v-model="proxyForm.proxy_id" required>
              <option disabled value="">{{ $t('common.choose') }}</option>
              <option v-for="p in proxyCandidates" :key="p.user.id" :value="p.user.id">{{ p.user.full_name }}</option>
            </select>
          </div>
          <button class="btn primary" :disabled="!approvedAbsent.length">{{ $t('participants.assignProxy') }}</button>
        </form>
      </div>
    </div>

    <div class="card">
      <h2>{{ $t('participants.log') }}</h2>
      <div v-if="!logs.length" class="empty">{{ $t('participants.noLog') }}</div>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th>{{ $t('common.time') }}</th><th>{{ $t('common.member') }}</th><th>{{ $t('participants.event') }}</th><th>IP</th></tr></thead>
          <tbody><tr v-for="l in logs" :key="l.id"><td>{{ fmtDateTime(l.at) }}</td><td>{{ l.user.full_name }}</td><td><span class="badge" :class="l.event === 'join' ? 'success' : ''">{{ label(l.event) }}</span></td><td class="mono">{{ l.ip || '—' }}</td></tr></tbody>
        </table>
      </div>
    </div>

    <Modal v-if="showAdd" :title="$t('participants.add')" @close="showAdd = false">
      <div class="form-grid" style="margin-bottom: 1rem">
        <div class="field"><label>{{ $t('meetingForm.meetingRole') }}</label><select v-model="addRole"><option v-for="r in roles" :key="r" :value="r">{{ label(r) }}</option></select></div>
        <label class="check"><input v-model="addVoting" type="checkbox" />{{ $t('participants.votingMember') }}</label>
      </div>
      <div v-if="!candidates.length" class="muted">{{ $t('participants.allInvited') }}</div>
      <label v-for="u in candidates" :key="u.id" class="check" style="padding: .35rem 0"><input v-model="addIds" type="checkbox" :value="u.id" /><Person :user="u" :sub="roleName(u.role)" /></label>
      <template #footer>
        <button class="btn" @click="showAdd = false">{{ $t('common.close') }}</button>
        <button class="btn primary" :disabled="!addIds.length" @click="addParticipants">{{ $t('participants.inviteN', { n: addIds.length || '' }) }}</button>
      </template>
    </Modal>
  </div>
  <div v-else class="card empty">{{ $t('common.loading') }}</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import http, { downloadFile } from '../../../api/http'
import Icon from '../../../components/Icon.vue'
import Modal from '../../../components/Modal.vue'
import Person from '../../../components/Person.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import { roleName, t } from '../../../i18n'
import { useAuth } from '../../../stores/auth'
import { useToast } from '../../../stores/toast'
import { fmtDateTime, fmtTime, label } from '../../../utils/format'

const props = defineProps({ meeting: { type: Object, required: true } })
const emit = defineEmits(['reload'])
const auth = useAuth()
const toast = useToast()
const roster = ref(null)
const logs = ref([])
const absences = ref([])
const proxies = ref([])
const directory = ref([])
const showAdd = ref(false)
const addIds = ref([])
const addRole = ref('director')
const addVoting = ref(true)
const proxyForm = reactive({ principal_id: '', proxy_id: '' })
const statuses = ['pending', 'present', 'excused', 'unexcused', 'proxy']
const roles = ['director', 'chair', 'secretary', 'counsel', 'observer', 'auditor']
let timer = null

const approvedAbsent = computed(() => absences.value.filter((a) => a.status === 'approved' && !a.proxy &&
  roster.value?.participants.some((p) => p.user.id === a.user.id && p.is_voting)))
const proxyCandidates = computed(() => (roster.value?.participants || []).filter((p) => p.is_voting &&
  !absences.value.some((a) => a.user.id === p.user.id && a.status !== 'rejected') && p.user.id !== Number(proxyForm.principal_id)))
const candidates = computed(() => directory.value.filter((u) => !roster.value?.participants.some((p) => p.user.id === u.id)))

async function load() {
  try {
    const id = props.meeting.id
    const [r, l, px] = await Promise.all([
      http.get(`/attendance/${id}/roster`), http.get(`/attendance/${id}/logs`), http.get('/absences/proxies', { params: { meeting_id: id } }),
    ])
    roster.value = r.data
    logs.value = l.data.reverse()
    proxies.value = px.data
    const scope = auth.can('absence.approve') ? 'all' : 'mine'
    absences.value = (await http.get('/absences', { params: { scope, meeting_id: id } })).data
  } catch (e) { toast.error(e) }
}

async function setStatus(p, value) {
  try { await http.put(`/attendance/${props.meeting.id}/participants/${p.id}/status`, { attendance_status: value }); toast.success(t('participants.statusUpdated')) } catch (e) { toast.error(e) }
  load()
}
async function admit(p) { try { await http.post(`/attendance/${props.meeting.id}/admit/${p.id}`); toast.success(t('participants.admitted', { name: p.user.full_name })); load() } catch (e) { toast.error(e) } }
async function remove(p) {
  if (!confirm(t('participants.confirmRemove', { name: p.user.full_name }))) return
  try { await http.delete(`/meetings/${props.meeting.id}/participants/${p.id}`); load(); emit('reload') } catch (e) { toast.error(e) }
}
async function openAdd() {
  showAdd.value = true
  if (!directory.value.length) directory.value = (await http.get('/users/directory')).data
}
async function addParticipants() {
  try {
    await http.post(`/meetings/${props.meeting.id}/participants`, { user_ids: addIds.value, meeting_role: addRole.value, is_voting: addVoting.value })
    toast.success(t('participants.invited'))
    showAdd.value = false
    addIds.value = []
    load(); emit('reload')
  } catch (e) { toast.error(e) }
}
async function decide(a, action) {
  const comment = action === 'reject' ? prompt(t('absences.rejectReason')) ?? '' : ''
  try { await http.post(`/absences/${a.id}/${action}`, { comment }); toast.success(action === 'approve' ? t('absences.approved') : t('absences.rejected')); load() } catch (e) { toast.error(e) }
}
async function assignProxy() {
  try {
    await http.post('/absences/proxies', { meeting_id: props.meeting.id, principal_id: Number(proxyForm.principal_id), proxy_id: Number(proxyForm.proxy_id) })
    toast.success(t('participants.proxyAssigned'))
    proxyForm.principal_id = ''; proxyForm.proxy_id = ''
    load()
  } catch (e) { toast.error(e) }
}
async function revoke(x) { try { await http.delete(`/absences/proxies/${x.id}`); toast.success(t('participants.proxyRevoked')); load() } catch (e) { toast.error(e) } }

onMounted(() => { load(); timer = setInterval(() => { if (props.meeting.status === 'live' && !document.hidden) load() }, 10000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
