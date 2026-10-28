<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { formatDate, questionTypeLabels, statusLabels } from '../utils.js'

const route = useRoute()
const question = ref(null)
const usages = ref({ items: [], total: 0 })
const shares = ref({ items: [] })
const stats = ref(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const editing = ref(false)
const draft = ref(null)
const shareUsername = ref('')
const isOwner = computed(() => question.value?.access === 'owner')

function startVersion(source = question.value.current_version) {
  draft.value = {
    type: source.type,
    title: source.title,
    options: source.options.map((item) => ({ ...item })),
    validation: { ...source.validation },
    parent_version_id: source.id,
    change_note: '',
  }
  editing.value = true
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    question.value = await apiRequest(`/questions/${route.params.id}`)
    const requests = [apiRequest(`/questions/${route.params.id}/usages`), apiRequest(`/questions/${route.params.id}/statistics`)]
    ;[usages.value, stats.value] = await Promise.all(requests)
    if (question.value.access === 'owner') shares.value = await apiRequest(`/questions/${route.params.id}/shares`)
  } catch (reason) { error.value = reason.message } finally { loading.value = false }
}

function cleanValidation() {
  return Object.fromEntries(Object.entries(draft.value.validation || {}).filter(([, value]) => value !== '' && value !== null && value !== undefined))
}

async function saveVersion() {
  try {
    await apiRequest(`/questions/${question.value.id}/versions`, { method: 'POST', body: { ...draft.value, validation: cleanValidation() } })
    editing.value = false
    notice.value = '新版本已创建；已有问卷仍使用原版本'
    await load()
  } catch (reason) { error.value = reason.message }
}

async function restore(version) {
  if (!window.confirm(`基于 v${version.version_no} 创建一个新的恢复版本吗？`)) return
  try {
    await apiRequest(`/questions/${question.value.id}/versions/${version.id}/restore`, { method: 'POST' })
    notice.value = `已基于 v${version.version_no} 创建最新版本`
    await load()
  } catch (reason) { error.value = reason.message }
}

async function share() {
  if (!shareUsername.value.trim()) return
  try {
    const item = await apiRequest(`/questions/${question.value.id}/shares`, { method: 'POST', body: { username: shareUsername.value.trim() } })
    shares.value.items.push(item)
    shareUsername.value = ''
    notice.value = '题目已共享，对方可以在自己的问卷中使用'
  } catch (reason) { error.value = reason.message }
}

async function revoke(item) {
  try {
    await apiRequest(`/questions/${question.value.id}/shares/${item.user_id}`, { method: 'DELETE' })
    shares.value.items = shares.value.items.filter((shareItem) => shareItem.user_id !== item.user_id)
  } catch (reason) { error.value = reason.message }
}

function addOption() { draft.value.options.push({ label: `选项 ${draft.value.options.length + 1}` }) }

onMounted(load)
</script>

