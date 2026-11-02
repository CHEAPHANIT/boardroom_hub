<template>
  <span v-if="user" class="person">
    <span class="avatar">{{ initials(user.full_name) }}</span>
    <span><b>{{ user.full_name }}</b><small>{{ sub ?? (user.title || roleName(user.role) || user.email) }}</small></span>
  </span>
  <span v-else class="muted">—</span>
</template>

<script setup>
import { roleName } from '../i18n'
import { initials } from '../utils/format'

defineProps({ user: Object, sub: String })
</script>
