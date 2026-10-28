<script setup>
import { onMounted, ref } from 'vue'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { formatDate, questionTypeLabels } from '../utils.js'

const questions = ref([])
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const search = ref('')
const scope = ref('all')
const draft = ref({ type: 'single_choice', title: '' })

function contentForDraft() {
  const choice = ['single_choice', 'multiple_choice'].includes(draft.value.type)
  return {
    type: draft.value.type,
    title: draft.value.title.trim(),
    options: choice ? [{ label: '选项 1' }, { label: '选项 2' }] : [],
    validation: draft.value.type === 'number' ? { integer_only: false } : {},
    change_note: '在题目库中创建',
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams({ scope: scope.value })
    if (search.value.trim()) query.set('search', search.value.trim())
    questions.value = (await apiRequest(`/questions?${query}`)).items
  } catch (reason) { error.value = reason.message } finally { loading.value = false }
}

async function createQuestion() {
  if (!draft.value.title.trim()) { error.value = '请填写题目标题'; return }
  busy.value = true
  error.value = ''
  try {
    const created = await apiRequest('/questions', { method: 'POST', body: contentForDraft() })
    questions.value.unshift(created)
    draft.value.title = ''
    notice.value = '题目已保存到个人题目库'
  } catch (reason) { error.value = reason.message } finally { busy.value = false }
}

async function archiveQuestion(question) {
  if (!window.confirm(`归档“${question.current_version.title}”吗？已使用它的问卷不会受影响。`)) return
  try {
    await apiRequest(`/questions/${question.id}`, { method: 'DELETE' })
    questions.value = questions.value.filter((item) => item.id !== question.id)
    notice.value = '题目已归档，已有问卷快照保持不变'
  } catch (reason) { error.value = reason.message }
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-heading split-heading">
      <div><p class="kicker">复用与版本管理</p><h1>题目库</h1><p>保存常用题目，在多个问卷间复用，并通过不可变版本保护已发布问卷。</p></div>
      <RouterLink class="button secondary" to="/question-banks">管理题库</RouterLink>
    </header>
    <StatusMessage type="success" :message="notice" />
    <StatusMessage type="error" :message="error" />

    <form class="library-create" @submit.prevent="createQuestion">
      <label>题型<select v-model="draft.type"><option v-for="(label, value) in questionTypeLabels" :key="value" :value="value">{{ label }}</option></select></label>
      <label>题目标题<input v-model="draft.title" maxlength="500" placeholder="例如：你的年龄" /></label>
      <button class="button" type="submit" :disabled="busy">保存题目</button>
    </form>

    <div class="library-toolbar">
      <div class="segmented"><button type="button" :class="{ active: scope === 'all' }" @click="scope = 'all'; load()">全部</button><button type="button" :class="{ active: scope === 'mine' }" @click="scope = 'mine'; load()">我的</button><button type="button" :class="{ active: scope === 'shared' }" @click="scope = 'shared'; load()">共享给我</button></div>
      <form class="search-form" @submit.prevent="load"><input v-model="search" placeholder="搜索题目标题" /><button class="button secondary compact" type="submit">搜索</button></form>
    </div>

    <LoadingBlock v-if="loading" />
    <div v-else-if="!questions.length" class="empty-state compact-empty"><h2>没有匹配的题目</h2><p>可以在上方创建题目，或等待其他用户共享。</p></div>
    <div v-else class="library-grid">
      <article v-for="question in questions" :key="question.id" class="library-card">
        <div class="library-card-meta"><span>{{ questionTypeLabels[question.current_version.type] }}</span><span>v{{ question.current_version.version_no }}</span><span v-if="question.access === 'shared'">来自 {{ question.owner_username }}</span></div>
        <h2>{{ question.current_version.title }}</h2>
        <p>{{ question.current_version.options.length ? `${question.current_version.options.length} 个选项` : '无选项题型' }} · 更新于 {{ formatDate(question.updated_at) }}</p>
        <footer><RouterLink class="button secondary compact" :to="`/questions/${question.id}`">版本、共享与统计</RouterLink><button v-if="question.access === 'owner'" class="text-button danger" type="button" @click="archiveQuestion(question)">归档</button></footer>
      </article>
    </div>
  </section>
</template>
