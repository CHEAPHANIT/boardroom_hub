<template>
  <div v-if="data" class="grid grid-3">
    <div class="stack" style="grid-column: span 2">
      <div class="card">
        <div class="card-head">
          <h2>{{ $t('minutes.title') }} <StatusBadge :status="data.status" :text="statusText" /></h2>
          <div class="actions">
            <button v-if="auth.can('export.data') && data.current_version" class="btn sm" @click="downloadFile(`/minutes/${meeting.id}/pdf`, 'minutes.pdf')"><Icon name="download" />{{ $t('minutes.exportPdf') }}</button>
            <button v-if="auth.can('minutes.publish') && data.status === 'draft' && data.current_version" class="btn sm primary" :disabled="meeting.status !== 'ended'" :title="meeting.status !== 'ended' ? $t('minutes.afterEnd') : ''" @click="publish">{{ $t('minutes.publish') }}</button>
            <button v-if="auth.can('minutes.seal') && data.status === 'published'" class="btn sm success" @click="seal"><Icon name="lock" />{{ $t('minutes.seal') }}</button>
          </div>
        </div>
        <div v-if="data.status === 'published'" class="alert info">{{ $t('minutes.publishedInfo', { name: data.published_by?.full_name, date: fmtDateTime(data.published_at) }) }}</div>
        <div v-if="data.status === 'sealed'" class="alert" :class="data.seal_valid ? 'success' : 'danger'">
          <b>{{ data.seal_valid ? $t('minutes.sealed') : $t('minutes.sealBroken') }}</b> {{ $t('minutes.sealedBy', { name: data.sealed_by?.full_name, date: fmtDateTime(data.sealed_at) }) }}
          <div class="small mono" style="word-break: break-all">SHA-256 {{ data.seal_hash }}</div>
        </div>

        <template v-if="canEdit">
          <div class="field"><label>{{ $t('minutes.general') }}</label><textarea v-model="draft.general_notes" rows="4" :placeholder="$t('minutes.generalPh')" @input="dirty = true" /></div>
          <div v-for="a in data.agenda" :key="a.id" class="field" style="margin-top: .9rem">
            <label>{{ a.position }}. {{ a.title }}</label>
            <textarea v-model="draft.items[a.id]" rows="3" :placeholder="$t('minutes.itemPh')" @input="dirty = true" />
          </div>
          <div class="inline-form" style="margin-top: 1rem">
            <div class="field" style="flex: 1"><label>{{ $t('minutes.changeNote') }}</label><input v-model="changeNote" :placeholder="$t('minutes.changeNotePh')" /></div>
            <button class="btn primary" :disabled="saving" @click="save">{{ saving ? $t('common.saving') : $t('minutes.saveVersion') }}</button>
          </div>
          <p v-if="dirty" class="small muted">{{ $t('minutes.unsaved') }}</p>
        </template>
        <template v-else-if="data.content">
          <h3>{{ $t('minutes.general') }}</h3>
          <p class="pre">{{ data.content.general_notes || '—' }}</p>
          <div v-for="a in data.agenda" :key="a.id" style="margin-top: .8rem">
            <h3>{{ a.position }}. {{ a.title }}</h3>
            <p class="pre">{{ notesFor(a.id) || $t('minutes.noNotes') }}</p>
          </div>
        </template>
        <div v-else class="empty">{{ $t('minutes.notWritten') }}</div>
      </div>

      <div class="card">
        <h2>{{ $t('minutes.summary') }}</h2>
        <p class="small muted">{{ $t('minutes.summaryHint') }}</p>
        <div v-for="a in data.agenda" :key="a.id" style="border-top: 1px solid var(--border); padding: .75rem 0">
          <div class="row between"><b>{{ a.position }}. {{ a.title }}</b>
            <button v-if="canEdit && editingItem !== a.id" class="btn sm" @click="startItem(a)">{{ $t('common.edit') }}</button></div>
          <div v-if="editingItem === a.id" class="stack" style="margin-top: .5rem">
            <div class="field"><label>{{ $t('minutes.decision') }}</label><textarea v-model="itemForm.decision" rows="2" /></div>
            <div class="field"><label>{{ $t('minutes.advisoryLong') }}</label><textarea v-model="itemForm.advisory" rows="2" /></div>
            <div class="field"><label>{{ $t('minutes.findingLong') }}</label><textarea v-model="itemForm.finding" rows="2" /></div>
            <div class="actions"><button class="btn sm primary" @click="saveItem(a)">{{ $t('minutes.saveSummary') }}</button><button class="btn sm" @click="editingItem = null">{{ $t('common.cancel') }}</button></div>
          </div>
          <template v-else>
            <div v-if="a.decision" class="small"><span class="badge success">{{ $t('minutes.decision') }}</span> {{ a.decision }}</div>
            <div v-if="a.advisory" class="small"><span class="badge info">{{ $t('minutes.advisory') }}</span> {{ a.advisory }}</div>
            <div v-if="a.finding" class="small"><span class="badge warning">{{ $t('minutes.finding') }}</span> {{ a.finding }}</div>
            <div v-if="!a.decision && !a.advisory && !a.finding" class="small muted">{{ $t('minutes.noSummary') }}</div>
          </template>
        </div>
      </div>
    </div>

    <div class="stack">
      <div class="card">
        <h2>{{ $t('minutes.history') }}</h2>
        <div v-if="!versions.length" class="empty">{{ $t('minutes.noVersions') }}</div>
        <ul v-else class="list">
          <li v-for="v in versions" :key="v.version">
            <div class="row between"><b>v{{ v.version }}</b><span class="small muted">{{ fmtDateTime(v.created_at) }}</span></div>
            <div class="small">{{ v.author?.full_name }} · {{ v.change_note || $t('minutes.noChangeNote') }}</div>
          </li>
        </ul>
        <div v-if="versions.length > 1" class="inline-form" style="margin-top: .75rem">
          <div class="field" style="min-width: 80px"><label>{{ $t('minutes.from') }}</label><select v-model.number="diffFrom"><option v-for="v in versions" :key="v.version" :value="v.version">v{{ v.version }}</option></select></div>
          <div class="field" style="min-width: 80px"><label>{{ $t('minutes.to') }}</label><select v-model.number="diffTo"><option v-for="v in versions" :key="v.version" :value="v.version">v{{ v.version }}</option></select></div>
          <button class="btn sm" @click="compare">{{ $t('minutes.compare') }}</button>
        </div>
      </div>
      <div v-if="diff" class="card">
        <div class="card-head"><h3>v{{ diff.from.version }} → v{{ diff.to.version }}</h3><button class="btn sm ghost" @click="diff = null"><Icon name="x" /></button></div>
        <p class="small muted">{{ $t('minutes.changesBy', { name: diff.to.author?.full_name }) }}</p>
        <div v-if="!diff.lines.length" class="muted small">{{ $t('minutes.noDiff') }}</div>
        <div v-for="(l, i) in diff.lines" :key="i" class="diff-line" :class="l.kind">{{ l.kind === 'add' ? '+ ' : l.kind === 'remove' ? '− ' : '' }}{{ l.text }}</div>
      </div>
    </div>
  </div>
  <div v-else class="card empty">{{ $t('common.loading') }}</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import http, { downloadFile } from '../../../api/http'
