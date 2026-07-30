import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '../views/Dashboard.vue'
import Interview from '../views/Interview.vue'
import Login from '../views/Login.vue'
import Profile from '../views/Profile.vue'
import Register from '../views/Register.vue'
import Report from '../views/Report.vue'
import ResumeUpload from '../views/ResumeUpload.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: Login, meta: { guest: true } },
    { path: '/register', component: Register, meta: { guest: true } },
    {
      path: '/dashboard',
      component: Dashboard,
      meta: { requiresAuth: true, title: '控制台' },
    },
    {
      path: '/resume/new',
      component: ResumeUpload,
      meta: { requiresAuth: true, title: '开始面试' },
    },
    {
      path: '/interviews/:id',
      component: Interview,
      meta: { requiresAuth: true, title: '模拟面试' },
    },
    {
      path: '/interviews/:id/report',
      component: Report,
      meta: { requiresAuth: true, title: '面试报告' },
    },
    {
      path: '/profile',
      component: Profile,
      meta: { requiresAuth: true, title: '个人设置' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) {
    await auth.initialize()
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return '/dashboard'
  }
  document.title = to.meta.title
    ? `${to.meta.title} · PrepPilot`
    : 'PrepPilot · AI 模拟面试'
  return true
})

export default router
