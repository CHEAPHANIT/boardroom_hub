<template>
  <div class="pw-wrap">
    <input v-bind="$attrs" :type="show ? 'text' : 'password'" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />
    <button type="button" class="pw-toggle" :aria-label="show ? $t('auth.hidePassword') : $t('auth.showPassword')"
      :title="show ? $t('auth.hidePassword') : $t('auth.showPassword')" :aria-pressed="show" @click="show = !show">
      <Icon :name="show ? 'eye-off' : 'eye'" :size="18" />
    </button>
  </div>
</template>

<script setup>
// Password field with an eye button to show / hide what was typed.
import { ref } from 'vue'
import Icon from './Icon.vue'

defineOptions({ inheritAttrs: false })
defineProps({ modelValue: { type: String, default: '' } })
defineEmits(['update:modelValue'])
const show = ref(false)
</script>
