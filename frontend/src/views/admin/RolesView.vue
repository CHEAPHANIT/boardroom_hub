<template>
  <div>
    <div class="page-head">
      <div><h1>{{ $t('rolesView.title') }}</h1><p>{{ $t('rolesView.subtitle') }}</p></div>
      <div class="actions"><button v-if="canManage" class="btn primary" @click="openRole()"><Icon name="plus" />{{ $t('rolesView.create') }}</button></div>
    </div>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'roles' }" @click="tab = 'roles'">{{ $t('rolesView.roles') }}</button>
      <button class="tab" :class="{ active: tab === 'matrix' }" @click="tab = 'matrix'">{{ $t('rolesView.matrix') }}</button>
    </div>

    <div v-if="tab === 'roles'" class="grid grid-2">
      <div v-for="r in roles" :key="r.id" class="card">
        <div class="card-head">
          <div><h2 style="margin: 0">{{ roleName(r.name) }}</h2><div class="small muted">{{ roleDesc(r) }}</div></div>
          <div class="row"><span class="badge">{{ $t('rolesView.userCount', { n: r.user_count }) }}</span><span v-if="r.is_system" class="badge info">{{ $t('rolesView.builtIn') }}</span></div>
        </div>
        <div class="small" style="display: flex; flex-wrap: wrap; gap: .3rem">
          <span v-for="p in r.permissions" :key="p" class="badge primary" :title="p">{{ permLabel(p) }}</span>
          <span v-if="!r.permissions.length" class="muted">{{ $t('rolesView.noPerms') }}</span>
        </div>
        <div v-if="canManage" class="actions" style="margin-top: .9rem">
          <button class="btn sm" @click="openRole(r)">{{ $t('rolesView.editPerms') }}</button>
          <button v-if="!r.is_system" class="btn sm ghost" :disabled="r.user_count > 0" @click="removeRole(r)">{{ $t('common.delete') }}</button>
        </div>
      </div>
    </div>

    <div v-else-if="matrix" class="card">
      <div class="table-wrap">
        <table class="table matrix">
          <thead><tr><th>{{ $t('rolesView.feature') }}</th><th v-for="r in matrix.roles" :key="r.id" class="rot">{{ roleName(r.name) }}</th></tr></thead>
          <tbody>
            <template v-for="(group, g) in grouped" :key="g">
              <tr><td :colspan="matrix.roles.length + 1" style="background: var(--surface-2)"><b>{{ groupLabel(g) }}</b></td></tr>
              <tr v-for="p in group" :key="p.code">
                <td>{{ permLabel(p.code, p.label) }}<div class="small muted mono">{{ p.code }}</div></td>
                <td v-for="r in matrix.roles" :key="r.id" class="c"><span :class="p.granted[r.id] ? 'yes' : 'no'">{{ p.granted[r.id] ? '✓' : '·' }}</span></td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <Modal v-if="editing" :title="editing.id ? $t('rolesView.editTitle', { name: roleName(editing.name) }) : $t('rolesView.create')" wide @close="editing = null">
      <div class="form-grid" style="margin-bottom: 1rem">
        <div class="field"><label>{{ $t('rolesView.roleName') }}</label><input v-model.trim="editing.name" :disabled="editing.is_system" :placeholder="$t('rolesView.roleNamePh')" /></div>
        <div class="field"><label>{{ $t('common.description') }}</label><input v-model.trim="editing.description" /></div>
      </div>
      <div class="grid grid-2">
        <div v-for="(group, g) in catalogueGrouped" :key="g">
          <h3>{{ groupLabel(g) }}</h3>
          <label v-for="p in group" :key="p.code" class="check" style="padding: .2rem 0"><input v-model="editing.permissions" type="checkbox" :value="p.code" />{{ permLabel(p.code, p.label) }} <span class="small muted mono">{{ p.code }}</span></label>
        </div>
      </div>
      <template #footer><button class="btn" @click="editing = null">{{ $t('common.cancel') }}</button><button class="btn primary" @click="saveRole">{{ $t('rolesView.saveRole') }}</button></template>
    </Modal>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../../api/http'
import Icon from '../../components/Icon.vue'
import Modal from '../../components/Modal.vue'
import { has, roleName, t } from '../../i18n'
import { useAuth } from '../../stores/auth'
import { useToast } from '../../stores/toast'

const auth = useAuth()
const toast = useToast()
const canManage = computed(() => auth.can('role.manage'))
const tab = ref(canManage.value ? 'roles' : 'matrix')
const roles = ref([])
const matrix = ref(null)
const catalogue = ref([])
const editing = ref(null)

const permLabel = (code, fallback) => (has('perms.' + code.replace('.', '_')) ? t('perms.' + code.replace('.', '_')) : (fallback || code))
const groupLabel = (g) => (has('permGroups.' + g.replace(/\W+/g, '_')) ? t('permGroups.' + g.replace(/\W+/g, '_')) : g)
const roleDesc = (r) => (r.is_system && has('roleDesc.' + r.name.replace(/\s+/g, '_')) ? t('roleDesc.' + r.name.replace(/\s+/g, '_')) : r.description)
const groupBy = (list) => list.reduce((acc, p) => { (acc[p.group] ||= []).push(p); return acc }, {})
const grouped = computed(() => groupBy(matrix.value?.permissions || []))
const catalogueGrouped = computed(() => groupBy(catalogue.value))

async function load() {
  try {
    if (canManage.value) roles.value = (await http.get('/roles')).data
    matrix.value = (await http.get('/roles/matrix')).data
    catalogue.value = (await http.get('/auth/permissions')).data
  } catch (e) { toast.error(e) }
}
function openRole(r) { editing.value = r ? { ...r, permissions: [...r.permissions] } : { name: '', description: '', permissions: ['meeting.view'] } }
async function saveRole() {
  const e = editing.value
  try {
    if (e.id) await http.put(`/roles/${e.id}`, { name: e.name, description: e.description, permissions: e.permissions })
    else await http.post('/roles', { name: e.name, description: e.description, permissions: e.permissions })
    toast.success(t('rolesView.saved'))
    editing.value = null
    load()
    auth.refreshMe()
  } catch (err) { toast.error(err) }
}
async function removeRole(r) {
  if (!confirm(t('rolesView.confirmDelete', { name: roleName(r.name) }))) return
  try { await http.delete(`/roles/${r.id}`); load() } catch (e) { toast.error(e) }
}

onMounted(load)
</script>
