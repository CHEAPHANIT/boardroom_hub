<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('reports.title') }}</h1><p>{{ $t('reports.subtitle') }}</p></div>
    </div>
    <div class="card">
      <div class="inline-form">
        <div class="field"><label>{{ $t('reports.report') }}</label>
          <select v-model="kind"><option v-for="k in kinds" :key="k" :value="k">{{ $t('reports.kinds.' + k) }}</option></select>
        </div>
        <div class="field"><label>{{ $t('reports.period') }}</label>
          <select v-model="preset" @change="applyPreset"><option v-for="p in presets" :key="p" :value="p">{{ $t('reports.presets.' + p) }}</option></select>
        </div>
        <div class="field"><label>{{ $t('minutes.from') }}</label><input v-model="from" type="date" @change="preset = 'custom'" /></div>
        <div class="field"><label>{{ $t('minutes.to') }}</label><input v-model="to" type="date" @change="preset = 'custom'" /></div>
        <button class="btn primary" @click="run">{{ $t('reports.generate') }}</button>
        <template v-if="auth.can('export.data') && report">
          <button class="btn" @click="downloadFile(url('pdf'), kind + '-report.pdf')"><Icon name="download" />PDF</button>
          <button class="btn" @click="downloadFile(url('csv'), kind + '-report.csv')">CSV</button>
        </template>
      </div>
    </div>

    <div v-if="report" class="card">
      <h2>{{ $t('reports.kinds.' + kind) }}</h2>
      <p class="muted small">{{ fmtDate(report.from) }} – {{ fmtDate(report.to) }}</p>
      <div class="grid grid-4" style="margin-bottom: 1rem">
        <div v-for="(v, k) in summary" :key="k" class="kpi" style="background: var(--surface-2); padding: .8rem; border-radius: 8px">
          <span class="kpi-label">{{ col(k) }}</span><span class="kpi-value" style="font-size: 1.4rem">{{ v ?? '—' }}</span>
        </div>
      </div>
      <div v-if="!report.rows.length" class="empty">{{ $t('reports.noData') }}</div>
      <div v-else class="table-wrap">
        <table class="table">
          <thead><tr><th v-for="c in report.columns" :key="c">{{ col(c) }}</th></tr></thead>
          <tbody><tr v-for="(r, i) in report.rows" :key="i"><td v-for="c in report.columns" :key="c">{{ cell(c, r[c]) }}</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { downloadFile } from '../api/http'
import Icon from '../components/Icon.vue'
import { has, roleName, t } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { fmtDate, label } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const kinds = ['attendance', 'voting', 'compliance']
const presets = ['month', 'quarter', 'year', 'custom']
const kind = ref('attendance')
const preset = ref('quarter')
const from = ref('')
const to = ref('')
const report = ref(null)
const iso = (d) => d.toISOString().slice(0, 10)

const summary = computed(() => Object.fromEntries(Object.entries(report.value || {}).filter(([k]) => !['rows', 'columns', 'title', 'from', 'to'].includes(k))))
const col = (c) => (has('reports.cols.' + c) ? t('reports.cols.' + c) : label(c))
function cell(c, v) {
  if (c.endsWith('_at') || c === 'date') return fmtDate(v)
  if (c === 'minutes') return label(v)
  if (c === 'quorum_met') return v === 'Yes' ? t('common.yes') : t('common.no')
  if (c === 'role') return roleName(v)
  return v
}

function applyPreset() {
  const now = new Date()
  const end = new Date(now.getTime() + 86400000)
  let start = new Date(now.getTime() - 90 * 86400000)
  if (preset.value === 'month') start = new Date(now.getFullYear(), now.getMonth(), 1)
  if (preset.value === 'year') start = new Date(now.getFullYear(), 0, 1)
  if (preset.value !== 'custom') { from.value = iso(start); to.value = iso(end) }
}
const url = (format) => `/dashboard/reports/${kind.value}?from=${from.value}T00:00:00&to=${to.value}T23:59:59&format=${format}`

async function run() {
  try { report.value = (await http.get(url('json'))).data } catch (e) { toast.error(e) }
}

onMounted(() => { applyPreset(); run() })
</script>
