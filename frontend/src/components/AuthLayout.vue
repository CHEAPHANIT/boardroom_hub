<template>
  <div class="auth-page">
    <section class="auth-hero">
      <div class="brand" style="padding: 0">
        <div class="brand-logo"><Icon name="shield" :size="20" /></div>
        <div><b>Boardroom Hub</b><small style="color:#c7d2fe">{{ $t('auth.heroBrand') }}</small></div>
      </div>
      <div>
        <h1>{{ $t('auth.heroTitle') }}</h1>
        <ul>
          <li>{{ $t('auth.hero1') }}</li>
          <li>{{ $t('auth.hero2') }}</li>
          <li>{{ $t('auth.hero3') }}</li>
          <li>{{ $t('auth.hero4') }}</li>
        </ul>
      </div>
      <small style="color:#a5b4fc">Vue 3 · Flask RESTful API · SQLite</small>
    </section>
    <section class="auth-panel">
      <div style="width: min(400px, 100%)">
        <div class="row" style="justify-content: flex-end; margin-bottom: .75rem"><LangSwitch /></div>
        <div class="auth-card card"><slot /></div>
      </div>
    </section>
  </div>
</template>

<script setup>
import Icon from './Icon.vue'
import LangSwitch from './LangSwitch.vue'
</script>
