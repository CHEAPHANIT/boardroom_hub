<template>
  <Modal :title="$t('viewer.title', { title: doc.title, v: version })" wide @close="close">
    <div class="row between" style="margin-bottom: .75rem">
      <span class="small muted">{{ $t('viewer.note') }}</span>
      <StatusBadge :status="doc.classification" />
    </div>
    <div class="viewer" @contextmenu.prevent>
      <iframe v-if="url && isPdf" :src="url + '#toolbar=0&navpanes=0'" :title="$t('viewer.document')" />
      <img v-else-if="url && isImage" :src="url" :alt="$t('viewer.document')" draggable="false" />
      <div v-else-if="url" class="empty" style="padding-top: 25vh">{{ $t('viewer.noPreview') }}<br />
        <span v-if="doc.can_download">{{ $t('viewer.useDownload') }}</span><span v-else>{{ $t('viewer.restricted') }}</span></div>
      <div v-else class="empty" style="padding-top: 25vh">{{ error || $t('viewer.loading') }}</div>
      <div class="watermark"><span v-for="i in 30" :key="i">{{ mark }}</span></div>
    </div>
  </Modal>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'
import Modal from './Modal.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({ doc: { type: Object, required: true }, version: { type: Number, required: true } })
const emit = defineEmits(['close'])
const auth = useAuth()
const url = ref('')
const mime = ref('')
const error = ref('')
const mark = `${auth.user.full_name} · ${auth.user.email} · ${new Date().toLocaleDateString()}`
const isPdf = computed(() => mime.value.includes('pdf'))
const isImage = computed(() => mime.value.startsWith('image/'))

onMounted(async () => {
  try {
    const res = await http.get(`/documents/${props.doc.id}/view`, { params: { version: props.version }, responseType: 'blob' })
    mime.value = res.data.type || ''
    url.value = URL.createObjectURL(res.data)
  } catch (e) {
    const blob = e?.response?.data
    if (blob instanceof Blob) { try { e.response.data = JSON.parse(await blob.text()) } catch { /* ignore */ } }
    error.value = errorMessage(e)
  }
})
onBeforeUnmount(() => { if (url.value) URL.revokeObjectURL(url.value) })
function close() { emit('close') }
</script>
