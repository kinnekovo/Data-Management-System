import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api/client.js'
import DashboardView from './views/DashboardView.vue'
import LoginView from './views/LoginView.vue'
import NewSurveyView from './views/NewSurveyView.vue'
import RegisterView from './views/RegisterView.vue'
import StatisticsView from './views/StatisticsView.vue'
import SurveyEditView from './views/SurveyEditView.vue'
import SurveyFillView from './views/SurveyFillView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: LoginView, meta: { guest: true } },
    { path: '/register', component: RegisterView, meta: { guest: true } },
    { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/surveys/new', component: NewSurveyView, meta: { requiresAuth: true } },
    { path: '/surveys/:id/edit', component: SurveyEditView, meta: { requiresAuth: true } },
    { path: '/surveys/:id/statistics', component: StatisticsView, meta: { requiresAuth: true } },
    { path: '/survey/:slug', component: SurveyFillView, meta: { requiresAuth: true, publicFlow: true } },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const hasToken = Boolean(getToken())
  if (to.meta.requiresAuth && !hasToken) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && hasToken) return '/dashboard'
  return true
})

export default router
