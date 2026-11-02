<template>
  <AuthLayout>
    <h2>{{ $t('auth.activateTitle') }}</h2>
    <div v-if="error" class="alert danger">{{ error }}</div>
    <template v-if="invite">
      <p class="muted">{{ $t('auth.activateWelcome', { name: invite.full_name, role: roleName(invite.role), email: invite.email }) }}</p>
      <form class="stack" @submit.prevent="submit">
        <div class="field">
          <label for="name">{{ $t('common.fullName') }}</label>
          <input id="name" v-model.trim="fullName" required />
        </div>
        <div class="field">
          <label for="pw">{{ $t('auth.createPassword') }}</label>
          <PasswordInput id="pw" v-model="password" autocomplete="new-password" required />
          <small>{{ $t('auth.passwordRule') }}</small>
        </div>
        <div class="field">
          <label for="pw2">{{ $t('auth.confirmPassword') }}</label>
          <PasswordInput id="pw2" v-model="confirm" autocomplete="new-password" required />
        </div>
        <button class="btn primary block" :disabled="busy">{{ $t('auth.activateButton') }}</button>
      </form>
    </template>
    <p v-else-if="!error" class="muted">{{ $t('auth.checkingInvite') }}</p>
  </AuthLayout>
</template>

<script setup>
import PasswordInput from '../../components/PasswordInput.vue'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http, { errorMessage } from '../../api/http'
import AuthLayout from '../../components/AuthLayout.vue'
import { roleName, t } from '../../i18n'
import { useAuth } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const invite = ref(null)
const fullName = ref('')
const password = ref('')
const confirm = ref('')
const busy = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    invite.value = (await http.get(`/auth/invite/${encodeURIComponent(route.query.token || 'x')}`)).data
    fullName.value = invite.value.full_name
  } catch (e) { error.value = errorMessage(e) }
})

async function submit() {
  if (password.value !== confirm.value) { error.value = t('auth.passwordMismatch'); return }
  busy.value = true
  error.value = ''
  try {
    const { data } = await http.post('/auth/activate', { token: route.query.token, password: password.value, full_name: fullName.value })
    auth.setSession(data)
    router.push('/')
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
</script>
