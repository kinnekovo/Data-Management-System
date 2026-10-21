<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { formatDate } from '../utils.js'

const route = useRoute()
const survey = ref(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const fieldError = ref('')
const submitted = ref(null)
const answers = reactive({})
const history = ref([0])
const reviewing = ref(false)

const currentIndex = computed(() => history.value[history.value.length - 1] ?? 0)
const current = computed(() => survey.value?.questions[currentIndex.value])
const progress = computed(() => survey.value ? Math.round(((currentIndex.value + 1) / survey.value.questions.length) * 100) : 0)

function optionIds(question) { return new Set(question.options.map((option) => option.id)) }

function validate(question, value) {
  const empty = value === undefined || value === null || (question.type === 'text' && !String(value).trim()) || (question.type === 'multiple_choice' && Array.isArray(value) && !value.length)
  if (empty) return question.required ? '该题为必答题' : ''
  if (question.type === 'single_choice' && !optionIds(question).has(value)) return '请选择一个合法选项'
  if (question.type === 'multiple_choice') {
    if (!Array.isArray(value)) return '请选择选项'
    const min = question.validation.min_selections
    const max = question.validation.max_selections
    if (min !== undefined && value.length < min) return `至少选择 ${min} 项`
    if (max !== undefined && value.length > max) return `最多选择 ${max} 项`
  }
  if (question.type === 'text') {
    const min = question.validation.min_length
    const max = question.validation.max_length
    if (min !== undefined && value.length < min) return `至少输入 ${min} 个字符`
    if (max !== undefined && value.length > max) return `最多输入 ${max} 个字符`
  }
  if (question.type === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '请输入有效数字'
    if (question.validation.integer_only && !Number.isInteger(value)) return '请输入整数'
    if (question.validation.min_value !== undefined && value < question.validation.min_value) return `数值不能小于 ${question.validation.min_value}`
    if (question.validation.max_value !== undefined && value > question.validation.max_value) return `数值不能大于 ${question.validation.max_value}`
  }
  return ''
}

function matches(question, answer, rule) {
  if (question.type === 'single_choice') return answer === rule.value
  if (question.type === 'multiple_choice') {
    if (rule.operator === 'contains_any') return rule.value.some((item) => answer.includes(item))
    return rule.value.every((item) => answer.includes(item))
  }
  if (question.type === 'number') {
    return { eq: answer === rule.value, gt: answer > rule.value, gte: answer >= rule.value, lt: answer < rule.value, lte: answer <= rule.value }[rule.operator]
  }
  return false
}

function nextIndex(index) {
  const question = survey.value.questions[index]
  const answer = answers[question.id]
  const present = answer !== undefined && answer !== null && answer !== '' && !(Array.isArray(answer) && !answer.length)
  if (present) {
    const rule = [...question.rules].sort((a, b) => a.priority - b.priority).find((item) => matches(question, answer, item))
    if (rule) return survey.value.questions.findIndex((item) => item.id === rule.target_question_id)
  }
  return index + 1
}

function clearAnswersOutside(indices) {
  const keep = new Set(indices.map((index) => survey.value.questions[index].id))
  for (const questionId of Object.keys(answers)) if (!keep.has(questionId)) delete answers[questionId]
}

function toggleMultiple(questionId, optionId, checked) {
  const selected = Array.isArray(answers[questionId]) ? [...answers[questionId]] : []
  const optionIndex = selected.indexOf(optionId)
  if (checked && optionIndex === -1) selected.push(optionId)
  if (!checked && optionIndex !== -1) selected.splice(optionIndex, 1)
  answers[questionId] = selected
}

function goNext() {
  fieldError.value = validate(current.value, answers[current.value.id])
  if (fieldError.value) return
  clearAnswersOutside(history.value)
  const next = nextIndex(currentIndex.value)
  if (next >= survey.value.questions.length) reviewing.value = true
  else history.value.push(next)
}

function goBack() {
  fieldError.value = ''
  if (reviewing.value) { reviewing.value = false; return }
  if (history.value.length > 1) history.value.pop()
  clearAnswersOutside(history.value)
}

function buildSubmission() {
  const visited = []
  let index = 0
  while (index < survey.value.questions.length) {
    const question = survey.value.questions[index]
    const message = validate(question, answers[question.id])
    if (message) throw new Error(`第 ${index + 1} 题：${message}`)
    visited.push(index)
    index = nextIndex(index)
  }
  clearAnswersOutside(visited)
  return visited
    .filter((item) => answers[survey.value.questions[item].id] !== undefined && answers[survey.value.questions[item].id] !== '')
    .map((item) => ({ question_id: survey.value.questions[item].id, value: answers[survey.value.questions[item].id] }))
}

function displayAnswer(question) {
  const value = answers[question.id]
  if (question.type === 'single_choice') return question.options.find((option) => option.id === value)?.label || '未作答'
  if (question.type === 'multiple_choice') {
    return (value || []).map((optionId) => question.options.find((option) => option.id === optionId)?.label).filter(Boolean).join('、') || '未作答'
  }
  return value ?? '未作答'
}

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const payload = { answers: buildSubmission() }
    submitted.value = await apiRequest(`/public/surveys/${route.params.slug}/responses`, { method: 'POST', body: payload })
  } catch (reason) {
    error.value = reason.message
  } finally { busy.value = false }
}