<template>
  <LoadingBlock v-if="loading" />
  <section v-else-if="question">
    <header class="page-heading split-heading"><div><p class="kicker">题目详情</p><h1>{{ question.current_version.title }}</h1><p>{{ questionTypeLabels[question.current_version.type] }} · 当前 v{{ question.current_version.version_no }} · {{ question.access === 'owner' ? '我的题目' : `由 ${question.owner_username} 共享` }}</p></div><div class="heading-actions"><RouterLink class="button quiet" to="/questions">返回题目库</RouterLink><button v-if="isOwner" class="button" type="button" @click="startVersion()">创建新版本</button></div></header>
    <StatusMessage type="success" :message="notice" /><StatusMessage type="error" :message="error" />

    <form v-if="editing" class="version-editor" @submit.prevent="saveVersion">
      <div class="section-heading"><div><h2>基于 v{{ question.current_version.version_no }} 创建版本</h2><p>保存后生成不可变的新版本，不会替换已有问卷。</p></div><button class="text-button" type="button" @click="editing = false">取消</button></div>
      <div class="editor-grid"><label>标题<input v-model="draft.title" maxlength="500" /></label><label>题型<input :value="questionTypeLabels[draft.type]" disabled /></label></div>
      <fieldset v-if="['single_choice', 'multiple_choice'].includes(draft.type)" class="subsection"><legend>选项</legend><div v-for="(option, index) in draft.options" :key="option.id || index" class="inline-row"><span class="option-key">{{ String.fromCharCode(65 + index) }}</span><input v-model="option.label" maxlength="200" /><button class="text-button danger" type="button" :disabled="draft.options.length <= 2" @click="draft.options.splice(index, 1)">删除</button></div><button class="text-button" type="button" @click="addOption">＋ 添加选项</button></fieldset>
      <fieldset v-if="draft.type === 'multiple_choice'" class="subsection inline-fields"><legend>选择数量</legend><label>最少<input v-model.number="draft.validation.min_selections" type="number" min="0" /></label><label>最多<input v-model.number="draft.validation.max_selections" type="number" min="0" /></label></fieldset>
      <fieldset v-if="draft.type === 'text'" class="subsection inline-fields"><legend>文本长度</legend><label>最少字符<input v-model.number="draft.validation.min_length" type="number" min="0" /></label><label>最多字符<input v-model.number="draft.validation.max_length" type="number" min="0" /></label></fieldset>
      <fieldset v-if="draft.type === 'number'" class="subsection inline-fields"><legend>数值范围</legend><label>最小值<input v-model.number="draft.validation.min_value" type="number" /></label><label>最大值<input v-model.number="draft.validation.max_value" type="number" /></label><label class="check-row compact-check"><input v-model="draft.validation.integer_only" type="checkbox" /><span><strong>只允许整数</strong></span></label></fieldset>
      <label>修改说明<textarea v-model="draft.change_note" rows="2" maxlength="500" placeholder="说明本次修改内容"></textarea></label>
      <div class="form-actions"><button class="button" type="submit">保存为新版本</button></div>
    </form>

    <div class="detail-columns">
      <section>
        <div class="section-heading"><div><h2>版本历史</h2><p>恢复旧版本也会创建新版本，历史记录不会被覆盖。</p></div></div>
        <ol class="version-timeline"><li v-for="version in question.versions" :key="version.id"><div><strong>v{{ version.version_no }} · {{ version.title }}</strong><p>{{ version.change_note || '无修改说明' }}</p><small>{{ formatDate(version.created_at) }}<span v-if="version.parent_version_id"> · 来源版本 {{ question.versions.find((item) => item.id === version.parent_version_id)?.version_no || '外部' }}</span></small></div><div class="row-actions"><button v-if="isOwner && version.id !== question.current_version_id" class="text-button" type="button" @click="startVersion(version)">基于此版本修改</button><button v-if="isOwner && version.id !== question.current_version_id" class="button secondary compact" type="button" @click="restore(version)">恢复</button></div></li></ol>
      </section>
      <aside v-if="isOwner" class="share-panel"><h2>共享使用权</h2><p>对方可以使用各版本，但不能修改你的原题。</p><form @submit.prevent="share"><label>用户名<input v-model="shareUsername" maxlength="32" placeholder="输入对方用户名" /></label><button class="button compact" type="submit">共享</button></form><div class="share-list"><div v-for="item in shares.items" :key="item.user_id"><span><strong>{{ item.username }}</strong><small>可使用</small></span><button class="text-button danger" type="button" @click="revoke(item)">撤销</button></div><p v-if="!shares.items.length" class="muted">尚未共享给其他用户。</p></div></aside>
    </div>

    <section><div class="section-heading"><div><h2>被哪些问卷使用</h2><p>共 {{ usages.total }} 处使用；共享用户只会看到自己的问卷。</p></div></div><div v-if="usages.items.length" class="usage-list"><article v-for="item in usages.items" :key="`${item.survey_id}-${item.survey_question_id}`"><div><h3>{{ item.survey_title }}</h3><small>题目 v{{ question.versions.find((version) => version.id === item.question_version_id)?.version_no || '?' }} · {{ formatDate(item.updated_at) }}</small></div><span class="status-badge" :class="item.survey_status">{{ statusLabels[item.survey_status] }}</span></article></div><p v-else class="muted">还没有问卷使用这道题。</p></section>

    <section><div class="section-heading"><div><h2>跨问卷匿名统计</h2><p>{{ stats.survey_count }} 份问卷 · {{ stats.answered_count }} 个回答，按版本分别统计。</p></div></div><div v-if="!stats.version_stats.length" class="empty-state compact-empty"><h3>暂无回答</h3><p>问卷收到回答后，这里会展示跨问卷汇总。</p></div><article v-for="item in stats.version_stats" :key="item.version_id" class="stat-section"><header><span>{{ item.version_no }}</span><div><h2>v{{ item.version_no }} · {{ item.title }}</h2><p>{{ item.answered_count }} 个回答</p></div></header><div v-if="item.options" class="bar-list"><div v-for="option in item.options" :key="option.id" class="bar-row"><div><span>{{ option.label }}</span><strong>{{ option.count }}</strong></div><div class="bar-track"><span :style="{ width: `${item.answered_count ? option.count / item.answered_count * 100 : 0}%` }"></span></div></div></div><dl v-else-if="item.type === 'number'" class="number-stats"><div><dt>平均值</dt><dd>{{ item.average ?? '—' }}</dd></div><div><dt>最小值</dt><dd>{{ item.minimum ?? '—' }}</dd></div><div><dt>最大值</dt><dd>{{ item.maximum ?? '—' }}</dd></div></dl><p v-else class="muted">文本题仅展示匿名回答数量，不跨问卷暴露原文。</p></article></section>
  </section>
  <StatusMessage v-else type="error" :message="error" />
</template>
