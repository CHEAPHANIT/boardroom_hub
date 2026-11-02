import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setLogoutHandler } from './api/http'
import { useAuth } from './stores/auth'
import i18nPlugin, { applyDocumentLang } from './i18n'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(i18nPlugin)
applyDocumentLang()

setLogoutHandler(() => {
  const auth = useAuth(pinia)
  auth.clear()
  if (router.currentRoute.value.name !== 'login') router.push({ name: 'login', query: { expired: '1' } })
})

app.mount('#app')
