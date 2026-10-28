<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import QuestionEditor from '../components/QuestionEditor.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { formatDate, fromLocalInput, questionTypeLabels, statusLabels, toLocalInput } from '../utils.js'

const route = useRoute()
const router = useRouter()
const survey = ref(null)
const loading = ref(true)
const busy = ref(false)
const savingQuestion = ref('')
const error = ref('')
const notice = ref('')
const preview = ref(false)
const expiresLocal = ref('')
const draftType = ref('single_choice')
const draftTitle = ref('')
const libraryQuestions = ref([])
const banks = ref([])
const librarySource = ref('all')
const selectedLibraryQuestion = ref('')
const selectedLibraryVersion = ref('')
const selectedQuestionDetail = ref(null)
const readonly = computed(() => survey.value?.status !== 'draft')

function showError(reason) {
  if (Array.isArray(reason.details)) {
    error.value = `${reason.message}：${reason.details.map((item) => `${item.question_id || '问卷'} ${item.message}`).join('；')}`
  } else error.value = reason.message
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    survey.value = await apiRequest(`/surveys/${route.params.id}`)
    expiresLocal.value = toLocalInput(survey.value.expires_at)
    if (survey.value.status === 'draft') await loadLibrary()
  } catch (reason) {
    showError(reason)
  } finally {
    loading.value = false
  }
}

async function loadLibrary() {
  const [questionResult, bankResult] = await Promise.all([
    apiRequest('/questions'), apiRequest('/question-banks'),
  ])
  libraryQuestions.value = questionResult.items
  banks.value = bankResult.items
}

async function sourceChanged() {
  selectedLibraryQuestion.value = ''
  selectedLibraryVersion.value = ''
  selectedQuestionDetail.value = null
  if (librarySource.value === 'all') {
    await loadLibrary()
    return
  }
  const bank = await apiRequest(`/question-banks/${librarySource.value}`)
  libraryQuestions.value = bank.items.map((item) => ({ ...item.question, bank_default_version_id: item.default_version.id }))
}

async function libraryQuestionChanged() {
  if (!selectedLibraryQuestion.value) return
  selectedQuestionDetail.value = await apiRequest(`/questions/${selectedLibraryQuestion.value}`)
  const selected = libraryQuestions.value.find((item) => item.id === selectedLibraryQuestion.value)
  selectedLibraryVersion.value = selected?.bank_default_version_id || selectedQuestionDetail.value.current_version_id
}

async function addFromLibrary() {
  if (!selectedLibraryQuestion.value || !selectedLibraryVersion.value) {
    error.value = '请先选择题目和版本'
    return
  }
  busy.value = true
  try {
    const question = await apiRequest(`/surveys/${survey.value.id}/questions/from-library`, {
      method: 'POST',
      body: { question_id: selectedLibraryQuestion.value, question_version_id: selectedLibraryVersion.value, required: false },
    })
    survey.value.questions.push(question)
    if (librarySource.value === 'all') await loadLibrary()
    notice.value = `已从题目库加入“${question.title}”v${question.version_no}`
  } catch (reason) { showError(reason) } finally { busy.value = false }
}

function latestFor(question) {
  return libraryQuestions.value.find((item) => item.id === question.question_id)
}

async function upgradeQuestion(question) {
  const latest = latestFor(question)
  if (!latest || latest.current_version_id === question.question_version_id) return
  try {
    const updated = await apiRequest(`/surveys/${survey.value.id}/questions/${question.id}/version`, {
      method: 'PUT', body: { question_version_id: latest.current_version_id },
    })
    const index = survey.value.questions.findIndex((item) => item.id === question.id)
    survey.value.questions[index] = updated
    if (librarySource.value === 'all') await loadLibrary()
    notice.value = `已将“${updated.title}”升级到 v${updated.version_no}`
  } catch (reason) { showError(reason) }
}

async function saveBasics() {
  busy.value = true
  error.value = ''
  try {
    const body = survey.value.status === 'draft'
      ? {
          title: survey.value.title,
          description: survey.value.description,
          allow_anonymous: survey.value.allow_anonymous,
          allow_multiple_submissions: survey.value.allow_multiple_submissions,
          expires_at: fromLocalInput(expiresLocal.value),
        }
      : { expires_at: fromLocalInput(expiresLocal.value) }
    survey.value = await apiRequest(`/surveys/${survey.value.id}`, { method: 'PATCH', body })
    expiresLocal.value = toLocalInput(survey.value.expires_at)
    notice.value = '问卷设置已保存'
  } catch (reason) { showError(reason) } finally { busy.value = false }
}

