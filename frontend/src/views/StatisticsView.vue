<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { formatDate, questionTypeLabels } from '../utils.js'

const route = useRoute()
const survey = ref(null)
const stats = ref(null)
const responses = ref(null)
const textDetails = ref({})
const loading = ref(true)
const error = ref('')

function width(count, options) {
  const max = Math.max(1, ...options.map((item) => item.count))
  return `${Math.round((count / max) * 100)}%`
}

async function loadText(questionId, page = 1) {
  try {
    textDetails.value[questionId] = await apiRequest(`/surveys/${route.params.id}/statistics/questions/${questionId}?page=${page}&page_size=10`)
  } catch (reason) { error.value = reason.message }
}

async function loadResponses(page = 1) {
  try {
    responses.value = await apiRequest(`/surveys/${route.params.id}/responses?page=${page}&page_size=10`)
  } catch (reason) { error.value = reason.message }
}

async function load() {
  try {
    ;[survey.value, stats.value] = await Promise.all([
      apiRequest(`/surveys/${route.params.id}`),
      apiRequest(`/surveys/${route.params.id}/statistics`),
    ])
    await loadResponses()
  } catch (reason) { error.value = reason.message } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <LoadingBlock v-if="loading" />
  <section v-else-if="stats && survey">
    <header class="page-heading split-heading">
      <div><p class="kicker">答卷统计</p><h1>{{ stats.title }}</h1><p>查看每道题的回答人数与选项分布。</p></div>
      <div class="metric-block"><strong>{{ stats.submission_count }}</strong><span>份有效提交</span></div>
    </header>
    <StatusMessage type="error" :message="error" />

    <div v-if="!stats.question_stats.length" class="empty-state compact-empty"><h2>暂无题目</h2><p>问卷添加题目后，这里会显示对应统计。</p></div>
    <div class="stats-list">
      <article v-for="(item, index) in stats.question_stats" :key="item.question_id" class="stat-section">
        <header><span>{{ index + 1 }}</span><div><h2>{{ item.title }}</h2><p>{{ questionTypeLabels[item.type] || '其他题型' }} · {{ item.answered_count }} 人回答</p></div></header>
        <div v-if="item.options" class="bar-list">
          <div v-for="option in item.options" :key="option.id" class="bar-row">
            <div><span>{{ option.label }}</span><strong>{{ option.count }}</strong></div>
            <div class="bar-track"><span :style="{ width: width(option.count, item.options) }"></span></div>
          </div>
        </div>
        <dl v-else-if="item.type === 'number'" class="number-stats">
          <div><dt>平均值</dt><dd>{{ item.average ?? '—' }}</dd></div>
          <div><dt>最小值</dt><dd>{{ item.minimum ?? '—' }}</dd></div>
          <div><dt>最大值</dt><dd>{{ item.maximum ?? '—' }}</dd></div>
        </dl>
        <div v-else>
          <button class="button secondary compact" type="button" @click="loadText(item.question_id)">查看文本回答</button>
          <div v-if="textDetails[item.question_id]" class="text-responses">
            <blockquote v-for="(answer, answerIndex) in textDetails[item.question_id].items" :key="answerIndex"><p>{{ answer.value }}</p><small>{{ formatDate(answer.submitted_at) }}</small></blockquote>
            <div class="pagination"><button class="text-button" :disabled="textDetails[item.question_id].page <= 1" @click="loadText(item.question_id, textDetails[item.question_id].page - 1)">上一页</button><span>第 {{ textDetails[item.question_id].page }} 页 / 共 {{ textDetails[item.question_id].total }} 条</span><button class="text-button" :disabled="textDetails[item.question_id].page * textDetails[item.question_id].page_size >= textDetails[item.question_id].total" @click="loadText(item.question_id, textDetails[item.question_id].page + 1)">下一页</button></div>
          </div>
        </div>
      </article>
    </div>

    <section class="responses-section">
      <div class="section-heading"><div><h2>答卷记录</h2><p>{{ survey.allow_anonymous ? '匿名问卷：这里不会显示填写者姓名。' : '这里会显示填写者用户名。' }}</p></div></div>
      <div v-if="responses?.items.length" class="response-table-wrap">
        <table><thead><tr><th>提交时间</th><th v-if="!survey.allow_anonymous">填写者</th><th>回答数</th></tr></thead><tbody><tr v-for="response in responses.items" :key="response.id"><td>{{ formatDate(response.submitted_at) }}</td><td v-if="!survey.allow_anonymous">{{ response.respondent_username }}</td><td>{{ response.answers.length }}</td></tr></tbody></table>
        <div class="pagination"><button class="text-button" :disabled="responses.page <= 1" @click="loadResponses(responses.page - 1)">上一页</button><span>第 {{ responses.page }} 页 / 共 {{ responses.total }} 条</span><button class="text-button" :disabled="responses.page * responses.page_size >= responses.total" @click="loadResponses(responses.page + 1)">下一页</button></div>
      </div>
      <p v-else class="muted">尚无答卷。</p>
    </section>
    <footer class="sticky-actions"><RouterLink class="button quiet" to="/dashboard">返回工作台</RouterLink><RouterLink class="button secondary" :to="`/surveys/${survey.id}/edit`">查看问卷</RouterLink></footer>
  </section>
  <StatusMessage v-else type="error" :message="error" />
</template>
