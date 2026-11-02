<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('resolutions.title') }}</h1><p>{{ $t('resolutions.subtitle') }}</p></div>
      <div class="actions">
        <select v-model="outcome" style="width: 200px"><option value="">{{ $t('resolutions.allOutcomes') }}</option><option value="passed">{{ label('passed') }}</option><option value="failed">{{ label('failed') }}</option></select>
      </div>
    </div>
    <div class="card">
      <div v-if="!rows.length" class="empty">{{ $t('resolutions.none') }}</div>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th>{{ $t('resolutions.number') }}</th><th>{{ $t('resolutions.resolution') }}</th><th>{{ $t('resolutions.meeting') }}</th><th>{{ $t('resolutions.tally') }}</th><th>{{ $t('overview.quorum') }}</th><th>{{ $t('resolutions.outcome') }}</th><th>{{ $t('resolutions.certified') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in shown" :key="r.id">
              <td class="mono"><b>{{ r.number }}</b></td>
              <td>{{ r.title }}<div v-if="r.text" class="small muted">{{ r.text }}</div></td>
              <td><RouterLink :to="`/meetings/${r.meeting.id}?tab=voting`">{{ r.meeting.title }}</RouterLink></td>
              <td class="small">{{ (r.tallies || []).map((x) => `${optionLabel(x.option)} ${x.votes}`).join(' · ') }}</td>
              <td><span class="badge" :class="r.quorum_met ? 'success' : 'danger'">{{ r.quorum_met ? $t('participants.met') : $t('participants.notMet') }}</span></td>
              <td><StatusBadge :status="r.outcome" /></td>
              <td class="small">{{ fmtDate(r.certified_at) }}<div class="muted">{{ r.certified_by?.full_name }}</div></td>
              <td><button v-if="auth.can('export.data')" class="btn sm" @click="downloadFile(`/voting/ballots/${r.ballot_id}/export?format=pdf`, r.number + '.pdf')"><Icon name="download" />PDF</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="small muted" style="margin-top: .75rem">{{ $t('resolutions.hashNote') }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { downloadFile } from '../api/http'
import Icon from '../components/Icon.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { has, t } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { fmtDate, label } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const rows = ref([])
const outcome = ref('')
const shown = computed(() => rows.value.filter((r) => !outcome.value || r.outcome === outcome.value))
const optionLabel = (o) => (has('voting.opt.' + o) ? t('voting.opt.' + o) : o)

onMounted(async () => { try { rows.value = (await http.get('/voting/resolutions')).data } catch (e) { toast.error(e) } })
</script>
