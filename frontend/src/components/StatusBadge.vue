<template>
  <span class="badge" :class="tone">
    <span v-if="status === 'live'" class="live-dot" />
    {{ text || label(status) }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { label } from '../utils/format'

const props = defineProps({ status: String, text: String })

const TONES = {
  live: 'danger', scheduled: 'info', ended: '', cancelled: 'warning',
  present: 'success', proxy: 'primary', excused: 'info', unexcused: 'danger', pending: 'warning',
  approved: 'success', rejected: 'danger', accepted: 'success', declined: 'danger', tentative: 'warning',
  draft: 'warning', published: 'info', sealed: 'success', none: '',
  open: 'danger', closed: '', passed: 'success', failed: 'danger',
  active: 'success', invited: 'warning', disabled: 'danger', acknowledged: 'success',
  high: 'danger', medium: 'warning', low: 'info',
  internal: 'info', confidential: 'warning', strictly_confidential: 'danger',
}
const tone = computed(() => TONES[props.status] ?? '')
</script>