function freshQuestion(type, title) {
  return {
    type,
    title,
    required: false,
    options: ['single_choice', 'multiple_choice'].includes(type)
      ? [{ label: '选项 1' }, { label: '选项 2' }]
      : [],
    validation: type === 'number' ? { integer_only: false } : {},
    rules: [],
  }
}

async function addQuestion() {
  if (!draftTitle.value.trim()) { error.value = '请先填写题目标题'; return }
  busy.value = true
  error.value = ''
  try {
    const question = await apiRequest(`/surveys/${survey.value.id}/questions`, {
      method: 'POST', body: freshQuestion(draftType.value, draftTitle.value.trim()),
    })
    survey.value.questions.push(question)
    if (librarySource.value === 'all') await loadLibrary()
    draftTitle.value = ''
    notice.value = '题目已添加，可继续设置选项、约束和跳转规则'
  } catch (reason) { showError(reason) } finally { busy.value = false }
}

async function saveQuestion(question) {
  savingQuestion.value = question.id
  error.value = ''
  try {
    const updated = await apiRequest(`/surveys/${survey.value.id}/questions/${question.id}`, { method: 'PATCH', body: question })
    const index = survey.value.questions.findIndex((item) => item.id === question.id)
    survey.value.questions[index] = updated
    if (librarySource.value === 'all') await loadLibrary()
    notice.value = `第 ${index + 1} 题已保存`
  } catch (reason) { showError(reason) } finally { savingQuestion.value = '' }
}

async function deleteQuestion(question) {
  if (!window.confirm(`确认删除“${question.title}”吗？`)) return
  error.value = ''
  try {
    await apiRequest(`/surveys/${survey.value.id}/questions/${question.id}`, { method: 'DELETE' })
    survey.value.questions = survey.value.questions.filter((item) => item.id !== question.id)
    notice.value = '题目已删除'
  } catch (reason) { showError(reason) }
}

async function move(index, direction) {
  const next = index + direction
  if (next < 0 || next >= survey.value.questions.length) return
  const reordered = [...survey.value.questions]
  ;[reordered[index], reordered[next]] = [reordered[next], reordered[index]]
  try {
    const result = await apiRequest(`/surveys/${survey.value.id}/question-order`, {
      method: 'PUT', body: { question_ids: reordered.map((item) => item.id) },
    })
    survey.value.questions = result.questions
    notice.value = '题序已更新'
  } catch (reason) { showError(reason) }
}

async function publish() {
  if (!window.confirm('发布后题目、选项和填写策略将被冻结。确认发布吗？')) return
  busy.value = true
  error.value = ''
  try {
    survey.value = await apiRequest(`/surveys/${survey.value.id}/publish`, { method: 'POST' })
    notice.value = '问卷已发布，可以复制分享链接'
  } catch (reason) { showError(reason) } finally { busy.value = false }
}

async function closeSurvey() {
  if (!window.confirm('关闭后不能重新开启，确认关闭吗？')) return
  try {
    survey.value = await apiRequest(`/surveys/${survey.value.id}/close`, { method: 'POST' })
    notice.value = '问卷已关闭'
  } catch (reason) { showError(reason) }
}

async function copyLink() {
  await navigator.clipboard.writeText(`${window.location.origin}${survey.value.share_path}`)
  notice.value = '分享链接已复制'
}

onMounted(load)
</script>

