<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../auth.js'
import StatusMessage from '../components/StatusMessage.vue'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await login(username.value.trim(), password.value)
    const target = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.replace(target)
  } catch (reason) {
    error.value = reason.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="auth-layout">
    <div class="auth-copy">
      <p class="kicker">欢迎回来</p>
      <h1>登录后继续创建或填写问卷</h1>
      <p>登录后可以管理自己的问卷，或继续填写分享给你的问卷。</p>
    </div>
    <form class="form-panel" @submit.prevent="submit">
      <h2>登录</h2>
      <label>用户名<input v-model="username" required minlength="3" maxlength="32" autocomplete="username" /></label>
      <label>密码<input v-model="password" required minlength="8" maxlength="128" type="password" autocomplete="current-password" /></label>
      <StatusMessage type="error" :message="error" />
      <button class="button wide" :disabled="busy" type="submit">{{ busy ? '正在登录…' : '登录' }}</button>
      <p class="form-foot">还没有账号？<RouterLink to="/register">创建账号</RouterLink></p>
    </form>
  </section>
</template>
