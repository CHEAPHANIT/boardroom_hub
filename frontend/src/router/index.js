import { createRouter, createWebHistory } from 'vue-router'
import { t } from '../i18n'
import { useAuth } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/auth/LoginView.vue'), meta: { public: true } },
  { path: '/forgot-password', name: 'forgot', component: () => import('../views/auth/ForgotPasswordView.vue'), meta: { public: true } },
  { path: '/reset-password', name: 'reset', component: () => import('../views/auth/ResetPasswordView.vue'), meta: { public: true } },
  { path: '/activate', name: 'activate', component: () => import('../views/auth/ActivateView.vue'), meta: { public: true } },

  { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: 'titles.dashboard' } },
  { path: '/meetings', name: 'meetings', component: () => import('../views/meetings/MeetingsView.vue'), meta: { title: 'titles.meetings', perm: 'meeting.view' } },
  { path: '/meetings/new', name: 'meeting-new', component: () => import('../views/meetings/MeetingFormView.vue'), meta: { title: 'titles.newMeeting', perm: 'meeting.create' } },
  { path: '/meetings/:id/edit', name: 'meeting-edit', component: () => import('../views/meetings/MeetingFormView.vue'), meta: { title: 'titles.editMeeting', perm: 'meeting.update' } },
  { path: '/meetings/:id', name: 'meeting', component: () => import('../views/meetings/MeetingDetailView.vue'), meta: { title: 'titles.meeting', perm: 'meeting.view' } },
  { path: '/absences', name: 'absences', component: () => import('../views/AbsencesView.vue'), meta: { title: 'titles.absences' } },
  { path: '/resolutions', name: 'resolutions', component: () => import('../views/ResolutionsView.vue'), meta: { title: 'titles.resolutions', perm: 'meeting.view' } },
  { path: '/reports', name: 'reports', component: () => import('../views/ReportsView.vue'), meta: { title: 'titles.reports', perm: 'report.view' } },
  { path: '/notifications', name: 'notifications', component: () => import('../views/NotificationsView.vue'), meta: { title: 'titles.notifications' } },
  { path: '/profile', name: 'profile', component: () => import('../views/ProfileView.vue'), meta: { title: 'titles.profile' } },
  { path: '/admin/users', name: 'users', component: () => import('../views/admin/UsersView.vue'), meta: { title: 'titles.users', perm: 'user.manage' } },
  { path: '/admin/roles', name: 'roles', component: () => import('../views/admin/RolesView.vue'), meta: { title: 'titles.roles', anyPerm: ['role.manage', 'audit.view'] } },
  { path: '/admin/outbox', name: 'outbox', component: () => import('../views/admin/OutboxView.vue'), meta: { title: 'titles.outbox', anyPerm: ['user.manage', 'audit.view'] } },
  { path: '/audit', name: 'audit', component: () => import('../views/AuditView.vue'), meta: { title: 'titles.audit', perm: 'audit.view' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

router.beforeEach(async (to) => {
  const auth = useAuth()
  await auth.init()
  if (to.meta.public) return auth.isLoggedIn && to.name === 'login' ? { name: 'dashboard' } : true
  if (!auth.isLoggedIn) return { name: 'login', query: { next: to.fullPath } }
  if (to.meta.perm && !auth.can(to.meta.perm)) return { name: 'dashboard' }
  if (to.meta.anyPerm && !auth.canAny(...to.meta.anyPerm)) return { name: 'dashboard' }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title ? t(to.meta.title) + ' · ' : ''}Boardroom Hub`
})

export default router
