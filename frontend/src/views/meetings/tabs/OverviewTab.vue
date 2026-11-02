<template>
  <div class="grid grid-3">
    <div class="stack" style="grid-column: span 2">
      <div class="card">
        <div class="card-head"><h2>{{ $t('overview.room') }}</h2><span v-if="meeting.room_locked" class="badge warning"><Icon name="lock" :size="12" />{{ $t('overview.locked') }}</span></div>

        <template v-if="meeting.status === 'scheduled'">
          <p class="muted">{{ $t('overview.opensWhen') }}</p>
        </template>

        <template v-else-if="meeting.status === 'live'">
          <template v-if="joined">
            <div class="room-wrap">
              <iframe class="room-frame" :src="roomSrc" allow="camera; microphone; fullscreen; display-capture" :title="$t('overview.room')" />
              <div v-if="watermarkText" class="watermark"><span v-for="i in 18" :key="i">{{ watermarkText }}</span></div>
            </div>
            <div class="row between" style="margin-top: .75rem">
              <span class="small muted">{{ $t('overview.connectedSince', { time: fmtTime(me?.first_join_at) }) }}</span>
              <div class="actions">
                <a class="btn sm" :href="roomSrc" target="_blank" rel="noopener">{{ $t('overview.newTab') }}</a>
                <button class="btn sm danger" @click="leave">{{ $t('overview.leave') }}</button>
              </div>
            </div>
          </template>
          <template v-else-if="me?.in_waiting_room || waiting">
            <div class="alert info">{{ $t('overview.waiting') }} <button class="btn sm" @click="$emit('reload')">{{ $t('overview.checkAgain') }}</button></div>
          </template>
          <template v-else-if="me">
            <p>{{ $t('overview.liveJoin') }}</p>
            <form class="inline-form" @submit.prevent="join">
              <div v-if="meeting.has_passcode && !meeting.is_host" class="field"><label>{{ $t('overview.passcode') }}</label><input v-model.trim="passcode" required inputmode="numeric" /></div>
              <button class="btn success"><Icon name="video" />{{ $t('overview.join') }}</button>
            </form>
          </template>
          <p v-else class="muted">{{ $t('overview.notParticipant') }}</p>
        </template>

        <template v-else-if="meeting.status === 'ended'">
          <p>{{ $t('overview.heldOn', { start: fmtDateTime(meeting.actual_start), end: fmtTime(meeting.actual_end) }) }}</p>
        </template>
        <p v-else class="muted">{{ $t('overview.wasCancelled') }}</p>

        <div v-if="meeting.is_host" class="alert info small" style="margin: 1rem 0 0">
          {{ $t('overview.hostDetails') }} <b class="mono">{{ meeting.room_name }}</b> · {{ $t('overview.passcode') }} <b class="mono">{{ meeting.passcode || $t('common.none') }}</b>
        </div>
      </div>

      <div class="card">
        <h2>{{ $t('overview.agenda') }}</h2>
        <div v-if="!meeting.agenda_items.length" class="empty">{{ $t('overview.noAgenda') }}</div>
        <ol v-else style="padding-left: 1.2rem; margin: 0">
          <li v-for="a in meeting.agenda_items" :key="a.id" style="margin-bottom: .7rem">
            <b>{{ a.title }}</b> <span class="small muted">· {{ a.presenter || $t('overview.tbc') }} · {{ $t('common.minutes', { n: a.duration_minutes }) }}</span>
            <div v-if="a.decision" class="small"><span class="badge success">{{ $t('minutes.decision') }}</span> {{ a.decision }}</div>
            <div v-if="a.advisory" class="small"><span class="badge info">{{ $t('minutes.advisory') }}</span> {{ a.advisory }}</div>
            <div v-if="a.finding" class="small"><span class="badge warning">{{ $t('minutes.finding') }}</span> {{ a.finding }}</div>
          </li>
        </ol>
      </div>
    </div>

    <div class="stack">
      <div class="card">
        <h2>{{ $t('common.details') }}</h2>
        <dl class="dl">
          <dt>{{ $t('meetings.classification') }}</dt><dd>{{ label(meeting.classification) }}</dd>
          <dt>{{ $t('overview.starts') }}</dt><dd>{{ fmtDateTime(meeting.scheduled_start) }}</dd>
          <dt>{{ $t('overview.duration') }}</dt><dd>{{ $t('common.minutes', { n: meeting.duration_minutes }) }}</dd>
          <dt>{{ $t('detail.host') }}</dt><dd>{{ meeting.host?.full_name }}</dd>
          <dt>{{ $t('meetingForm.cohost') }}</dt><dd>{{ meeting.cohost?.full_name || '—' }}</dd>
          <dt>{{ $t('overview.quorum') }}</dt><dd>{{ $t('overview.quorumValue', { n: meeting.quorum_percent }) }}</dd>
          <dt>{{ $t('meetingForm.participants') }}</dt><dd>{{ meeting.participant_count }}</dd>
          <dt>{{ $t('overview.waitingRoom') }}</dt><dd>{{ meeting.waiting_room ? $t('common.on') : $t('common.off') }}</dd>
          <dt>{{ $t('overview.watermark') }}</dt><dd>{{ meeting.watermark ? $t('common.on') : $t('common.off') }}</dd>
        </dl>
        <p v-if="meeting.description" class="pre" style="margin-top: .8rem">{{ meeting.description }}</p>
      </div>

      <div v-if="me && meeting.status === 'scheduled'" class="card">
        <h2>{{ $t('overview.rsvp') }}</h2>
        <p class="small muted">{{ $t('overview.current') }} <StatusBadge :status="me.rsvp" /></p>
        <div class="actions">
          <button class="btn sm success" @click="rsvp('accepted')">{{ $t('overview.accept') }}</button>
          <button class="btn sm" @click="rsvp('tentative')">{{ $t('overview.tentative') }}</button>
          <button class="btn sm danger" @click="rsvp('declined')">{{ $t('overview.decline') }}</button>
        </div>
        <p v-if="auth.can('absence.submit')" class="small" style="margin-top: .75rem">{{ $t('overview.cantAttend') }} <RouterLink :to="`/absences?meeting=${meeting.id}`">{{ $t('overview.submitAbsence') }}</RouterLink></p>
      </div>

      <div v-if="meeting.is_host && ['scheduled', 'live'].includes(meeting.status)" class="card">
        <h2>{{ $t('overview.security') }}</h2>
        <div class="stack">
          <label class="check"><input v-model="sec.waiting_room" type="checkbox" />{{ $t('overview.waitingRoom') }}</label>
          <label class="check"><input v-model="sec.watermark" type="checkbox" />{{ $t('overview.dynWatermark') }}</label>
          <label class="check"><input v-model="sec.room_locked" type="checkbox" />{{ $t('overview.lockRoom') }}</label>
          <div class="field"><label>{{ $t('overview.passcode') }}</label><input v-model.trim="sec.passcode" maxlength="12" /></div>
          <button class="btn primary sm" @click="saveSecurity">{{ $t('overview.saveSecurity') }}</button>
        </div>
      </div>

      <div v-if="meeting.series?.length" class="card">
        <h2>{{ $t('overview.series') }}</h2>
        <ul class="list">
          <li v-for="s in meeting.series" :key="s.id" class="row between">
            <RouterLink :to="`/meetings/${s.id}`" :style="{ fontWeight: s.id === meeting.id ? 700 : 400 }">{{ fmtDate(s.scheduled_start) }}</RouterLink>
            <StatusBadge :status="s.status" />
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import http from '../../../api/http'
import Icon from '../../../components/Icon.vue'
import StatusBadge from '../../../components/StatusBadge.vue'
import { t } from '../../../i18n'
import { useAuth } from '../../../stores/auth'
import { useToast } from '../../../stores/toast'
import { fmtDate, fmtDateTime, fmtTime, label } from '../../../utils/format'