async function load() {
  try {
    survey.value = await apiRequest(`/public/surveys/${route.params.slug}`)
    for (const question of survey.value.questions) if (question.type === 'multiple_choice') answers[question.id] = []
  } catch (reason) { error.value = reason.message } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <LoadingBlock v-if="loading" />
  <section v-else-if="submitted" class="completion-panel">
    <span class="completion-mark">✓</span><p class="kicker">提交成功</p><h1>感谢完成问卷</h1>
    <p>答卷已提交。提交时间：{{ formatDate(submitted.submitted_at) }}</p>
    <RouterLink class="button" to="/dashboard">返回工作台</RouterLink>
  </section>
  <section v-else-if="survey" class="fill-layout">
    <header class="fill-heading"><p class="kicker">在线问卷</p><h1>{{ survey.title }}</h1><p>{{ survey.description }}</p><small>截止时间：{{ formatDate(survey.expires_at) }} · {{ survey.allow_anonymous ? '创建者不可见填写身份' : '创建者可见填写身份' }}</small></header>
    <div class="progress-track" aria-label="答题进度"><span :style="{ transform: `scaleX(${(reviewing ? 100 : progress) / 100})` }"></span></div>

    <article v-if="!reviewing" class="question-stage">
      <p class="question-position">第 {{ currentIndex + 1 }} 题 / 共 {{ survey.questions.length }} 题</p>
      <h2>{{ current.title }} <span v-if="current.required" class="required-mark">必答</span></h2>
      <div v-if="current.type === 'single_choice'" class="answer-options">
        <label v-for="option in current.options" :key="option.id"><input v-model="answers[current.id]" type="radio" :value="option.id" /><span>{{ option.label }}</span></label>
      </div>
      <div v-else-if="current.type === 'multiple_choice'" class="answer-options">
          <label v-for="option in current.options" :key="option.id"><input :checked="(answers[current.id] || []).includes(option.id)" type="checkbox" :value="option.id" @change="toggleMultiple(current.id, option.id, $event.target.checked)" /><span>{{ option.label }}</span></label>
        <small>选择范围：{{ current.validation.min_selections ?? 0 }}–{{ current.validation.max_selections ?? current.options.length }} 项</small>
      </div>
      <label v-else-if="current.type === 'text'" class="answer-field"><textarea v-model="answers[current.id]" rows="6" :maxlength="current.validation.max_length" placeholder="请输入回答"></textarea><small v-if="current.validation.max_length">最多 {{ current.validation.max_length }} 个字符</small></label>
      <label v-else class="answer-field"><input v-model.number="answers[current.id]" type="number" :min="current.validation.min_value" :max="current.validation.max_value" :step="current.validation.integer_only ? 1 : 'any'" placeholder="请输入数字" /></label>
      <StatusMessage type="error" :message="fieldError" />
      <div class="stage-actions"><button class="button quiet" type="button" :disabled="history.length === 1" @click="goBack">上一步</button><button class="button" type="button" @click="goNext">{{ nextIndex(currentIndex) >= survey.questions.length ? '检查答案' : '下一题' }}</button></div>
    </article>

    <article v-else class="review-stage">
      <p class="kicker">提交前检查</p><h2>请检查这 {{ history.length }} 道题的回答</h2><p>确认无误后即可提交，提交后无法修改。</p>
        <ol class="review-list"><li v-for="index in history" :key="survey.questions[index].id"><span>{{ survey.questions[index].title }}</span><strong>{{ displayAnswer(survey.questions[index]) }}</strong></li></ol>
      <StatusMessage type="error" :message="error" />
      <div class="stage-actions"><button class="button quiet" type="button" @click="goBack">返回修改</button><button class="button" :disabled="busy" type="button" @click="submit">{{ busy ? '正在提交…' : '确认提交' }}</button></div>
    </article>
  </section>
  <section v-else class="empty-state"><h1>无法打开问卷</h1><StatusMessage type="error" :message="error" /><RouterLink class="button" to="/dashboard">返回工作台</RouterLink></section>
</template>
