<template>
  <AuthLayout>
    <h2>{{ $t('auth.resetTitle') }}</h2>
    <p class="muted">{{ $t('auth.resetSub') }}</p>
    <div v-if="error" class="alert danger">{{ error }}</div>
    <div v-if="sent" class="alert success">
      {{ $t('auth.resetSent') }}
      <template v-if="devLink"><br /><small>{{ $t('auth.demoNoMail') }} <RouterLink :to="devPath">{{ $t('auth.openResetLink') }}</RouterLink></small></template>
    </div>
    <form v-if="!sent" class="stack" @submit.prevent="submit">
      <div class="field">
        <label for="email">{{ $t('common.email') }}</label>
        <input id="email" v-model.trim="email" type="email" required />
      </div>
      <button class="btn primary block" :disabled="busy">{{ $t('auth.sendResetLink') }}</button>
    </form>
    <p class="small" style="margin-top: 1rem"><RouterLink to="/login">{{ $t('auth.backToSignIn') }}</RouterLink></p>
  </AuthLayout>
</template>

<script setup>
import { computed, ref } from 'vue'
import http, { errorMessage } from '../../api/http'
import AuthLayout from '../../components/AuthLayout.vue'

const email = ref('')
const sent = ref(false)
const busy = ref(false)
const error = ref('')
const devLink = ref('')
const devPath = computed(() => devLink.value ? '/reset-password?' + devLink.value.split('?')[1] : '')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const { data } = await http.post('/auth/forgot-password', { email: email.value })
    devLink.value = data.dev_reset_link || ''
    sent.value = true
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
</script>