const props = defineProps({ meeting: { type: Object, required: true } })
const emit = defineEmits(['reload'])
const auth = useAuth()
const toast = useToast()
const passcode = ref('')
const waiting = ref(false)
const joinInfo = ref(null)

const me = computed(() => props.meeting.my_participation)
const joined = computed(() => props.meeting.status === 'live' && me.value?.connected)
const roomSrc = computed(() => joinInfo.value?.room_url || props.meeting.room_url)
const watermarkText = computed(() => props.meeting.watermark ? `${auth.user.full_name} · ${auth.user.email}` : '')

const sec = reactive({ waiting_room: true, watermark: true, room_locked: false, passcode: '' })
watch(() => props.meeting, (m) => Object.assign(sec, { waiting_room: m.waiting_room, watermark: m.watermark, room_locked: m.room_locked, passcode: m.passcode || '' }), { immediate: true })

async function join() {
  try {
    const { data } = await http.post(`/attendance/${props.meeting.id}/join`, { passcode: passcode.value })
    if (data.waiting) { waiting.value = true; toast.info(t('overview.waiting')) } else { joinInfo.value = data; toast.success(t('overview.joined')) }
    emit('reload')
  } catch (e) { toast.error(e) }
}

async function leave() {
  try { await http.post(`/attendance/${props.meeting.id}/leave`); joinInfo.value = null; toast.info(t('overview.left')); emit('reload') } catch (e) { toast.error(e) }
}

async function rsvp(value) {
  try { await http.post(`/meetings/${props.meeting.id}/rsvp`, { rsvp: value }); toast.success(`${t('overview.rsvp')}: ${label(value)}`); emit('reload') } catch (e) { toast.error(e) }
}

async function saveSecurity() {
  try {
    const payload = { waiting_room: sec.waiting_room, watermark: sec.watermark, room_locked: sec.room_locked }
    if (sec.passcode !== (props.meeting.passcode || '')) payload.passcode = sec.passcode
    await http.put(`/meetings/${props.meeting.id}/security`, payload)
    toast.success(t('overview.securitySaved'))
    emit('reload')
  } catch (e) { toast.error(e) }
}
</script>
