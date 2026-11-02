<template>
  <AppShell v-if="auth.isLoggedIn && !route.meta.public">
    <RouterView :key="route.path" />
  </AppShell>
  <RouterView v-else />
  <div class="toasts">
    <div v-for="t in toast.items" :key="t.id" class="toast" :class="t.type" role="status" @click="toast.dismiss(t.id)">
      <span class="toast-text">{{ t.message }}</span>
      <button type="button" class="toast-close" :aria-label="$t('common.close')" @click.stop="toast.dismiss(t.id)">×</button>
      <span class="toast-bar" :style="{ animationDuration: t.timeout + 'ms' }" />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from './components/AppShell.vue'
import { useAuth } from './stores/auth'
import { useToast } from './stores/toast'

const route = useRoute()
const auth = useAuth()
const toast = useToast()
window.addEventListener('bh:error', (e) => toast.error(e.detail))

// Safety net: remove any toast whose time is up, even if its own timer was lost.
let watchdog = null
onMounted(() => { watchdog = setInterval(() => toast.prune(), 1000) })
onBeforeUnmount(() => clearInterval(watchdog))
</script>
