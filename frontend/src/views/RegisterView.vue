<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiRequest } from '../api/client.js'
import StatusMessage from '../components/StatusMessage.vue'

const router = useRouter()
const username = ref('')
const password = ref('')
const confirmation = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busy.value = true
  try {
    await apiRequest('/auth/register', { method: 'POST', body: { username: username.value.trim(), password: password.value } })
    await router.replace({ path: '/login', query: { registered: '1' } })
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
      <p class="kicker">创建者与填写者共用账号</p>
      <h1>创建你的问卷身份</h1>
      <p>注册后可以创建和填写问卷。填写匿名问卷时，创建者看不到你的账号。</p>
    </div>
    <form class="form-panel" @submit.prevent="submit">
      <h2>注册</h2>
      <label>用户名<input v-model="username" required minlength="3" maxlength="32" autocomplete="username" /></label>
      <label>密码<input v-model="password" required minlength="8" maxlength="128" type="password" autocomplete="new-password" /></label>
      <label>确认密码<input v-model="confirmation" required type="password" autocomplete="new-password" /></label>
      <StatusMessage type="error" :message="error" />
      <button class="button wide" :disabled="busy" type="submit">{{ busy ? '正在注册…' : '注册账号' }}</button>
      <p class="form-foot">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
    </form>
  </section>
</template>
