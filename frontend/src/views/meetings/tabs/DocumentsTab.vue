<template>
  <div class="stack">
    <div v-if="auth.can('document.upload') && meeting.status !== 'cancelled'" class="card">
      <h2>{{ $t('docs.uploadTitle') }}</h2>
      <form class="form-grid" @submit.prevent="upload">
        <div class="field"><label>{{ $t('common.title') }}</label><input v-model.trim="form.title" :placeholder="$t('docs.titlePh')" /></div>
        <div class="field"><label>{{ $t('docs.linkAgenda') }}</label>
          <select v-model="form.agenda_item_id"><option value="">{{ $t('docs.general') }}</option><option v-for="a in meeting.agenda_items" :key="a.id" :value="a.id">{{ a.position }}. {{ a.title }}</option></select>
        </div>
        <div class="field"><label>{{ $t('docs.classification') }}</label>
          <select v-model="form.classification">
            <option value="internal">{{ label('internal') }}</option><option value="confidential">{{ label('confidential') }}</option>
            <option value="strictly_confidential">{{ label('strictly_confidential') }} ({{ $t('docs.viewOnly') }})</option>
          </select>
        </div>
        <div class="field"><label>{{ $t('docs.file') }}</label><input ref="fileInput" type="file" required accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.txt" /></div>
        <label class="check"><input v-model="form.allow_download" type="checkbox" :disabled="form.classification === 'strictly_confidential'" />{{ $t('docs.allowDownload') }}</label>
        <div class="right"><button class="btn primary" :disabled="busy"><Icon name="upload" />{{ busy ? $t('docs.uploading') : $t('docs.upload') }}</button></div>
      </form>
    </div>

    <div class="card">
      <h2>{{ $t('docs.boardPack', { n: docs.length }) }}</h2>
      <div v-if="!docs.length" class="empty">{{ $t('docs.none') }}</div>
      <div v-for="d in docs" :key="d.id" style="border-top: 1px solid var(--border); padding: .9rem 0">
        <div class="row between">
          <div class="row"><Icon name="file" :size="22" />
            <div>
              <b>{{ d.title }}</b> <StatusBadge :status="d.classification" /> <span class="badge">v{{ d.current_version }}</span>
              <div class="small muted">{{ d.agenda_item ? $t('docs.agendaPrefix', { title: d.agenda_item.title }) + ' · ' : '' }}{{ d.latest?.filename }} · {{ bytes(d.latest?.size) }} · {{ fmtDateTime(d.latest?.uploaded_at) }} · {{ d.latest?.uploaded_by?.full_name }}</div>
            </div>
          </div>
          <div class="actions">
            <button class="btn sm" @click="viewing = { doc: d, version: d.current_version }"><Icon name="eye" />{{ $t('common.view') }}</button>
            <button v-if="d.can_download" class="btn sm" @click="download(d, d.current_version)"><Icon name="download" />{{ $t('common.download') }}</button>
            <span v-else class="badge" :title="$t('docs.restricted')"><Icon name="lock" :size="12" />{{ $t('docs.viewOnly') }}</span>
            <template v-if="auth.can('document.upload')">
              <button class="btn sm" @click="newVersion(d)">{{ $t('docs.newVersion') }}</button>
              <button class="btn sm" @click="openEdit(d)">{{ $t('docs.settings') }}</button>
              <button class="btn sm ghost" :title="$t('common.delete')" @click="remove(d)"><Icon name="x" /></button>
            </template>
          </div>
        </div>
        <details v-if="d.versions.length > 1" style="margin-top: .5rem">
          <summary class="small">{{ $t('docs.history', { n: d.versions.length }) }}</summary>
          <ul class="list small">
            <li v-for="v in d.versions" :key="v.id" class="row between">
              <span><b>v{{ v.version }}</b> {{ v.filename }} · {{ v.note || $t('docs.noNote') }} · {{ fmtDateTime(v.uploaded_at) }} · {{ v.uploaded_by?.full_name }}
                <span v-if="v.version === d.current_version" class="badge success">{{ $t('docs.latest') }}</span></span>
              <span class="actions"><button class="btn sm ghost" @click="viewing = { doc: d, version: v.version }">{{ $t('common.view') }}</button>
                <button v-if="d.can_download" class="btn sm ghost" @click="download(d, v.version)">{{ $t('common.download') }}</button></span>
            </li>
          </ul>
        </details>
      </div>
    </div>

    <input ref="versionInput" type="file" hidden @change="uploadVersion" />
    <DocViewer v-if="viewing" :doc="viewing.doc" :version="viewing.version" @close="viewing = null" />

    <Modal v-if="editing" :title="$t('docs.settingsTitle')" @close="editing = null">
      <div class="stack">
        <div class="field"><label>{{ $t('common.title') }}</label><input v-model="editing.title" /></div>
        <div class="field"><label>{{ $t('docs.agendaItem') }}</label>
          <select v-model="editing.agenda_item_id"><option :value="null">{{ $t('docs.general') }}</option><option v-for="a in meeting.agenda_items" :key="a.id" :value="a.id">{{ a.position }}. {{ a.title }}</option></select>
        </div>
        <div class="field"><label>{{ $t('docs.classification') }}</label>
          <select v-model="editing.classification"><option value="internal">{{ label('internal') }}</option><option value="confidential">{{ label('confidential') }}</option><option value="strictly_confidential">{{ label('strictly_confidential') }}</option></select>
        </div>
        <label class="check"><input v-model="editing.allow_download" type="checkbox" />{{ $t('docs.allowDownload') }}</label>
      </div>
      <template #footer><button class="btn" @click="editing = null">{{ $t('common.cancel') }}</button><button class="btn primary" @click="saveEdit">{{ $t('common.save') }}</button></template>
    </Modal>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import http, { downloadFile } from '../../../api/http'
