<template>
  <AuthLayout>
    <template v-if="!mfaToken">
      <h2>{{ $t('auth.signIn') }}</h2>
      <p class="muted">{{ $t('auth.signInSub') }}</p>
      <div v-if="route.query.expired" class="alert warning">{{ $t('auth.expired') }}</div>
      <div v-if="error" class="alert danger">{{ error }}</div>
      <form class="stack" @submit.prevent="submit">
        <div class="field">
          <label for="email">{{ $t('common.email') }}</label>
          <input id="email" v-model.trim="email" type="email" autocomplete="username" required />
        </div>
        <div class="field">
          <label for="password">{{ $t('auth.password') }}</label>
          <PasswordInput id="password" v-model="password" autocomplete="current-password" required />
        </div>
        <button class="btn primary block" :disabled="busy">{{ busy ? $t('auth.signingIn') : $t('auth.signIn') }}</button>
      </form>
      <p class="small" style="margin-top: 1rem"><RouterLink to="/forgot-password">{{ $t('auth.forgot') }}</RouterLink></p>
      <div class="demo-accounts">
        <div class="muted">{{ $t('auth.demo') }} <code>Password123!</code></div>
        <button v-for="a in demo" :key="a.email" type="button" class="btn sm" @click="fill(a.email)">{{ roleName(a.role) }}</button>
      </div>
    </template>
    <template v-else>
      <h2>{{ $t('auth.mfaTitle') }}</h2>
      <p class="muted">{{ $t('auth.mfaSub') }}</p>
      <div v-if="error" class="alert danger">{{ error }}</div>
      <form class="stack" @submit.prevent="verify">
        <div class="field">
          <label for="code">{{ $t('auth.code') }}</label>
          <input id="code" v-model.trim="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" required />
        </div>
        <button class="btn primary block" :disabled="busy">{{ $t('auth.verify') }}</button>
        <button type="button" class="btn ghost block" @click="mfaToken = ''">{{ $t('common.back') }}</button>
      </form>
    </template>
  </AuthLayout>
</template>

<script setup>
import PasswordInput from '../../components/PasswordInput.vue'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { errorMessage } from '../../api/http'
import AuthLayout from '../../components/AuthLayout.vue'
import { roleName } from '../../i18n'
import { useAuth } from '../../stores/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const email = ref('')
const password = ref('')
const code = ref('')
const mfaToken = ref('')
const error = ref('')
const busy = ref(false)

const demo = [
  { role: 'Administrator', email: 'admin@boardroom.local' },
  { role: 'Board Chair', email: 'chair@boardroom.local' },
  { role: 'Company Secretary', email: 'secretary@boardroom.local' },
  { role: 'Independent Director', email: 'vannak@boardroom.local' },
  { role: 'Executive Director', email: 'rithy@boardroom.local' },
  { role: 'Legal Counsel', email: 'counsel@boardroom.local' },
  { role: 'Auditor', email: 'auditor@boardroom.local' },
  { role: 'Observer', email: 'observer@boardroom.local' },
]

function fill(e) { email.value = e; password.value = 'Password123!' }

function done() { router.push(route.query.next || '/') }

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const data = await auth.login(email.value, password.value)
    if (data.mfa_required) mfaToken.value = data.mfa_token
    else done()
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}

async function verify() {
  busy.value = true
  error.value = ''
  try { await auth.verifyMfa(mfaToken.value, code.value); done() } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
</script>
