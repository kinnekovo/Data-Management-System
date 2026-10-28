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
const formError = ref('')

function freshDraft(type = 'single_choice') {
  const choice = ['single_choice', 'multiple_choice'].includes(type)
  return {
    type,
    title: '',
    options: choice ? [{ label: '选项 1' }, { label: '选项 2' }] : [],
    validation: type === 'number' ? { integer_only: false } : {},
  }
}

const draft = ref(freshDraft())

function typeChanged() {
  const title = draft.value.title
  draft.value = { ...freshDraft(draft.value.type), title }
  formError.value = ''
}

function addOption() {
  if (draft.value.options.length >= 100) return
  draft.value.options.push({ label: `选项 ${draft.value.options.length + 1}` })
}

function removeOption(index) {
  if (draft.value.options.length <= 2) return
  draft.value.options.splice(index, 1)
}

function cleanValidation() {
  return Object.fromEntries(
    Object.entries(draft.value.validation || {}).filter(([, value]) => (
      value !== '' && value !== null && value !== undefined
    )),
  )
}

function validateDraft() {
  if (!draft.value.title.trim()) return '请填写题目标题'
  if (['single_choice', 'multiple_choice'].includes(draft.value.type)) {
    if (draft.value.options.length < 2) return '选择题至少需要两个选项'
    if (draft.value.options.some((option) => !option.label.trim())) return '选项内容不能为空'
  }
  const validation = cleanValidation()
  if (draft.value.type === 'multiple_choice') {
    const minimum = validation.min_selections
    const maximum = validation.max_selections
    if (minimum !== undefined && (!Number.isInteger(minimum) || minimum < 0)) return '最少选择数必须是非负整数'
    if (maximum !== undefined && (!Number.isInteger(maximum) || maximum < 0)) return '最多选择数必须是非负整数'
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) return '最少选择数不能大于最多选择数'
    if (maximum !== undefined && maximum > draft.value.options.length) return '最多选择数不能超过选项数量'
  }
  if (draft.value.type === 'text') {
    const minimum = validation.min_length
    const maximum = validation.max_length
    if (minimum !== undefined && (!Number.isInteger(minimum) || minimum < 0)) return '最短字符数必须是非负整数'
    if (maximum !== undefined && (!Number.isInteger(maximum) || maximum < 0)) return '最长字符数必须是非负整数'
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) return '最短字符数不能大于最长字符数'
  }
  if (draft.value.type === 'number') {
    const minimum = validation.min_value
    const maximum = validation.max_value
    if (minimum !== undefined && maximum !== undefined && minimum > maximum) return '最小值不能大于最大值'
  }
  return ''
}

function contentForDraft() {
  return {
    type: draft.value.type,
    title: draft.value.title.trim(),
    options: draft.value.options.map((option) => ({ ...option, label: option.label.trim() })),
    validation: cleanValidation(),
    change_note: '在题目库中创建',
  }
}

function constraintSummary(version) {
  const validation = version.validation || {}
  if (version.type === 'single_choice') return `${version.options.length} 个选项`
  if (version.type === 'multiple_choice') {
    const minimum = validation.min_selections ?? '不限'
    const maximum = validation.max_selections ?? '不限'
    return `${version.options.length} 个选项 · 选择 ${minimum}–${maximum} 项`
  }
  if (version.type === 'text') {
    const minimum = validation.min_length ?? '不限'
    const maximum = validation.max_length ?? '不限'
    return `长度 ${minimum}–${maximum} 字符`
  }
  const minimum = validation.min_value ?? '不限'
  const maximum = validation.max_value ?? '不限'
  return `范围 ${minimum}–${maximum}${validation.integer_only ? ' · 仅整数' : ''}`
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
  formError.value = validateDraft()
  if (formError.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const created = await apiRequest('/questions', { method: 'POST', body: contentForDraft() })
    questions.value.unshift(created)
    draft.value = freshDraft()
    notice.value = '题目及约束已保存到个人题目库'
  } catch (reason) {
    formError.value = reason.message
  } finally { busy.value = false }
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
      <div class="library-create-heading"><div><h2>创建可复用题目</h2><p>题干、选项和约束将共同保存为 v1，加入问卷后仍可设置必答与跳转规则。</p></div><button class="button" type="submit" :disabled="busy">{{ busy ? '保存中…' : '保存题目' }}</button></div>
      <div class="library-create-main">
        <label>题型<select v-model="draft.type" :disabled="busy" @change="typeChanged"><option v-for="(label, value) in questionTypeLabels" :key="value" :value="value">{{ label }}</option></select></label>
        <label>题目标题<input v-model="draft.title" :disabled="busy" maxlength="500" placeholder="例如：你的年龄" required /></label>
      </div>

      <fieldset v-if="['single_choice', 'multiple_choice'].includes(draft.type)" class="library-constraints">
        <legend>选项设置</legend>
        <div class="library-options">
          <div v-for="(option, index) in draft.options" :key="index" class="library-option-row">
            <span class="option-key">{{ String.fromCharCode(65 + index) }}</span>
            <label :for="`library-option-${index}`" class="sr-only">选项 {{ index + 1 }}</label>
            <input :id="`library-option-${index}`" v-model="option.label" :disabled="busy" maxlength="200" required />
            <button class="text-button danger" type="button" :disabled="busy || draft.options.length <= 2" @click="removeOption(index)">删除</button>
          </div>
        </div>
        <button class="text-button" type="button" :disabled="busy || draft.options.length >= 100" @click="addOption">＋ 添加选项</button>
      </fieldset>

      <fieldset v-if="draft.type === 'multiple_choice'" class="library-constraints inline-fields">
        <legend>选择数量约束</legend>
        <label>最少选择数<input v-model.number="draft.validation.min_selections" :disabled="busy" type="number" min="0" :max="draft.options.length" placeholder="不限制" /></label>
        <label>最多选择数<input v-model.number="draft.validation.max_selections" :disabled="busy" type="number" min="0" :max="draft.options.length" placeholder="不限制" /></label>
      </fieldset>

      <fieldset v-if="draft.type === 'text'" class="library-constraints inline-fields">
        <legend>文本长度约束</legend>
        <label>最短字符数<input v-model.number="draft.validation.min_length" :disabled="busy" type="number" min="0" placeholder="不限制" /></label>
        <label>最长字符数<input v-model.number="draft.validation.max_length" :disabled="busy" type="number" min="0" placeholder="不限制" /></label>
      </fieldset>

      <fieldset v-if="draft.type === 'number'" class="library-constraints inline-fields">
        <legend>数值约束</legend>
        <label>最小值<input v-model.number="draft.validation.min_value" :disabled="busy" type="number" placeholder="不限制" /></label>
        <label>最大值<input v-model.number="draft.validation.max_value" :disabled="busy" type="number" placeholder="不限制" /></label>
        <label class="check-row compact-check"><input v-model="draft.validation.integer_only" :disabled="busy" type="checkbox" /><span><strong>只允许整数</strong><small>开启后拒绝小数答案</small></span></label>
      </fieldset>

      <p v-if="formError" class="form-inline-error" role="alert">{{ formError }}</p>
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
        <p>{{ constraintSummary(question.current_version) }} · 更新于 {{ formatDate(question.updated_at) }}</p>
        <footer><RouterLink class="button secondary compact" :to="`/questions/${question.id}`">版本、共享与统计</RouterLink><button v-if="question.access === 'owner'" class="text-button danger" type="button" @click="archiveQuestion(question)">归档</button></footer>
      </article>
    </div>
  </section>
</template>
