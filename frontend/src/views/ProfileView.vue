<template>
  <div>
    <div class="page-head"><div><h1>{{ $t('profile.title') }}</h1><p>{{ $t('profile.subtitle') }}</p></div></div>
    <div class="grid grid-2">
      <div class="card">
        <h2>{{ $t('profile.executive') }}</h2>
        <form class="stack" @submit.prevent="saveProfile">
          <div class="field"><label>{{ $t('common.fullName') }}</label><input v-model.trim="p.full_name" required /></div>
          <div class="field"><label>{{ $t('common.title') }}</label><input v-model.trim="p.title" /></div>
          <div class="field"><label>{{ $t('common.organization') }}</label><input v-model.trim="p.organization" /></div>
          <div class="field"><label>{{ $t('profile.timezone') }}</label><input v-model.trim="p.timezone" placeholder="Asia/Bangkok" /></div>
          <div class="field"><label>{{ $t('lang.switch') }}</label>
            <select :value="i18n.locale" @change="setLocale($event.target.value)"><option value="en">English</option><option value="km">ខ្មែរ (Khmer)</option></select>
          </div>
          <label class="check"><input v-model="p.notify_email" type="checkbox" />{{ $t('profile.emailNotif') }}</label>
          <label class="check"><input v-model="p.notify_inapp" type="checkbox" />{{ $t('profile.inappNotif') }}</label>
          <dl class="dl small"><dt>{{ $t('common.email') }}</dt><dd>{{ auth.user.email }}</dd><dt>{{ $t('common.role') }}</dt><dd>{{ roleName(auth.user.role?.name) }}</dd><dt>{{ $t('voting.weight') }}</dt><dd>{{ auth.user.vote_weight }}</dd><dt>{{ $t('profile.lastSignIn') }}</dt><dd>{{ fmtDateTime(auth.user.last_login_at) }}</dd></dl>
          <div><button class="btn primary">{{ $t('profile.save') }}</button></div>
        </form>
      </div>
      <div class="stack">
        <div class="card">
          <h2>{{ $t('profile.changePassword') }}</h2>
          <form class="stack" @submit.prevent="changePassword">
            <div class="field"><label>{{ $t('profile.currentPassword') }}</label><PasswordInput v-model="pw.current_password" autocomplete="current-password" required /></div>
            <div class="field"><label>{{ $t('auth.newPassword') }}</label><PasswordInput v-model="pw.new_password" autocomplete="new-password" required /><small>{{ $t('auth.passwordRule') }}</small></div>
            <div><button class="btn">{{ $t('profile.updatePassword') }}</button></div>
          </form>
        </div>
        <div class="card">
          <h2>{{ $t('profile.mfa') }} <span class="badge" :class="auth.user.mfa_enabled ? 'success' : 'warning'">{{ auth.user.mfa_enabled ? $t('common.on') : $t('common.off') }}</span></h2>
          <template v-if="auth.user.mfa_enabled">
            <p class="small">{{ $t('profile.mfaOnInfo') }}</p>
            <form class="inline-form" @submit.prevent="disableMfa">
              <div class="field"><label>{{ $t('profile.confirmPassword') }}</label><PasswordInput v-model="mfaPassword" required /></div>
              <button class="btn danger">{{ $t('profile.mfaOff') }}</button>
            </form>
          </template>
          <template v-else-if="setup">
            <p class="small">{{ $t('profile.mfaStep1') }}</p>
            <img :src="setup.qr" :alt="$t('profile.qrAlt')" style="width: 180px; height: 180px; background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 6px" />
            <p class="small muted">{{ $t('profile.manualKey') }} <code>{{ setup.secret }}</code></p>
            <form class="inline-form" @submit.prevent="enableMfa">
              <div class="field"><label>{{ $t('profile.mfaStep2') }}</label><input v-model.trim="code" maxlength="6" inputmode="numeric" required /></div>
              <button class="btn primary">{{ $t('profile.mfaOn') }}</button>
            </form>
          </template>
          <template v-else>
            <p class="small">{{ $t('profile.mfaIntro') }}</p>
            <button class="btn primary" @click="startSetup"><Icon name="shield" />{{ $t('profile.setupMfa') }}</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import PasswordInput from '../components/PasswordInput.vue'
import { reactive, ref } from 'vue'
import http from '../api/http'
import Icon from '../components/Icon.vue'
import { i18n, roleName, setLocale, t } from '../i18n'
import { useAuth } from '../stores/auth'
import { useToast } from '../stores/toast'
import { fmtDateTime } from '../utils/format'

const auth = useAuth()
const toast = useToast()
const u = auth.user
const p = reactive({ full_name: u.full_name, title: u.title, organization: u.organization, timezone: u.timezone, notify_email: u.notify_email, notify_inapp: u.notify_inapp })
const pw = reactive({ current_password: '', new_password: '' })
const setup = ref(null)
const code = ref('')
const mfaPassword = ref('')

async function saveProfile() {
  try { auth.user = (await http.put('/auth/me', p)).data; toast.success(t('profile.saved')) } catch (e) { toast.error(e) }
}
async function changePassword() {
  try { await http.post('/auth/change-password', pw); pw.current_password = pw.new_password = ''; toast.success(t('profile.passwordUpdated')) } catch (e) { toast.error(e) }
}
async function startSetup() { try { setup.value = (await http.post('/auth/mfa/setup')).data } catch (e) { toast.error(e) } }
async function enableMfa() {
  try { auth.user = (await http.post('/auth/mfa/enable', { code: code.value })).data; setup.value = null; code.value = ''; toast.success(t('profile.mfaEnabled')) } catch (e) { toast.error(e) }
}
async function disableMfa() {
  try { auth.user = (await http.post('/auth/mfa/disable', { password: mfaPassword.value })).data; mfaPassword.value = ''; toast.success(t('profile.mfaDisabled')) } catch (e) { toast.error(e) }
}
</script>
