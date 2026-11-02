<template>
  <div class="shell">
    <aside class="sidebar" :class="{ open: menuOpen }" @click="menuOpen = false">
      <div class="brand">
        <div class="brand-logo"><Icon name="shield" :size="20" /></div>
        <div><b>Boardroom Hub</b><small>{{ $t('nav.brandSub') }}</small></div>
      </div>
      <nav>
        <div class="nav-group">
          <span>{{ $t('nav.workspace') }}</span>
          <RouterLink class="nav-link" to="/"><Icon name="dashboard" />{{ $t('nav.dashboard') }}</RouterLink>
          <RouterLink v-if="auth.can('meeting.view')" class="nav-link" :class="{ active: route.path.startsWith('/meetings') }" to="/meetings"><Icon name="calendar" />{{ $t('nav.meetings') }}</RouterLink>
          <RouterLink class="nav-link" to="/absences"><Icon name="absence" />{{ $t('nav.absences') }}</RouterLink>
          <RouterLink v-if="auth.can('meeting.view')" class="nav-link" to="/resolutions"><Icon name="gavel" />{{ $t('nav.resolutions') }}</RouterLink>
          <RouterLink v-if="auth.can('report.view')" class="nav-link" to="/reports"><Icon name="chart" />{{ $t('nav.reports') }}</RouterLink>
          <RouterLink class="nav-link" to="/notifications"><Icon name="bell" />{{ $t('nav.notifications') }}</RouterLink>
        </div>
        <div v-if="auth.canAny('user.manage', 'role.manage', 'audit.view')" class="nav-group">
          <span>{{ $t('nav.administration') }}</span>
          <RouterLink v-if="auth.can('user.manage')" class="nav-link" to="/admin/users"><Icon name="users" />{{ $t('nav.users') }}</RouterLink>
          <RouterLink v-if="auth.canAny('role.manage', 'audit.view')" class="nav-link" to="/admin/roles"><Icon name="shield" />{{ $t('nav.roles') }}</RouterLink>
          <RouterLink v-if="auth.can('audit.view')" class="nav-link" to="/audit"><Icon name="log" />{{ $t('nav.audit') }}</RouterLink>
          <RouterLink v-if="auth.canAny('user.manage', 'audit.view')" class="nav-link" to="/admin/outbox"><Icon name="mail" />{{ $t('nav.outbox') }}</RouterLink>
        </div>
        <div class="nav-group">
          <span>{{ $t('nav.account') }}</span>
          <RouterLink class="nav-link" to="/profile"><Icon name="user" />{{ $t('nav.profile') }}</RouterLink>
          <a class="nav-link" href="#" @click.prevent="logout"><Icon name="logout" />{{ $t('nav.signOut') }}</a>
        </div>
      </nav>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="row">
          <button class="icon-btn menu-btn" :aria-label="$t('nav.openMenu')" @click.stop="menuOpen = !menuOpen"><Icon name="menu" /></button>
          <b>{{ route.meta.title ? $t(route.meta.title) : 'Boardroom Hub' }}</b>
        </div>
        <div class="row">
          <LangSwitch />
          <button class="icon-btn" :aria-label="$t('nav.notifications')" @click="router.push('/notifications')">
            <Icon name="bell" />
            <span v-if="unread" class="dot">{{ unread > 99 ? '99+' : unread }}</span>
          </button>
          <RouterLink to="/profile" class="person" style="color: inherit">
            <span class="avatar">{{ initials(auth.user?.full_name) }}</span>
            <span class="hide-sm"><b>{{ auth.user?.full_name }}</b><small>{{ roleName(auth.user?.role?.name) }}</small></span>
          </RouterLink>
        </div>
      </header>
      <main class="content"><slot /></main>
    </div>
  </div>
</template>

<script setup>
import { useToast } from '../stores/toast'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { i18n, roleName, t } from '../i18n'
import { useAuth } from '../stores/auth'
import { initials } from '../utils/format'
import Icon from './Icon.vue'
import LangSwitch from './LangSwitch.vue'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const menuOpen = ref(false)
const toast = useToast()
const unread = ref(0)
let timer = null

async function poll() {
  try { unread.value = (await http.get('/notifications', { params: { unread: 1, limit: 1 } })).data.unread } catch { /* ignore */ }
}

async function logout() {
  toast.clear()
  await auth.logout()
  router.push('/login')
}

watch(() => i18n.locale, () => { if (route.meta.title) document.title = `${t(route.meta.title)} · Boardroom Hub` })
onMounted(() => { poll(); timer = setInterval(poll, 20000) })
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.fullPath, poll)
</script>
