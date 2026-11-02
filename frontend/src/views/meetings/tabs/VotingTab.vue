<template>
  <div class="stack">
    <div v-if="auth.can('vote.manage') && ['scheduled', 'live'].includes(meeting.status)" class="card">
      <div class="card-head"><h2>{{ $t('voting.create') }}</h2><button class="btn sm" @click="showForm = !showForm">{{ showForm ? $t('voting.hide') : $t('voting.newBallot') }}</button></div>
      <form v-if="showForm" class="form-grid" @submit.prevent="create">
        <div class="field full"><label>{{ $t('voting.motion') }} *</label><input v-model.trim="form.motion" required :placeholder="$t('voting.motionPh')" /></div>
        <div class="field full"><label>{{ $t('common.description') }}</label><textarea v-model="form.description" rows="2" /></div>
        <div class="field"><label>{{ $t('voting.rule') }}</label>
          <select v-model="form.rule"><option v-for="r in rules" :key="r" :value="r">{{ $t('voting.rules.' + r) }}</option></select>
        </div>
        <div class="field"><label>{{ $t('docs.agendaItem') }}</label>
          <select v-model="form.agenda_item_id"><option value="">—</option><option v-for="a in meeting.agenda_items" :key="a.id" :value="a.id">{{ a.position }}. {{ a.title }}</option></select>
        </div>
        <div class="field"><label>{{ $t('voting.options') }}</label><input v-model="form.options" /><small>{{ $t('voting.optionsHint') }}</small></div>
        <div class="stack">
          <label class="check"><input v-model="form.anonymous" type="checkbox" />{{ $t('voting.anonymous') }}</label>
          <label class="check"><input v-model="form.weighted" type="checkbox" />{{ $t('voting.weighted') }}</label>
        </div>
        <div class="full right"><button class="btn primary">{{ $t('voting.createButton') }}</button></div>
      </form>
    </div>

    <div v-if="!ballots.length" class="card empty">{{ $t('voting.none') }}</div>

    <div v-for="b in ballots" :key="b.id" class="card">
      <div class="card-head">
        <div>
          <h2 style="margin-bottom: .2rem">{{ b.motion }}</h2>
          <div class="small muted">{{ $t('voting.rules.' + b.rule) }} · {{ b.anonymous ? $t('voting.anonymousShort') : $t('voting.identified') }}{{ b.weighted ? ' · ' + $t('voting.weightedShort') : '' }}{{ b.agenda_item ? ' · ' + $t('docs.agendaPrefix', { title: b.agenda_item.title }) : '' }}</div>
        </div>
        <div class="row">
          <span v-if="b.status === 'open' && b.closes_at" class="badge warning">{{ $t('voting.closes', { when: fromNow(b.closes_at) }) }}</span>
          <StatusBadge :status="b.status" :text="b.status === 'open' ? $t('voting.open') : undefined" />
        </div>
      </div>
      <p v-if="b.description" class="pre">{{ b.description }}</p>

      <div v-if="b.status === 'draft' && auth.can('vote.manage')" class="inline-form">
        <div class="field" style="min-width: 140px"><label>{{ $t('voting.window') }}</label><input v-model.number="windows[b.id]" type="number" min="0" max="240" /></div>
        <button class="btn primary" :disabled="meeting.status !== 'live'" :title="meeting.status !== 'live' ? $t('voting.startFirst') : ''" @click="launch(b)"><Icon name="vote" />{{ $t('voting.launch') }}</button>
        <button class="btn ghost" @click="remove(b)">{{ $t('common.delete') }}</button>
        <span v-if="meeting.status !== 'live'" class="small muted">{{ $t('voting.launchWhenLive') }}</span>
      </div>

      <template v-if="b.status === 'open'">
        <div v-if="details[b.id]?.eligible?.length" class="stack">
          <div v-for="e in details[b.id].eligible" :key="e.user.id" class="row between" style="background: var(--surface-2); padding: .6rem .8rem; border-radius: 8px">
            <span>{{ e.self ? $t('voting.yourVote') : $t('voting.asProxy', { name: e.user.full_name }) }}</span>
            <span v-if="e.already_voted" class="badge success"><Icon name="check" :size="12" />{{ $t('voting.recorded') }}</span>
            <span v-else class="actions"><button v-for="o in b.options" :key="o" class="btn sm" :class="o === 'For' ? 'success' : o === 'Against' ? 'danger' : ''" @click="cast(b, o, e)">{{ optionLabel(o) }}</button></span>
          </div>
        </div>
        <p v-else class="small muted">{{ auth.can('vote.cast') ? $t('voting.notEligible') : $t('voting.noRights') }}</p>
        <div v-if="auth.can('vote.manage')" style="margin-top: 1rem">
          <div class="row between"><b>{{ $t('voting.liveTally', { n: b.votes_cast }) }}</b><button class="btn danger sm" @click="close(b)">{{ $t('voting.close') }}</button></div>
          <ResultBars v-if="live[b.id]" :result="live[b.id]" />
        </div>
      </template>

      <template v-if="b.status === 'closed' && b.result">
        <div class="alert" :class="b.result.passed ? 'success' : 'danger'">
          <b>{{ outcomeLabel(b.result) }}</b>
          <span v-if="b.result.support_percent !== undefined"> · {{ $t('voting.support', { n: b.result.support_percent }) }}</span>
          · {{ $t('voting.quorumLine', { present: b.result.quorum.present, eligible: b.result.quorum.eligible, percent: b.result.quorum.percent, required: b.result.quorum.required_percent }) }}
        </div>
        <ResultBars :result="b.result" />
        <details v-if="!b.anonymous" style="margin-top: .5rem" @toggle="loadVotes(b, $event)">
          <summary class="small">{{ $t('voting.distribution') }}</summary>
          <div v-if="votes[b.id]" class="table-wrap" style="margin-top: .5rem">
            <table class="table"><thead><tr><th>{{ $t('common.member') }}</th><th>{{ $t('voting.castBy') }}</th><th>{{ $t('voting.choice') }}</th><th>{{ $t('voting.weight') }}</th></tr></thead>
              <tbody><tr v-for="v in votes[b.id]" :key="v.member.id"><td>{{ v.member.full_name }}</td><td>{{ v.cast_by.id === v.member.id ? '—' : v.cast_by.full_name + ' (' + $t('voting.proxy') + ')' }}</td><td>{{ optionLabel(v.choice) }}</td><td>{{ v.weight }}</td></tr></tbody>
            </table>
          </div>
        </details>
        <div class="row between" style="margin-top: .8rem">
          <span v-if="b.resolution" class="small">{{ $t('voting.resolutionCertified', { number: b.resolution.number, name: b.resolution.certified_by?.full_name }) }}</span>
          <span v-else class="small muted">{{ $t('voting.noResolution') }}</span>
          <div class="actions">
            <button v-if="!b.resolution && auth.can('resolution.record')" class="btn sm primary" @click="record(b)"><Icon name="gavel" />{{ $t('voting.record') }}</button>
            <template v-if="auth.can('export.data')">
              <button class="btn sm" @click="downloadFile(`/voting/ballots/${b.id}/export?format=pdf`, 'ballot.pdf')"><Icon name="download" />{{ $t('voting.summaryPdf') }}</button>
              <button class="btn sm" @click="downloadFile(`/voting/ballots/${b.id}/export?format=csv`, 'ballot.csv')">CSV</button>
            </template>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { defineComponent, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import http, { downloadFile } from '../../../api/http'
import Icon from '../../../components/Icon.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import { has, t } from '../../../i18n'
import { useAuth } from '../../../stores/auth'
import { useToast } from '../../../stores/toast'
import { fromNow } from '../../../utils/format'

const optionLabel = (o) => (has('voting.opt.' + o) ? t('voting.opt.' + o) : o)

function outcomeLabel(r) {
  if (r.winner !== undefined) {
    if (r.passed) return t('voting.decided', { option: optionLabel(r.winner) })
    return r.quorum.met ? t('voting.noDecisionTie') : t('voting.noDecisionQuorum')
  }
  if (r.passed) return t('voting.carried')
  return r.quorum.met ? t('voting.notCarried') : t('voting.notCarriedQuorum')
}

const ResultBars = defineComponent({
  props: { result: Object },
  setup(p) {
    const colors = { For: '#15803d', Against: '#b91c1c', Abstain: '#64748b' }
    return () => h('div', { style: 'margin-top:.6rem' }, p.result.tallies.map((tl) => h('div', { style: 'margin:.45rem 0' }, [
      h('div', { class: 'row between small' }, [h('span', optionLabel(tl.option)), h('b', t('voting.barLine', { votes: tl.votes, percent: tl.percent }))]),
      h('div', { class: 'progress' }, [h('span', { style: { width: tl.percent + '%', background: colors[tl.option] || '#4338ca' } })]),
    ])))
  },
})

const props = defineProps({ meeting: { type: Object, required: true } })
const auth = useAuth()
const toast = useToast()
const ballots = ref([])
const details = reactive({})
const live = reactive({})
const votes = reactive({})
const windows = reactive({})
const showForm = ref(false)
const rules = ['simple', 'two_thirds', 'three_quarters', 'unanimous']
const form = reactive({ motion: '', description: '', rule: 'simple', agenda_item_id: '', options: 'For, Against, Abstain', anonymous: false, weighted: false })
let timer = null

async function load() {
  try {
    ballots.value = (await http.get('/voting/ballots', { params: { meeting_id: props.meeting.id } })).data
    for (const b of ballots.value.filter((x) => x.status === 'open')) {
      details[b.id] = (await http.get(`/voting/ballots/${b.id}`)).data
      if (auth.can('vote.manage')) live[b.id] = (await http.get(`/voting/ballots/${b.id}/results`)).data.result
    }
  } catch (e) { toast.error(e) }
}

async function create() {
  try {
    await http.post('/voting/ballots', { ...form, meeting_id: props.meeting.id, agenda_item_id: form.agenda_item_id || null,
      options: form.options.split(',').map((s) => s.trim()).filter(Boolean) })
    toast.success(t('voting.created'))
    Object.assign(form, { motion: '', description: '' })
    showForm.value = false
    load()
  } catch (e) { toast.error(e) }
}
async function launch(b) { try { await http.post(`/voting/ballots/${b.id}/launch`, { duration_minutes: windows[b.id] || 0 }); toast.success(t('voting.launched')); load() } catch (e) { toast.error(e) } }
async function remove(b) { if (confirm(t('voting.confirmDelete'))) { try { await http.delete(`/voting/ballots/${b.id}`); load() } catch (e) { toast.error(e) } } }
async function cast(b, choice, e) {
  const msg = e.self ? t('voting.confirmCast', { choice: optionLabel(choice) }) : t('voting.confirmCastProxy', { choice: optionLabel(choice), name: e.user.full_name })
  if (!confirm(msg)) return
  try {
    const { data } = await http.post(`/voting/ballots/${b.id}/vote`, { choice, on_behalf_of: e.self ? undefined : e.user.id })
    toast.success(t('voting.castToast', { receipt: data.receipt }))
    load()
  } catch (err) { toast.error(err) }
}
async function close(b) {
  if (!confirm(t('voting.confirmClose'))) return
  try { await http.post(`/voting/ballots/${b.id}/close`); toast.success(t('voting.closedToast')); load() } catch (e) { toast.error(e) }
}
async function record(b) {
  try { const { data } = await http.post(`/voting/ballots/${b.id}/resolution`, {}); toast.success(t('voting.recordedToast', { number: data.number })); load() } catch (e) { toast.error(e) }
}
async function loadVotes(b, ev) {
  if (!ev.target.open || votes[b.id]) return
  try { votes[b.id] = (await http.get(`/voting/ballots/${b.id}/results`)).data.votes } catch (e) { toast.error(e) }
}

onMounted(() => { load(); timer = setInterval(() => { if (ballots.value.some((b) => b.status === 'open') && !document.hidden) load() }, 6000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
