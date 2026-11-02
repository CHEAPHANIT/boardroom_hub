<template>
  <div>
    <div class="page-head">
      <div><h1>{{ isEdit ? $t('meetingForm.editTitle') : $t('meetingForm.createTitle') }}</h1><p>{{ $t('meetingForm.subtitle') }}</p></div>
      <div class="actions"><RouterLink class="btn" :to="isEdit ? `/meetings/${route.params.id}` : '/meetings'">{{ $t('common.cancel') }}</RouterLink></div>
    </div>

    <form class="stack" @submit.prevent="save">
      <div class="card">
        <h2>{{ $t('meetingForm.details') }}</h2>
        <div class="form-grid">
          <div class="field full"><label>{{ $t('meetingForm.agendaTitle') }} *</label><input v-model.trim="form.title" required maxlength="200" :placeholder="$t('meetingForm.titlePh')" /></div>
          <div class="field"><label>{{ $t('meetings.classification') }}</label>
            <select v-model="form.classification">
              <option v-for="c in classes" :key="c" :value="c">{{ $t('meetingForm.class.' + c) }}</option>
            </select>
          </div>
          <div class="field"><label>{{ $t('meetingForm.start') }} *</label><input v-model="form.start" type="datetime-local" required /></div>
          <div class="field"><label>{{ $t('meetingForm.duration') }}</label><input v-model.number="form.duration_minutes" type="number" min="5" max="1440" /></div>
          <div class="field"><label>{{ $t('meetingForm.quorum') }}</label><input v-model.number="form.quorum_percent" type="number" min="1" max="100" /><small>{{ $t('meetingForm.quorumHint') }}</small></div>
          <div class="field full"><label>{{ $t('common.description') }}</label><textarea v-model="form.description" rows="3" /></div>
        </div>
      </div>

      <div v-if="!isEdit" class="card">
        <h2>{{ $t('meetingForm.recurring') }}</h2>
        <div class="form-grid">
          <div class="field"><label>{{ $t('meetingForm.repeat') }}</label>
            <select v-model="form.recurrence">
              <option v-for="r in ['none', 'biweekly', 'monthly', 'quarterly']" :key="r" :value="r">{{ $t('meetingForm.rec.' + r) }}</option>
            </select>
          </div>
          <div class="field"><label>{{ $t('meetingForm.sessions') }}</label><input v-model.number="form.occurrences" type="number" min="1" max="24" :disabled="form.recurrence === 'none'" /></div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h2>{{ $t('meetingForm.agendaItems') }}</h2><button type="button" class="btn sm" @click="addItem"><Icon name="plus" />{{ $t('meetingForm.addItem') }}</button></div>
        <div v-for="(it, i) in form.agenda_items" :key="i" class="inline-form" style="margin-bottom: .6rem">
          <span class="badge">{{ i + 1 }}</span>
          <div class="field" style="flex: 3"><input v-model="it.title" :placeholder="$t('meetingForm.itemTitlePh')" /></div>
          <div class="field" style="flex: 2"><input v-model="it.presenter" :placeholder="$t('meetingForm.presenterPh')" /></div>
          <div class="field" style="width: 110px; min-width: 110px"><input v-model.number="it.duration_minutes" type="number" min="1" :placeholder="$t('meetingForm.minPh')" /></div>
          <button type="button" class="btn sm ghost" :disabled="i === 0" :title="$t('meetingForm.moveUp')" @click="move(i, -1)">↑</button>
          <button type="button" class="btn sm ghost" :title="$t('common.remove')" @click="form.agenda_items.splice(i, 1)"><Icon name="x" /></button>
        </div>
        <div v-if="!form.agenda_items.length" class="muted small">{{ $t('meetingForm.noItems') }}</div>
      </div>

      <div v-if="!isEdit" class="card">
        <h2>{{ $t('meetingForm.participants') }}</h2>
        <p class="muted small">{{ $t('meetingForm.participantsHint') }}</p>
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th></th><th>{{ $t('common.member') }}</th><th>{{ $t('meetingForm.meetingRole') }}</th><th>{{ $t('meetingForm.voting') }}</th></tr></thead>
            <tbody>
              <tr v-for="u in others" :key="u.id">
                <td><input v-model="picked[u.id].on" type="checkbox" :aria-label="$t('meetingForm.inviteX', { name: u.full_name })" /></td>
                <td><Person :user="u" :sub="roleName(u.role)" /></td>
                <td><select v-model="picked[u.id].meeting_role" :disabled="!picked[u.id].on">
                  <option v-for="r in roles" :key="r" :value="r">{{ label(r) }}</option></select></td>
                <td><label class="check"><input v-model="picked[u.id].is_voting" type="checkbox" :disabled="!picked[u.id].on" />{{ $t('meetingForm.voting') }}</label></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2>{{ $t('meetingForm.security') }}</h2>
        <div class="form-grid">
          <div class="field"><label>{{ $t('meetingForm.passcode') }}</label><input v-model.trim="form.passcode" maxlength="12" :placeholder="$t('meetingForm.passcodePh')" /></div>
          <div class="field"><label>{{ $t('meetingForm.cohost') }}</label>
            <select v-model="form.cohost_id"><option :value="null">{{ $t('common.none') }}</option><option v-for="u in directory" :key="u.id" :value="u.id">{{ u.full_name }}</option></select>
          </div>
          <label class="check"><input v-model="form.waiting_room" type="checkbox" />{{ $t('meetingForm.waitingRoom') }}</label>
          <label class="check"><input v-model="form.watermark" type="checkbox" />{{ $t('meetingForm.watermark') }}</label>
        </div>
      </div>

      <div class="actions"><button class="btn primary" :disabled="busy">{{ busy ? $t('common.saving') : isEdit ? $t('common.saveChanges') : $t('meetingForm.createButton') }}</button></div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import Icon from '../../components/Icon.vue'
