<template>
  <div class="lang-switch" role="group" :aria-label="$t('lang.switch')">
    <button type="button" :class="{ on: i18n.locale === 'en' }" @click="setLocale('en')">EN</button>
    <button type="button" class="km" :class="{ on: i18n.locale === 'km' }" @click="setLocale('km')">ខ្មែរ</button>
  </div>
</template>

<script setup>
import { i18n, setLocale } from '../i18n'
</script>
