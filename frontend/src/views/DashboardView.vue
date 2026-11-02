<template>
  <div>
    <div class="page-head">
      <div>
        <h1>{{ $t('dashboard.greeting.' + greeting, { name: firstName }) }}</h1>
        <p>{{ $t('dashboard.subtitle') }} · {{ roleName(auth.user?.role?.name) }}</p>
      </div>
      <div class="actions">
        <button class="btn" @click="downloadFile('/meetings/calendar.ics', 'boardroom-meetings.ics')"><Icon name="calendar" />{{ $t('dashboard.addCalendar') }}</button>
        <RouterLink v-if="auth.can('meeting.create')" class="btn primary" to="/meetings/new"><Icon name="plus" />{{ $t('meetings.new') }}</RouterLink>
      </div>
    </div>

    <div v-if="!data" class="card empty">{{ $t('common.loading') }}</div>
    <template v-else>
      <div v-for="m in data.live" :key="m.id" class="alert danger row between">
        <span><span class="live-dot" /> <b>{{ m.title }}</b> {{ $t('dashboard.isLive') }}</span>
        <RouterLink class="btn sm danger" :to="`/meetings/${m.id}`">{{ $t('dashboard.goToMeeting') }}</RouterLink>
      </div>
      <div v-for="v in data.my_pending_votes" :key="v.ballot_id" class="alert warning row between">
        <span><b>{{ $t('dashboard.voteNeeded') }}</b> {{ v.motion }} ({{ v.meeting_title }})</span>
        <RouterLink class="btn sm" :to="`/meetings/${v.meeting_id}?tab=voting`">{{ $t('dashboard.voteNow') }}</RouterLink>
      </div>

      <div class="grid grid-4">
        <div class="card kpi"><span class="kpi-label">{{ $t('dashboard.kpiUpcoming') }}</span><span class="kpi-value">{{ data.kpis.upcoming_meetings }}</span><span class="kpi-note">{{ $t('dashboard.liveNow', { n: data.kpis.live_meetings }) }}</span></div>
        <div class="card kpi"><span class="kpi-label">{{ $t('dashboard.kpiAttendance') }}</span><span class="kpi-value">{{ data.kpis.attendance_rate ?? '—' }}<small v-if="data.kpis.attendance_rate !== null">%</small></span><span class="kpi-note">{{ $t('dashboard.kpiAttendanceNote') }}</span></div>
        <div class="card kpi"><span class="kpi-label">{{ $t('dashboard.kpiBreaches') }}</span><span class="kpi-value" :style="{ color: data.kpis.quorum_breaches ? 'var(--danger)' : '' }">{{ data.kpis.quorum_breaches }}</span><span class="kpi-note">{{ $t('dashboard.kpiBreachesNote') }}</span></div>
        <div class="card kpi"><span class="kpi-label">{{ $t('dashboard.kpiResolutions', { year: new Date().getFullYear() }) }}</span><span class="kpi-value">{{ data.kpis.resolutions_this_year }}</span><span class="kpi-note">{{ $t('dashboard.kpiResolutionsNote', { passed: data.kpis.resolutions_passed, open: data.kpis.open_ballots }) }}</span></div>
      </div>

      <div class="grid grid-3" style="margin-top: 1rem">
        <div class="card" style="grid-column: span 2">
          <div class="card-head"><h2>{{ $t('dashboard.upcoming') }}</h2><RouterLink to="/meetings">{{ $t('common.viewAll') }}</RouterLink></div>
          <div v-if="!data.upcoming.length" class="empty">{{ $t('dashboard.noUpcoming') }}</div>
          <ul v-else class="list">
            <li v-for="m in data.upcoming" :key="m.id" class="row between">
              <div>
                <RouterLink :to="`/meetings/${m.id}`"><b>{{ m.title }}</b></RouterLink>
                <div class="small muted">{{ fmtDateTime(m.scheduled_start) }} · {{ $t('common.minutes', { n: m.duration_minutes }) }} · {{ label(m.classification) }} · {{ $t('dashboard.participantsN', { n: m.participant_count }) }}</div>
              </div>
              <div class="row"><span class="small muted">{{ fromNow(m.scheduled_start) }}</span><StatusBadge :status="m.status" /></div>
            </li>
          </ul>
        </div>
        <div class="card">
          <h2>{{ $t('dashboard.actionItems') }}</h2>
          <ul class="list">
            <li v-if="data.pending_absences !== undefined" class="row between"><span>{{ $t('dashboard.absencesToReview') }}</span><RouterLink to="/absences?tab=pending" class="badge warning">{{ data.pending_absences }}</RouterLink></li>
            <li v-if="data.minutes_awaiting_seal" class="row between"><span>{{ $t('dashboard.awaitingSeal') }}</span><span class="badge primary">{{ data.minutes_awaiting_seal.length }}</span></li>
            <li v-for="x in data.minutes_awaiting_seal || []" :key="x.meeting_id" class="small"><RouterLink :to="`/meetings/${x.meeting_id}?tab=minutes`">{{ $t('dashboard.sealLink', { title: x.title }) }}</RouterLink></li>
            <li v-if="data.open_anomalies !== undefined" class="row between"><span>{{ $t('dashboard.openAnomalies') }}</span><RouterLink to="/audit?tab=anomalies" class="badge" :class="data.open_anomalies ? 'danger' : 'success'">{{ data.open_anomalies }}</RouterLink></li>
            <li class="row between"><span>{{ $t('dashboard.unread') }}</span><RouterLink to="/notifications" class="badge info">{{ data.kpis.unread_notifications }}</RouterLink></li>
            <li class="row between"><span>{{ $t('dashboard.votesWaiting') }}</span><span class="badge" :class="data.my_pending_votes.length ? 'danger' : ''">{{ data.my_pending_votes.length }}</span></li>
          </ul>
        </div>
      </div>

      <div class="grid grid-3" style="margin-top: 1rem">
        <div class="card">
          <h2>{{ $t('dashboard.perMonth') }}</h2>
          <div class="bars">
            <div v-for="m in data.meetings_by_month" :key="m.month" class="bar">
              <b>{{ m.meetings }}</b>
              <span :style="{ height: (100 * m.meetings / maxMeetings) + '%' }" />
              <small>{{ fmtMonth('1 ' + m.month) }}</small>
            </div>
          </div>
        </div>
        <div class="card">
          <h2>{{ $t('dashboard.breakdown') }}</h2>
          <div v-for="(n, s) in data.attendance_breakdown" :key="s" style="margin: .6rem 0">
            <div class="row between small"><span>{{ label(s) }}</span><b>{{ n }}</b></div>
            <div class="progress"><span :style="{ width: (100 * n / totalAttendance) + '%', background: colors[s] }" /></div>
          </div>
        </div>
        <div class="card">
          <h2>{{ $t('dashboard.kpiBreaches') }}</h2>
          <div v-if="!data.quorum_breaches.length" class="empty">{{ $t('dashboard.allMetQuorum') }}</div>
          <ul v-else class="list">
            <li v-for="q in data.quorum_breaches" :key="q.id">
              <RouterLink :to="`/meetings/${q.id}`">{{ q.title }}</RouterLink>
              <div class="small muted">{{ $t('dashboard.breachLine', { present: q.present, eligible: q.eligible, percent: q.percent, required: q.required_percent }) }}</div>
            </li>
          </ul>
        </div>
      </div>

      <div class="card" style="margin-top: 1rem">
        <div class="card-head"><h2>{{ $t('dashboard.recentResolutions') }}</h2><RouterLink to="/resolutions">{{ $t('dashboard.register') }}</RouterLink></div>
        <div v-if="!data.recent_resolutions.length" class="empty">{{ $t('dashboard.noResolutions') }}</div>
        <div v-else class="table-wrap">
          <table class="table">
            <thead><tr><th>{{ $t('resolutions.number') }}</th><th>{{ $t('resolutions.resolution') }}</th><th>{{ $t('resolutions.meeting') }}</th><th>{{ $t('resolutions.outcome') }}</th><th>{{ $t('resolutions.certified') }}</th></tr></thead>
            <tbody>
              <tr v-for="r in data.recent_resolutions" :key="r.id">
                <td class="mono">{{ r.number }}</td><td>{{ r.title }}</td>
                <td><RouterLink :to="`/meetings/${r.meeting.id}`">{{ r.meeting.title }}</RouterLink></td>
                <td><StatusBadge :status="r.outcome" /></td><td>{{ fmtDate(r.certified_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { downloadFile } from '../api/http'
import Icon from '../components/Icon.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { roleName } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { fmtDate, fmtDateTime, fmtMonth, fromNow, label } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const data = ref(null)
const colors = { present: '#15803d', proxy: '#4338ca', excused: '#0369a1', unexcused: '#b91c1c' }

const firstName = computed(() => (auth.user?.full_name || '').replace(/^Dr\.\s*/, '').split(' ')[0])
const greeting = computed(() => { const h = new Date().getHours(); return h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening' })
const maxMeetings = computed(() => Math.max(1, ...data.value.meetings_by_month.map((m) => m.meetings)))
const totalAttendance = computed(() => Object.values(data.value.attendance_breakdown).reduce((a, b) => a + b, 0) || 1)

onMounted(async () => {
  try { data.value = (await http.get('/dashboard')).data } catch (e) { toast.error(e) }
})
</script>
