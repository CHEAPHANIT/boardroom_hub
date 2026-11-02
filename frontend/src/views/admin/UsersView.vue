<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('users.title') }}</h1><p>{{ $t('users.subtitle') }}</p></div>
      <div class="actions"><button class="btn primary" @click="openInvite"><Icon name="plus" />{{ $t('users.invite') }}</button></div>
    </div>
    <div class="card">
      <div class="inline-form" style="margin-bottom: 1rem">
        <div class="field" style="flex: 1"><label>{{ $t('common.search') }}</label><input v-model="q" :placeholder="$t('users.searchPh')" @input="debounced" /></div>
        <div class="field"><label>{{ $t('common.role') }}</label><select v-model="roleFilter" @change="load"><option value="">{{ $t('users.allRoles') }}</option><option v-for="r in roles" :key="r.id" :value="r.id">{{ roleName(r.name) }}</option></select></div>
        <div class="field"><label>{{ $t('common.status') }}</label><select v-model="statusFilter" @change="load"><option value="">{{ $t('common.all') }}</option><option v-for="s in ['active', 'invited', 'disabled']" :key="s" :value="s">{{ label(s) }}</option></select></div>
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>{{ $t('users.user') }}</th><th>{{ $t('common.role') }}</th><th>{{ $t('voting.weight') }}</th><th>{{ $t('common.status') }}</th><th>MFA</th><th>{{ $t('profile.lastSignIn') }}</th><th></th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td><Person :user="u" :sub="u.email" /><div class="small muted" style="margin-left: 40px">{{ u.title }}</div></td>
              <td>
                <select :value="u.role_id" style="width: 210px" :disabled="u.id === auth.user.id" @change="assignRole(u, $event.target.value)">
                  <option v-for="r in roles" :key="r.id" :value="r.id">{{ roleName(r.name) }}</option>
                </select>
              </td>
              <td><input :value="u.vote_weight" type="number" min="1" max="100" style="width: 70px" @change="setWeight(u, $event.target.value)" /></td>
              <td><StatusBadge :status="u.status" /> <span v-if="u.locked" class="badge danger">{{ $t('users.locked') }}</span></td>
              <td>{{ u.mfa_enabled ? $t('common.on') : '—' }}</td>
              <td class="small">{{ fmtDateTime(u.last_login_at) }}</td>
              <td class="right">
                <div class="actions" style="justify-content: flex-end">
                  <button v-if="u.locked" class="btn sm" @click="act(u, 'unlock', $t('users.unlocked'))">{{ $t('users.unlock') }}</button>
                  <button v-if="u.status === 'invited'" class="btn sm" @click="resend(u)">{{ $t('users.resend') }}</button>
                  <button v-if="u.status === 'active' && u.id !== auth.user.id" class="btn sm danger" @click="confirmRevoke(u)">{{ $t('users.revoke') }}</button>
                  <button v-if="u.status === 'disabled'" class="btn sm success" @click="act(u, 'reactivate', $t('users.restored'))">{{ $t('users.restore') }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <Modal v-if="showInvite" :title="$t('users.inviteTitle')" @close="showInvite = false">
      <div v-if="inviteLink" class="alert success">
        {{ $t('users.inviteSent', { email: invite.email }) }}<br />
        <small>{{ $t('users.demoLink') }} <a :href="inviteLink" target="_blank">{{ inviteLink }}</a></small>
      </div>
      <form v-else id="invite-form" class="form-grid" @submit.prevent="sendInvite">
        <div class="field"><label>{{ $t('common.fullName') }} *</label><input v-model.trim="invite.full_name" required /></div>
        <div class="field"><label>{{ $t('users.corpEmail') }} *</label><input v-model.trim="invite.email" type="email" required /></div>
        <div class="field"><label>{{ $t('common.title') }}</label><input v-model.trim="invite.title" :placeholder="$t('users.titlePh')" /></div>
        <div class="field"><label>{{ $t('common.organization') }}</label><input v-model.trim="invite.organization" /></div>
        <div class="field"><label>{{ $t('users.govRole') }} *</label><select v-model="invite.role_id" required><option v-for="r in roles" :key="r.id" :value="r.id">{{ roleName(r.name) }}</option></select></div>
        <div class="field"><label>{{ $t('voting.weight') }}</label><input v-model.number="invite.vote_weight" type="number" min="1" max="100" /></div>
      </form>
      <template #footer>
        <button class="btn" @click="showInvite = false">{{ $t('common.close') }}</button>
        <button v-if="!inviteLink" class="btn primary" form="invite-form">{{ $t('users.sendInvite') }}</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import http from '../../api/http'
import Icon from '../../components/Icon.vue'
import Modal from '../../components/Modal.vue'
import Person from '../../components/Person.vue'
import StatusBadge from '../../components/StatusBadge.vue'
import { roleName, t } from '../../i18n'
import { useAuth } from '../../stores/auth'
import { useToast } from '../../stores/toast'
import { fmtDateTime, label } from '../../utils/format'

const auth = useAuth()
const toast = useToast()
const users = ref([])
const roles = ref([])
const q = ref('')
const roleFilter = ref('')
const statusFilter = ref('')
const showInvite = ref(false)
const inviteLink = ref('')
const invite = reactive({ full_name: '', email: '', title: '', organization: '', role_id: null, vote_weight: 1 })
let timer = null

async function load() {
  try { users.value = (await http.get('/users', { params: { q: q.value || undefined, role_id: roleFilter.value || undefined, status: statusFilter.value || undefined } })).data } catch (e) { toast.error(e) }
}
function debounced() { clearTimeout(timer); timer = setTimeout(load, 300) }

function openInvite() {
  Object.assign(invite, { full_name: '', email: '', title: '', organization: '', role_id: roles.value.find((r) => r.name === 'Independent Director')?.id, vote_weight: 1 })
  inviteLink.value = ''
  showInvite.value = true
}
async function sendInvite() {
  try {
    const { data } = await http.post('/users/invite', invite)
    inviteLink.value = data.dev_invite_link || ' '
    toast.success(t('users.inviteToast'))
    load()
  } catch (e) { toast.error(e) }
}
async function assignRole(u, roleId) {
  try { await http.post(`/users/${u.id}/role`, { role_id: Number(roleId) }); toast.success(t('users.roleAssigned', { name: u.full_name })) } catch (e) { toast.error(e) }
  load()
}
async function setWeight(u, w) {
  try { await http.put(`/users/${u.id}`, { vote_weight: Number(w) }); toast.success(t('users.weightUpdated')) } catch (e) { toast.error(e) }
  load()
}
function confirmRevoke(u) { if (confirm(t('users.confirmRevoke', { name: u.full_name }))) act(u, 'deactivate', t('users.revoked')) }
async function act(u, action, msg) { try { await http.post(`/users/${u.id}/${action}`); toast.success(msg); load() } catch (e) { toast.error(e) } }
async function resend(u) {
  try { const { data } = await http.post(`/users/${u.id}/resend-invite`); toast.success(t('users.resent')); if (data.dev_invite_link) prompt(t('users.demoLink'), data.dev_invite_link) } catch (e) { toast.error(e) }
}

onMounted(async () => {
  try { roles.value = (await http.get('/roles')).data } catch (e) { toast.error(e) }
  load()
})
</script>