import Icon from '../../../components/Icon.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import { t } from '../../../i18n'
import { useAuth } from '../../../stores/auth'
import { useToast } from '../../../stores/toast'
import { fmtDateTime } from '../../../utils/format'

const props = defineProps({ meeting: { type: Object, required: true } })
const auth = useAuth()
const toast = useToast()
const data = ref(null)
const versions = ref([])
const draft = reactive({ general_notes: '', items: {} })
const changeNote = ref('')
const dirty = ref(false)
const saving = ref(false)
const editingItem = ref(null)
const itemForm = reactive({ decision: '', advisory: '', finding: '' })
const diffFrom = ref(1)
const diffTo = ref(1)
const diff = ref(null)

const canEdit = computed(() => auth.can('minutes.edit') && data.value?.editable && props.meeting.status !== 'cancelled')
const statusText = computed(() => data.value.status === 'draft'
  ? t('minutes.draftV', { v: data.value.current_version })
  : t('minutes.status.' + data.value.status))
const notesFor = (id) => data.value.content?.items.find((i) => i.agenda_item_id === id)?.notes

async function load() {
  try {
    data.value = (await http.get(`/minutes/${props.meeting.id}`)).data
    versions.value = (await http.get(`/minutes/${props.meeting.id}/versions`)).data
    draft.general_notes = data.value.content?.general_notes || ''
    draft.items = Object.fromEntries(data.value.agenda.map((a) => [a.id, notesFor(a.id) || '']))
    if (versions.value.length > 1) { diffTo.value = versions.value[0].version; diffFrom.value = versions.value[1].version }
    dirty.value = false
  } catch (e) { toast.error(e) }
}

async function save() {
  saving.value = true
  try {
    await http.put(`/minutes/${props.meeting.id}`, {
      general_notes: draft.general_notes, change_note: changeNote.value,
      items: Object.entries(draft.items).map(([id, notes]) => ({ agenda_item_id: Number(id), notes })),
    })
    changeNote.value = ''
    toast.success(t('minutes.savedVersion'))
    await load()
  } catch (e) { toast.error(e) } finally { saving.value = false }
}

function startItem(a) { editingItem.value = a.id; Object.assign(itemForm, { decision: a.decision, advisory: a.advisory, finding: a.finding }) }
async function saveItem(a) {
  try { await http.put(`/minutes/${props.meeting.id}/agenda/${a.id}`, itemForm); editingItem.value = null; toast.success(t('minutes.summarySaved')); load() } catch (e) { toast.error(e) }
}
async function publish() {
  if (!confirm(t('minutes.confirmPublish'))) return
  try { await http.post(`/minutes/${props.meeting.id}/publish`); toast.success(t('minutes.publishedToast')); load() } catch (e) { toast.error(e) }
}
async function seal() {
  if (!confirm(t('minutes.confirmSeal'))) return
  try { await http.post(`/minutes/${props.meeting.id}/seal`); toast.success(t('minutes.sealedToast')); load() } catch (e) { toast.error(e) }
}
async function compare() {
  try { diff.value = (await http.get(`/minutes/${props.meeting.id}/diff/${diffFrom.value}/${diffTo.value}`)).data } catch (e) { toast.error(e) }
}

function beforeUnload(e) { if (dirty.value) { e.preventDefault(); e.returnValue = '' } }
onMounted(() => { load(); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
</script>