import Person from '../../components/Person.vue'
import { roleName, t } from '../../i18n'
import { useAuth } from '../../stores/auth'
import { useToast } from '../../stores/toast'
import { fromLocalInput, label, toLocalInput } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const isEdit = computed(() => !!route.params.id)
const busy = ref(false)
const origPasscode = ref('')
const directory = ref([])
const picked = reactive({})
const roles = ['director', 'chair', 'secretary', 'counsel', 'observer', 'auditor']
const classes = ['board', 'committee', 'advisory', 'extraordinary', 'agm']
const tomorrow = new Date(Date.now() + 86400000); tomorrow.setHours(9, 0, 0, 0)

const form = reactive({
  title: '', classification: 'board', description: '', start: toLocalInput(tomorrow.toISOString()), duration_minutes: 90,
  quorum_percent: 50, recurrence: 'none', occurrences: 4, passcode: '', cohost_id: null, waiting_room: true, watermark: true,
  agenda_items: [{ title: t('meetingForm.defaultItem'), presenter: '', duration_minutes: 10 }],
})
const others = computed(() => directory.value.filter((u) => u.id !== auth.user.id))

function guessRole(u) {
  const r = (u.role || '').toLowerCase()
  if (r.includes('chair')) return 'chair'
  if (r.includes('secretary')) return 'secretary'
  if (r.includes('counsel')) return 'counsel'
  if (r.includes('observer')) return 'observer'
  if (r.includes('auditor')) return 'auditor'
  return 'director'
}

function addItem() { form.agenda_items.push({ title: '', presenter: '', duration_minutes: 10 }) }
function move(i, d) { const a = form.agenda_items; [a[i + d], a[i]] = [a[i], a[i + d]] }

onMounted(async () => {
  try {
    directory.value = (await http.get('/users/directory')).data
    for (const u of directory.value) {
      const role = guessRole(u)
      picked[u.id] = { on: ['chair', 'director'].includes(role), meeting_role: role, is_voting: ['chair', 'director'].includes(role) }
    }
    if (isEdit.value) {
      const m = (await http.get(`/meetings/${route.params.id}`)).data
      Object.assign(form, { title: m.title, classification: m.classification, description: m.description, start: toLocalInput(m.scheduled_start),
        duration_minutes: m.duration_minutes, quorum_percent: m.quorum_percent, passcode: m.passcode || '', cohost_id: m.cohost?.id || null,
        waiting_room: m.waiting_room, watermark: m.watermark,
        agenda_items: m.agenda_items.map((a) => ({ id: a.id, title: a.title, presenter: a.presenter, duration_minutes: a.duration_minutes })) })
      origPasscode.value = m.passcode || ''
    }
  } catch (e) { toast.error(e) }
})

async function save() {
  busy.value = true
  const payload = {
    title: form.title, classification: form.classification, description: form.description, scheduled_start: fromLocalInput(form.start),
    duration_minutes: form.duration_minutes, quorum_percent: form.quorum_percent, cohost_id: form.cohost_id,
    waiting_room: form.waiting_room, watermark: form.watermark, agenda_items: form.agenda_items.filter((a) => a.title?.trim()),
  }
  if (isEdit.value ? form.passcode !== origPasscode.value : form.passcode) payload.passcode = form.passcode
  try {
    if (isEdit.value) {
      await http.put(`/meetings/${route.params.id}`, payload)
      toast.success(t('meetingForm.updated'))
      router.push(`/meetings/${route.params.id}`)
    } else {
      payload.recurrence = form.recurrence
      payload.occurrences = form.recurrence === 'none' ? 1 : form.occurrences
      payload.participants = Object.entries(picked).filter(([, p]) => p.on).map(([id, p]) => ({ user_id: Number(id), meeting_role: p.meeting_role, is_voting: p.is_voting }))
      const { data } = await http.post('/meetings', payload)
      toast.success(data.series_meeting_ids.length > 1 ? t('meetingForm.createdSeries', { n: data.series_meeting_ids.length }) : t('meetingForm.created'))
      router.push(`/meetings/${data.id}`)
    }
  } catch (e) { toast.error(e) } finally { busy.value = false }
}
</script>
