<template>
  <AuthLayout>
    <h2>{{ $t('auth.newPasswordTitle') }}</h2>
    <div v-if="error" class="alert danger">{{ error }}</div>
    <div v-if="done" class="alert success">{{ $t('auth.resetDone') }} <RouterLink to="/login">{{ $t('auth.signIn') }}</RouterLink></div>
    <form v-else class="stack" @submit.prevent="submit">
      <div class="field">
        <label for="pw">{{ $t('auth.newPassword') }}</label>
        <PasswordInput id="pw" v-model="password" autocomplete="new-password" required />
        <small>{{ $t('auth.passwordRule') }}</small>
      </div>
      <div class="field">
        <label for="pw2">{{ $t('auth.confirmPassword') }}</label>
        <PasswordInput id="pw2" v-model="confirm" autocomplete="new-password" required />
      </div>
      <button class="btn primary block" :disabled="busy">{{ $t('auth.resetButton') }}</button>
    </form>
  </AuthLayout>
</template>

<script setup>
import PasswordInput from '../../components/PasswordInput.vue'
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import http, { errorMessage } from '../../api/http'
import AuthLayout from '../../components/AuthLayout.vue'
import { t } from '../../i18n'

const route = useRoute()
const password = ref('')
const confirm = ref('')
const busy = ref(false)
const done = ref(false)
const error = ref('')

async function submit() {
  if (password.value !== confirm.value) { error.value = t('auth.passwordMismatch'); return }
  busy.value = true
  error.value = ''
  try {
    await http.post('/auth/reset-password', { token: route.query.token, new_password: password.value })
    done.value = true
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
</script>