import DocViewer from '../../../components/DocViewer.vue'
import Icon from '../../../components/Icon.vue'
import Modal from '../../../components/Modal.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import { t } from '../../../i18n'
import { useAuth } from '../../../stores/auth'
import { useToast } from '../../../stores/toast'
import { bytes, fmtDateTime, label } from '../../../utils/format'

const props = defineProps({ meeting: { type: Object, required: true } })
const auth = useAuth()
const toast = useToast()
const docs = ref([])
const busy = ref(false)
const viewing = ref(null)
const editing = ref(null)
const fileInput = ref(null)
const versionInput = ref(null)
const versionTarget = ref(null)
const form = reactive({ title: '', agenda_item_id: '', classification: 'confidential', allow_download: true })

async function load() {
  try { docs.value = (await http.get('/documents', { params: { meeting_id: props.meeting.id } })).data } catch (e) { toast.error(e) }
}

async function upload() {
  const file = fileInput.value.files[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  fd.append('meeting_id', props.meeting.id)
  fd.append('title', form.title)
  fd.append('classification', form.classification)
  fd.append('allow_download', form.classification === 'strictly_confidential' ? 'false' : String(form.allow_download))
  if (form.agenda_item_id) fd.append('agenda_item_id', form.agenda_item_id)
  busy.value = true
  try {
    await http.post('/documents', fd)
    toast.success(t('docs.uploaded'))
    form.title = ''
    fileInput.value.value = ''
    load()
  } catch (e) { toast.error(e) } finally { busy.value = false }
}

function newVersion(d) { versionTarget.value = d; versionInput.value.click() }
async function uploadVersion(ev) {
  const file = ev.target.files[0]
  if (!file) return
  const note = prompt(t('docs.whatChanged'), '') ?? ''
  const fd = new FormData()
  fd.append('file', file)
  fd.append('note', note)
  try { await http.post(`/documents/${versionTarget.value.id}/versions`, fd); toast.success(t('docs.versionUploaded')); load() } catch (e) { toast.error(e) }
  ev.target.value = ''
}
async function download(d, version) {
  await downloadFile(`/documents/${d.id}/download?version=${version}`, d.latest?.filename)
}
function openEdit(d) { editing.value = { id: d.id, title: d.title, agenda_item_id: d.agenda_item?.id || null, classification: d.classification, allow_download: d.allow_download } }
async function saveEdit() {
  try { await http.put(`/documents/${editing.value.id}`, editing.value); toast.success(t('docs.settingsSaved')); editing.value = null; load() } catch (e) { toast.error(e) }
}
async function remove(d) {
  if (!confirm(t('docs.confirmDelete', { title: d.title }))) return
  try { await http.delete(`/documents/${d.id}`); load() } catch (e) { toast.error(e) }
}

onMounted(load)
</script>
