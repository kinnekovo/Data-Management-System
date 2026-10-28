<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth, logout, restoreSession } from './auth.js'

const route = useRoute()
const router = useRouter()

function signOut() {
  logout()
  router.push('/login')
}

onMounted(restoreSession)
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/dashboard" aria-label="问卷工作台">
        <span class="brand-mark" aria-hidden="true">问</span>
        <span><strong>问卷工作台</strong><small>创建 · 填写 · 统计</small></span>
      </RouterLink>
      <nav v-if="auth.user" aria-label="主导航">
        <RouterLink to="/dashboard">我的问卷</RouterLink>
        <RouterLink to="/questions">题目库</RouterLink>
        <RouterLink to="/question-banks">题库</RouterLink>
        <RouterLink to="/surveys/new">新建问卷</RouterLink>
        <span class="user-chip">{{ auth.user.username }}</span>
        <button class="button quiet compact" type="button" @click="signOut">退出</button>
      </nav>
      <nav v-else-if="!route.meta.publicFlow" aria-label="账户导航">
        <RouterLink to="/login">登录</RouterLink>
        <RouterLink class="button compact" to="/register">注册</RouterLink>
      </nav>
    </header>
    <main class="page-frame"><RouterView /></main>
  </div>
</template>
