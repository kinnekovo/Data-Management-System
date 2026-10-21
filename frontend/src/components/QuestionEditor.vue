<script setup>
import { computed } from 'vue'
import { questionTypeLabels } from '../utils.js'

const props = defineProps({
  question: { type: Object, required: true },
  index: { type: Number, required: true },
  allQuestions: { type: Array, required: true },
  readonly: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'delete', 'move-up', 'move-down'])

const typeLabels = questionTypeLabels
const operators = computed(() => ({
  single_choice: [{ value: 'eq', label: '等于' }],
  multiple_choice: [{ value: 'contains_any', label: '包含任一' }, { value: 'contains_all', label: '包含全部' }],
  number: [
    { value: 'eq', label: '等于' }, { value: 'gt', label: '大于' },
    { value: 'gte', label: '大于等于' }, { value: 'lt', label: '小于' }, { value: 'lte', label: '小于等于' },
  ],
  text: [],
}[props.question.type] || []))
const laterQuestions = computed(() => props.allQuestions.slice(props.index + 1))

function newOptionId() {
  const randomPart = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID().replaceAll('-', '').slice(0, 12)
    : Math.random().toString(36).slice(2, 14)
  return `opt_${randomPart}`
}

function newOption(label) {
  return { id: newOptionId(), label }
}

function ensureOptionIds() {
  for (const option of props.question.options) {
    if (!option.id) option.id = newOptionId()
  }
}

function typeChanged() {
  const choice = ['single_choice', 'multiple_choice'].includes(props.question.type)
  props.question.options = choice ? [newOption('选项 1'), newOption('选项 2')] : []
  props.question.validation = props.question.type === 'number' ? { integer_only: false } : {}
  props.question.rules = []
}

function addOption() {
  props.question.options.push(newOption(`选项 ${props.question.options.length + 1}`))
}

function removeOption(index) {
  const removed = props.question.options[index]
  props.question.options.splice(index, 1)
  for (const rule of props.question.rules) {
    if (Array.isArray(rule.value)) rule.value = rule.value.filter((item) => item !== removed.id)
    else if (rule.value === removed.id) rule.value = ''
  }
}

function addRule() {
  const operator = operators.value[0]?.value
  if (!operator || !laterQuestions.value.length) return
  if (props.question.type === 'multiple_choice') ensureOptionIds()
  props.question.rules.push({
    priority: props.question.rules.length + 1,
    operator,
    value: props.question.type === 'multiple_choice' ? [] : props.question.type === 'number' ? 0 : '',
    target_question_id: laterQuestions.value[0].id,
  })
}

function operatorChanged(rule) {
  rule.value = props.question.type === 'multiple_choice' ? [] : props.question.type === 'number' ? 0 : ''
}

function toggleRuleOption(rule, option, checked) {
  if (!option.id) option.id = newOptionId()
  const optionId = option.id
  const selected = Array.isArray(rule.value) ? [...rule.value] : []
  const optionIndex = selected.indexOf(optionId)
  if (checked && optionIndex === -1) selected.push(optionId)
  if (!checked && optionIndex !== -1) selected.splice(optionIndex, 1)
  rule.value = selected
}

function cleanValidation() {
  return Object.fromEntries(Object.entries(props.question.validation || {}).filter(([, value]) => value !== '' && value !== null && value !== undefined))
}

function save() {
  if (['single_choice', 'multiple_choice'].includes(props.question.type)) ensureOptionIds()
  emit('save', { ...props.question, validation: cleanValidation() })
}
</script>

