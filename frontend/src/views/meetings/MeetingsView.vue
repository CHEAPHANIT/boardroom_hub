<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('meetings.title') }}</h1><p>{{ $t('meetings.subtitle') }}</p></div>
      <div class="actions">
        <button class="btn" @click="downloadFile('/meetings/calendar.ics', 'boardroom-meetings.ics')"><Icon name="calendar" />{{ $t('meetings.exportIcs') }}</button>
        <RouterLink v-if="auth.can('meeting.create')" class="btn primary" to="/meetings/new"><Icon name="plus" />{{ $t('meetings.new') }}</RouterLink>
      </div>
    </div>

    <div class="tabs">
      <button v-for="tb in tabs" :key="tb" class="tab" :class="{ active: tab === tb }" @click="tab = tb">
        {{ $t('meetings.tabs.' + tb) }}<span class="count">{{ counts[tb] }}</span>
      </button>
    </div>

    <div class="card">
      <div class="inline-form" style="margin-bottom: 1rem">
        <div class="field" style="flex: 1"><label>{{ $t('common.search') }}</label><input v-model="q" :placeholder="$t('meetings.searchPh')" /></div>
        <div class="field"><label>{{ $t('meetings.classification') }}</label>
          <select v-model="cls"><option value="">{{ $t('common.all') }}</option><option v-for="c in classes" :key="c" :value="c">{{ label(c) }}</option></select>
        </div>
      </div>
      <div v-if="loading" class="empty">{{ $t('common.loading') }}</div>
      <div v-else-if="!filtered.length" class="empty">{{ $t('meetings.none') }}</div>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th>{{ $t('meetings.colMeeting') }}</th><th>{{ $t('meetings.colDate') }}</th><th>{{ $t('meetings.colType') }}</th><th>{{ $t('meetings.colHost') }}</th><th>{{ $t('meetings.colPeople') }}</th><th>{{ $t('common.status') }}</th></tr></thead>
          <tbody>
            <tr v-for="m in filtered" :key="m.id" class="clickable" @click="router.push(`/meetings/${m.id}`)">
              <td><b>{{ m.title }}</b><div v-if="m.series_id" class="small muted">{{ $t('meetings.recurring') }} · {{ label(m.recurrence) }}</div></td>
              <td>{{ fmtDateTime(m.scheduled_start) }}<div class="small muted">{{ $t('common.minutes', { n: m.duration_minutes }) }} · {{ fromNow(m.scheduled_start) }}</div></td>
              <td>{{ label(m.classification) }}</td>
              <td>{{ m.host?.full_name }}</td>
              <td>{{ m.participant_count }}</td>
              <td><StatusBadge :status="m.status" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http, { downloadFile } from '../../api/http'
import Icon from '../../components/Icon.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import { useAuth } from '../../stores/auth'
import { useToast } from '../../stores/toast'
import { fmtDateTime, fromNow, label } from '../../utils/format'

const auth = useAuth()
const toast = useToast()
const router = useRouter()
const meetings = ref([])
const loading = ref(true)
const tab = ref('upcoming')
const q = ref('')
const cls = ref('')
const classes = ['board', 'committee', 'advisory', 'extraordinary', 'agm']
const tabs = ['upcoming', 'live', 'past', 'cancelled', 'all']

const match = (m, key) => key === 'all' || (key === 'upcoming' && m.status === 'scheduled') || (key === 'live' && m.status === 'live') ||
  (key === 'past' && m.status === 'ended') || (key === 'cancelled' && m.status === 'cancelled')
const counts = computed(() => Object.fromEntries(tabs.map((k) => [k, meetings.value.filter((m) => match(m, k)).length])))
const filtered = computed(() => {
  const list = meetings.value.filter((m) => match(m, tab.value) && (!cls.value || m.classification === cls.value) &&
    (!q.value || m.title.toLowerCase().includes(q.value.toLowerCase())))
  return tab.value === 'past' || tab.value === 'all' ? [...list].reverse() : list
})

onMounted(async () => {
  try {
    meetings.value = (await http.get('/meetings')).data
    if (meetings.value.some((m) => m.status === 'live')) tab.value = 'live'
  } catch (e) { toast.error(e) } finally { loading.value = false }
})
</script>
