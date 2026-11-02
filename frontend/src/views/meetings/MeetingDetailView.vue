<template>
  <div v-if="meeting">
    <div class="page-head">
      <div>
        <div class="row" style="gap: .5rem"><RouterLink to="/meetings" class="small">← {{ $t('nav.meetings') }}</RouterLink></div>
        <h1 class="row" style="gap: .6rem">{{ meeting.title }} <StatusBadge :status="meeting.status" /></h1>
        <p>{{ fmtDateTime(meeting.scheduled_start) }} – {{ fmtTime(meeting.scheduled_end) }} · {{ label(meeting.classification) }} · {{ $t('detail.host') }} {{ meeting.host?.full_name }}</p>
      </div>
      <div class="actions">
        <button v-if="meeting.is_host && meeting.status === 'scheduled'" class="btn success" @click="act('start')"><Icon name="video" />{{ $t('detail.start') }}</button>
        <button v-if="meeting.is_host && meeting.status === 'live'" class="btn danger" @click="confirmEnd"><Icon name="x" />{{ $t('detail.end') }}</button>
        <RouterLink v-if="auth.can('meeting.update') && meeting.status === 'scheduled'" class="btn" :to="`/meetings/${meeting.id}/edit`">{{ $t('common.edit') }}</RouterLink>
        <button v-if="auth.can('meeting.update') && meeting.status === 'scheduled'" class="btn" @click="remind">{{ $t('detail.sendReminder') }}</button>
        <button class="btn" @click="downloadFile(`/meetings/${meeting.id}/ics`, 'meeting.ics')"><Icon name="calendar" />.ics</button>
        <button v-if="auth.can('meeting.cancel') && meeting.status === 'scheduled'" class="btn danger" @click="showCancel = true">{{ $t('detail.cancelMeeting') }}</button>
      </div>
    </div>

    <div v-if="meeting.status === 'cancelled'" class="alert warning">{{ $t('detail.cancelledAlert', { reason: meeting.cancel_reason }) }}</div>

    <div class="tabs">
      <button v-for="tb in tabs" :key="tb" class="tab" :class="{ active: tab === tb }" @click="setTab(tb)">{{ $t('detail.tabs.' + tb) }}</button>
    </div>

    <OverviewTab v-if="tab === 'overview'" :meeting="meeting" @reload="load" />
    <ParticipantsTab v-else-if="tab === 'participants'" :meeting="meeting" @reload="load" />
    <DocumentsTab v-else-if="tab === 'documents'" :meeting="meeting" />
    <MinutesTab v-else-if="tab === 'minutes'" :meeting="meeting" />
    <VotingTab v-else-if="tab === 'voting'" :meeting="meeting" />

    <Modal v-if="showCancel" :title="$t('detail.cancelMeeting')" @close="showCancel = false">
      <p>{{ $t('detail.cancelInfo') }}</p>
      <div class="field"><label>{{ $t('detail.reason') }}</label><textarea v-model="cancelReason" rows="3" :placeholder="$t('detail.reasonPh')" /></div>
      <template #footer>
        <button class="btn" @click="showCancel = false">{{ $t('detail.keepMeeting') }}</button>
        <button class="btn danger" @click="cancelMeeting">{{ $t('detail.cancelMeeting') }}</button>
      </template>
    </Modal>
  </div>
  <div v-else class="card empty">{{ error || $t('common.loading') }}</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http, { downloadFile, errorMessage } from '../../api/http'
import Icon from '../../components/Icon.vue'
import Modal from '../../components/Modal.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import { serverText, t } from '../../i18n'
import { useAuth } from '../../stores/auth'
import { useToast } from '../../stores/toast'
import { fmtDateTime, fmtTime, label } from '../../utils/format'
import DocumentsTab from './tabs/DocumentsTab.vue'
import MinutesTab from './tabs/MinutesTab.vue'
import OverviewTab from './tabs/OverviewTab.vue'
import ParticipantsTab from './tabs/ParticipantsTab.vue'
import VotingTab from './tabs/VotingTab.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const meeting = ref(null)
const error = ref('')
const showCancel = ref(false)
const cancelReason = ref('')
let timer = null

const tabs = computed(() => [
  'overview',
  auth.can('attendance.view') && 'participants',
  auth.can('document.view') && 'documents',
  auth.can('minutes.view') && 'minutes',
  'voting',
].filter(Boolean))
const tab = computed(() => route.query.tab || 'overview')

function setTab(key) { router.replace({ query: { ...route.query, tab: key } }) }

async function load() {
  try { meeting.value = (await http.get(`/meetings/${route.params.id}`)).data } catch (e) { error.value = errorMessage(e) }
}

async function act(action) {
  try {
    meeting.value = (await http.post(`/meetings/${meeting.value.id}/${action}`)).data
    toast.success(action === 'start' ? t('detail.started') : t('detail.ended'))
  } catch (e) { toast.error(e) }
}

function confirmEnd() { if (confirm(t('detail.confirmEnd'))) act('end') }

async function remind() {
  try { toast.success(serverText((await http.post(`/meetings/${meeting.value.id}/remind`)).data.message)) } catch (e) { toast.error(e) }
}

async function cancelMeeting() {
  try {
    meeting.value = (await http.post(`/meetings/${meeting.value.id}/cancel`, { reason: cancelReason.value })).data
    showCancel.value = false
    toast.success(t('detail.cancelled'))
  } catch (e) { toast.error(e) }
}

onMounted(() => {
  load()
  timer = setInterval(() => { if (meeting.value?.status === 'live' && !document.hidden) load() }, 15000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>