<template>
  <LoadingBlock v-if="loading" />
  <section v-else-if="survey">
    <header class="page-heading split-heading">
      <div><p class="kicker">问卷管理</p><div class="title-line"><h1>{{ survey.title }}</h1><span class="status-badge" :class="survey.status">{{ statusLabels[survey.status] }}</span></div><p>在这里设置题目、选项和跳转规则，发布后即可分享给填写者。</p></div>
      <div class="heading-actions"><button class="button secondary" type="button" @click="preview = !preview">{{ preview ? '关闭预览' : '预览结构' }}</button><button v-if="survey.status === 'published'" class="button" type="button" @click="copyLink">复制分享链接</button></div>
    </header>
    <StatusMessage type="success" :message="notice" />
    <StatusMessage type="error" :message="error" />

    <section class="settings-strip">
      <div class="settings-main">
        <label>标题<input v-model="survey.title" :disabled="readonly" maxlength="200" /></label>
        <label>说明<textarea v-model="survey.description" :disabled="readonly" rows="3" maxlength="5000"></textarea></label>
      </div>
      <div class="settings-side">
        <label>截止时间<input v-model="expiresLocal" type="datetime-local" :disabled="survey.status === 'closed'" /></label>
        <label class="check-row"><input v-model="survey.allow_anonymous" type="checkbox" :disabled="readonly" /><span><strong>对创建者匿名</strong></span></label>
        <label class="check-row"><input v-model="survey.allow_multiple_submissions" type="checkbox" :disabled="readonly" /><span><strong>允许重复提交</strong></span></label>
        <button v-if="survey.status !== 'closed'" class="button secondary" type="button" :disabled="busy" @click="saveBasics">保存设置</button>
        <small v-if="survey.published_at">发布于 {{ formatDate(survey.published_at) }}</small>
      </div>
    </section>

    <section v-if="preview" class="definition-preview">
      <h2>结构预览</h2>
      <ol><li v-for="question in survey.questions" :key="question.id"><strong>{{ question.title }}</strong><span>{{ questionTypeLabels[question.type] || '其他题型' }} · {{ question.required ? '必答' : '选答' }} · {{ question.rules.length }} 条跳转</span></li></ol>
    </section>

    <div class="section-heading"><div><h2>题目与跳转</h2><p>共 {{ survey.questions.length }} 道题，可根据回答跳转到后面的题目。</p></div></div>
    <div v-if="!survey.questions.length" class="empty-state compact-empty"><h3>尚未添加题目</h3><p>至少添加一道题后才能发布问卷。</p></div>
    <template v-for="(question, index) in survey.questions" :key="question.id">
      <div v-if="question.question_id" class="question-origin-bar">
        <span>题目库版本 v{{ question.version_no || '?' }}</span>
        <RouterLink :to="`/questions/${question.question_id}`">查看历史与使用情况</RouterLink>
        <button v-if="!readonly && latestFor(question) && latestFor(question).current_version_id !== question.question_version_id" class="button secondary compact" type="button" @click="upgradeQuestion(question)">升级到 v{{ latestFor(question).current_version.version_no }}</button>
      </div>
      <QuestionEditor
        :question="question"
        :index="index"
        :all-questions="survey.questions"
        :readonly="readonly"
        :saving="savingQuestion === question.id"
        @save="saveQuestion"
        @delete="deleteQuestion(question)"
        @move-up="move(index, -1)"
        @move-down="move(index, 1)"
      />
    </template>

    <section v-if="!readonly" class="library-picker">
      <div><h3>从题目库选择</h3><p>可选个人题目、共享题目或题库中的推荐版本。</p></div>
      <label>来源<select v-model="librarySource" @change="sourceChanged"><option value="all">全部可用题目</option><option v-for="bank in banks" :key="bank.id" :value="bank.id">题库：{{ bank.name }}</option></select></label>
      <label>题目<select v-model="selectedLibraryQuestion" @change="libraryQuestionChanged"><option value="" disabled>请选择题目</option><option v-for="question in libraryQuestions" :key="question.id" :value="question.id">{{ question.current_version.title }}{{ question.access === 'shared' ? `（${question.owner_username} 共享）` : '' }}</option></select></label>
      <label>版本<select v-model="selectedLibraryVersion" :disabled="!selectedQuestionDetail"><option v-for="version in selectedQuestionDetail?.versions || []" :key="version.id" :value="version.id">v{{ version.version_no }} · {{ version.title }}</option></select></label>
      <button class="button" type="button" :disabled="busy || !selectedLibraryVersion" @click="addFromLibrary">加入问卷</button>
    </section>

    <form v-if="!readonly" class="add-question-bar" @submit.prevent="addQuestion">
      <label>新题型<select v-model="draftType"><option value="single_choice">单选题</option><option value="multiple_choice">多选题</option><option value="text">文本填空</option><option value="number">数字填空</option></select></label>
      <label>题目标题<input v-model="draftTitle" maxlength="500" placeholder="输入题目后添加" /></label>
      <button class="button" :disabled="busy" type="submit">新建并保存题目</button>
    </form>

    <footer class="sticky-actions">
      <button class="button quiet" type="button" @click="router.push('/dashboard')">返回工作台</button>
      <RouterLink class="button secondary" :to="`/surveys/${survey.id}/statistics`">查看统计</RouterLink>
      <button v-if="survey.status === 'draft'" class="button" :disabled="busy" type="button" @click="publish">校验并发布</button>
      <button v-if="survey.status === 'published'" class="button danger-button" type="button" @click="closeSurvey">关闭问卷</button>
    </footer>
  </section>
  <StatusMessage v-else type="error" :message="error" />
</template>
