<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('outbox.title') }}</h1><p>{{ $t('outbox.subtitle') }}</p></div>
      <div class="actions"><input v-model="q" :placeholder="$t('outbox.searchPh')" style="width: 280px" @input="debounced" /></div>
    </div>
    <div class="grid grid-2">
      <div class="card">
        <div v-if="!mails.length" class="empty">{{ $t('outbox.none') }}</div>
        <ul v-else class="list">
          <li v-for="m in mails" :key="m.id" style="cursor: pointer" :style="{ background: selected?.id === m.id ? 'var(--primary-50)' : '' }" @click="selected = m">
            <div class="row between"><b class="small">{{ m.to_email }}</b><span class="small muted">{{ fmtDateTime(m.created_at) }}</span></div>
            <div>{{ m.subject }}</div>
            <span class="badge">{{ label(m.kind) }}</span>
          </li>
        </ul>
      </div>
      <div class="card">
        <template v-if="selected">
          <h2>{{ selected.subject }}</h2>
          <p class="small muted">{{ $t('outbox.to', { email: selected.to_email }) }} · {{ fmtDateTime(selected.created_at) }}</p>
          <hr />
          <p class="pre" v-html="linkify(selected.body)" />
        </template>
        <div v-else class="empty">{{ $t('outbox.select') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import http from '../../api/http'
import { useToast } from '../../stores/toast'
import { fmtDateTime, label } from '../../utils/format'

const toast = useToast()
const mails = ref([])
const selected = ref(null)
const q = ref('')
let timer = null

const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
function linkify(text) {
  return esc(text || '').replace(/(https?:\/\/[^\s<]+)/g, (u) => {
    try {
      const url = new URL(u.replace(/&amp;/g, '&'))
      const local = url.pathname + url.search
      return `<a href="${local}">${u}</a>`
    } catch { return u }
  })
}
async function load() { try { mails.value = (await http.get('/notifications/outbox', { params: { q: q.value || undefined } })).data } catch (e) { toast.error(e) } }
function debounced() { clearTimeout(timer); timer = setTimeout(load, 300) }
onMounted(load)
</script>
