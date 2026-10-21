<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiRequest } from '../api/client.js'
import StatusMessage from '../components/StatusMessage.vue'
import { fromLocalInput } from '../utils.js'

const router = useRouter()
const form = reactive({ title: '', description: '', allow_anonymous: false, allow_multiple_submissions: false, expires_at: '' })
const busy = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const survey = await apiRequest('/surveys', {
      method: 'POST',
      body: { ...form, expires_at: fromLocalInput(form.expires_at) },
    })
    await router.replace(`/surveys/${survey.id}/edit`)
  } catch (reason) {
    error.value = reason.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="narrow-page">
    <header class="page-heading"><p class="kicker">新建草稿</p><h1>填写问卷基本信息</h1><p>创建后可以继续添加题目和跳转规则，确认无误后再发布。</p></header>
    <form class="form-panel large" @submit.prevent="submit">
      <label>问卷标题<input v-model="form.title" required maxlength="200" placeholder="例如：课程学习体验调查" /></label>
      <label>问卷说明<textarea v-model="form.description" maxlength="5000" rows="5" placeholder="说明填写目的与预计耗时"></textarea></label>
      <label>截止时间（可选）<input v-model="form.expires_at" type="datetime-local" /></label>
      <div class="choice-stack">
        <label class="check-row"><input v-model="form.allow_anonymous" type="checkbox" /><span><strong>对创建者匿名</strong><small>填写者仍需登录，但创建者看不到其账号。</small></span></label>
        <label class="check-row"><input v-model="form.allow_multiple_submissions" type="checkbox" /><span><strong>允许同一用户多次提交</strong><small>开启后，同一账号可以重复填写并提交。</small></span></label>
      </div>
      <StatusMessage type="error" :message="error" />
      <div class="form-actions"><RouterLink class="button quiet" to="/dashboard">取消</RouterLink><button class="button" :disabled="busy" type="submit">{{ busy ? '正在创建…' : '创建并添加题目' }}</button></div>
    </form>
  </section>
</template>
