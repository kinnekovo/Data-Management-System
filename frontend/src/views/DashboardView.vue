<script setup>
import { onMounted, ref } from 'vue'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { formatDate, statusLabels } from '../utils.js'

const surveys = ref([])
const loading = ref(true)
const error = ref('')
const notice = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    surveys.value = (await apiRequest('/surveys')).items
  } catch (reason) {
    error.value = reason.message
  } finally {
    loading.value = false
  }
}

async function copyShare(survey) {
  const link = `${window.location.origin}${survey.share_path}`
  try {
    await navigator.clipboard.writeText(link)
    notice.value = `已复制“${survey.title}”的分享链接`
  } catch {
    window.prompt('复制问卷链接', link)
  }
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-heading split-heading">
      <div><p class="kicker">创作与管理</p><h1>我的问卷</h1><p>草稿先完善结构，发布后即可分享并查看实时统计。</p></div>
      <RouterLink class="button" to="/surveys/new">新建问卷</RouterLink>
    </header>
    <StatusMessage type="success" :message="notice" />
    <StatusMessage type="error" :message="error" />
    <LoadingBlock v-if="loading" />
    <div v-else-if="!surveys.length" class="empty-state">
      <h2>还没有问卷</h2><p>创建第一份草稿，添加题目与跳转规则后再发布。</p>
      <RouterLink class="button" to="/surveys/new">创建第一份问卷</RouterLink>
    </div>
    <div v-else class="survey-list">
      <article v-for="survey in surveys" :key="survey.id" class="survey-row">
        <div>
          <div class="row-title"><h2>{{ survey.title }}</h2><span class="status-badge" :class="survey.status">{{ statusLabels[survey.status] }}</span></div>
          <p>{{ survey.description || '暂无说明' }}</p>
          <small>{{ survey.question_count }} 题 · 创建于 {{ formatDate(survey.created_at) }} · 截止 {{ formatDate(survey.expires_at) }}</small>
        </div>
        <div class="row-actions">
          <RouterLink class="button secondary compact" :to="`/surveys/${survey.id}/edit`">{{ survey.status === 'draft' ? '编辑' : '查看' }}</RouterLink>
          <RouterLink class="button secondary compact" :to="`/surveys/${survey.id}/statistics`">统计</RouterLink>
          <button class="button quiet compact" type="button" @click="copyShare(survey)">复制链接</button>
        </div>
      </article>
    </div>
  </section>
</template>