<template>
  <article class="question-editor" :class="{ frozen: readonly }">
    <header class="question-header">
      <span class="question-number">{{ index + 1 }}</span>
      <div><strong>{{ question.title || '未命名题目' }}</strong><small>{{ typeLabels[question.type] }}</small></div>
      <div v-if="!readonly" class="icon-actions">
        <button type="button" class="icon-button" :disabled="index === 0" aria-label="上移题目" @click="emit('move-up')">↑</button>
        <button type="button" class="icon-button" :disabled="index === allQuestions.length - 1" aria-label="下移题目" @click="emit('move-down')">↓</button>
      </div>
    </header>

    <div class="editor-grid">
      <label>题目标题<input v-model="question.title" :disabled="readonly" maxlength="500" /></label>
      <label>题型<select v-model="question.type" :disabled="readonly" @change="typeChanged"><option v-for="(label, value) in typeLabels" :key="value" :value="value">{{ label }}</option></select></label>
    </div>
    <label class="check-row compact-check"><input v-model="question.required" type="checkbox" :disabled="readonly" /><span><strong>必答题</strong></span></label>

    <fieldset v-if="['single_choice', 'multiple_choice'].includes(question.type)" class="subsection">
      <legend>选项</legend>
      <div v-for="(option, optionIndex) in question.options" :key="option.id || optionIndex" class="inline-row">
        <span class="option-key">{{ String.fromCharCode(65 + optionIndex) }}</span>
        <input v-model="option.label" :disabled="readonly" maxlength="200" />
        <button v-if="!readonly" type="button" class="text-button danger" :disabled="question.options.length <= 2" @click="removeOption(optionIndex)">删除</button>
      </div>
      <button v-if="!readonly" type="button" class="text-button" @click="addOption">＋ 添加选项</button>
    </fieldset>

    <fieldset v-if="question.type === 'multiple_choice'" class="subsection inline-fields">
      <legend>选择数量</legend>
      <label>最少<input v-model.number="question.validation.min_selections" :disabled="readonly" type="number" min="0" /></label>
      <label>最多<input v-model.number="question.validation.max_selections" :disabled="readonly" type="number" min="0" /></label>
    </fieldset>
    <fieldset v-if="question.type === 'text'" class="subsection inline-fields">
      <legend>文本长度</legend>
      <label>最少字符<input v-model.number="question.validation.min_length" :disabled="readonly" type="number" min="0" /></label>
      <label>最多字符<input v-model.number="question.validation.max_length" :disabled="readonly" type="number" min="0" /></label>
    </fieldset>
    <fieldset v-if="question.type === 'number'" class="subsection inline-fields">
      <legend>数值范围</legend>
      <label>最小值<input v-model.number="question.validation.min_value" :disabled="readonly" type="number" /></label>
      <label>最大值<input v-model.number="question.validation.max_value" :disabled="readonly" type="number" /></label>
      <label class="check-row compact-check"><input v-model="question.validation.integer_only" type="checkbox" :disabled="readonly" /><span><strong>只允许整数</strong></span></label>
    </fieldset>

    <fieldset v-if="question.type !== 'text'" class="subsection rules-section">
      <legend>条件跳转</legend>
      <p v-if="!laterQuestions.length" class="muted">这是最后一题，没有可跳转的后续题目。</p>
      <div v-for="(rule, ruleIndex) in question.rules" :key="ruleIndex" class="rule-row">
        <label>优先级<input v-model.number="rule.priority" :disabled="readonly" type="number" min="0" /></label>
        <label>条件<select v-model="rule.operator" :disabled="readonly" @change="operatorChanged(rule)"><option v-for="item in operators" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <label v-if="question.type === 'single_choice'">匹配值<select v-model="rule.value" :disabled="readonly"><option value="" disabled>请选择</option><option v-for="option in question.options" :key="option.id" :value="option.id">{{ option.label }}</option></select></label>
        <div v-else-if="question.type === 'multiple_choice'" class="rule-options"><span>匹配值</span><label v-for="(option, optionIndex) in question.options" :key="option.id || optionIndex" class="mini-check"><input :checked="Array.isArray(rule.value) && rule.value.includes(option.id)" type="checkbox" :value="option.id" :disabled="readonly" :aria-label="`匹配 ${option.label}`" @change="toggleRuleOption(rule, option, $event.target.checked)" />{{ option.label }}</label></div>
        <label v-else>匹配值<input v-model.number="rule.value" :disabled="readonly" type="number" /></label>
        <label>跳到<select v-model="rule.target_question_id" :disabled="readonly"><option v-for="target in laterQuestions" :key="target.id" :value="target.id">{{ allQuestions.indexOf(target) + 1 }}. {{ target.title }}</option></select></label>
        <button v-if="!readonly" type="button" class="text-button danger" @click="question.rules.splice(ruleIndex, 1)">删除规则</button>
      </div>
      <button v-if="!readonly && laterQuestions.length" type="button" class="text-button" @click="addRule">＋ 添加跳转规则</button>
    </fieldset>

    <footer v-if="!readonly" class="question-footer">
      <button type="button" class="text-button danger" @click="emit('delete')">删除题目</button>
      <button type="button" class="button compact" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存本题' }}</button>
    </footer>
  </article>
</template>
