<script setup>
import { onMounted, ref } from 'vue'
import { apiRequest } from '../api/client.js'
import LoadingBlock from '../components/LoadingBlock.vue'
import StatusMessage from '../components/StatusMessage.vue'
import { questionTypeLabels } from '../utils.js'

const banks = ref([])
const questions = ref([])
const selected = ref(null)
const name = ref('')
const description = ref('')
const addQuestionId = ref('')
const error = ref('')
const notice = ref('')
const loading = ref(true)

async function load() {
  try {
    const [bankResult, questionResult] = await Promise.all([apiRequest('/question-banks'), apiRequest('/questions')])
    banks.value = bankResult.items
    questions.value = questionResult.items
    if (selected.value) await selectBank(selected.value.id)
  } catch (reason) { error.value = reason.message } finally { loading.value = false }
}

async function selectBank(id) {
  try { selected.value = await apiRequest(`/question-banks/${id}`) } catch (reason) { error.value = reason.message }
}

async function createBank() {
  if (!name.value.trim()) return
  try {
    const bank = await apiRequest('/question-banks', { method: 'POST', body: { name: name.value.trim(), description: description.value } })
    banks.value.unshift(bank)
    name.value = ''; description.value = ''
    await selectBank(bank.id)
    notice.value = '题库已创建'
  } catch (reason) { error.value = reason.message }
}

async function addItem() {
  if (!selected.value || !addQuestionId.value) return
  try {
    await apiRequest(`/question-banks/${selected.value.id}/items`, { method: 'POST', body: { question_id: addQuestionId.value } })
    await selectBank(selected.value.id)
    addQuestionId.value = ''
    notice.value = '题目已加入题库'
  } catch (reason) { error.value = reason.message }
}

async function updateToLatest(item) {
  try {
    await apiRequest(`/question-banks/${selected.value.id}/items/${item.question.id}`, { method: 'PATCH', body: { default_version_id: item.question.current_version_id } })
    await selectBank(selected.value.id)
    notice.value = '题库默认版本已更新'
  } catch (reason) { error.value = reason.message }
}

async function removeItem(item) {
  try {
    await apiRequest(`/question-banks/${selected.value.id}/items/${item.question.id}`, { method: 'DELETE' })
    await selectBank(selected.value.id)
  } catch (reason) { error.value = reason.message }
}

async function deleteBank() {
  if (!selected.value || !window.confirm(`删除题库“${selected.value.name}”吗？题目本身不会删除。`)) return
  try {
    await apiRequest(`/question-banks/${selected.value.id}`, { method: 'DELETE' })
    banks.value = banks.value.filter((item) => item.id !== selected.value.id)
    selected.value = null
    notice.value = '题库已删除'
  } catch (reason) { error.value = reason.message }
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-heading split-heading"><div><p class="kicker">分类整理</p><h1>我的题库</h1><p>题库保存题目及推荐版本，更新题库不会改动已有问卷。</p></div><RouterLink class="button secondary" to="/questions">返回题目库</RouterLink></header>
    <StatusMessage type="success" :message="notice" /><StatusMessage type="error" :message="error" />
    <LoadingBlock v-if="loading" />
    <div v-else class="bank-layout">
      <aside class="bank-sidebar">
        <form class="bank-create" @submit.prevent="createBank"><label>新题库名称<input v-model="name" maxlength="100" /></label><label>说明<textarea v-model="description" rows="2"></textarea></label><button class="button compact" type="submit">创建题库</button></form>
        <button v-for="bank in banks" :key="bank.id" type="button" :class="['bank-nav-item', { active: selected?.id === bank.id }]" @click="selectBank(bank.id)"><strong>{{ bank.name }}</strong><span>{{ bank.item_count }} 题</span></button>
      </aside>
      <main v-if="selected" class="bank-content">
        <div class="section-heading"><div><h2>{{ selected.name }}</h2><p>{{ selected.description || '暂无说明' }}</p></div><button class="text-button danger" type="button" @click="deleteBank">删除题库</button></div>
        <form class="bank-add" @submit.prevent="addItem"><label>加入题目<select v-model="addQuestionId"><option value="" disabled>选择个人或共享题目</option><option v-for="question in questions" :key="question.id" :value="question.id">{{ question.current_version.title }}</option></select></label><button class="button compact" type="submit">加入</button></form>
        <div v-if="!selected.items.length" class="empty-state compact-empty"><h3>题库还是空的</h3><p>从个人或共享题目中选择加入。</p></div>
        <article v-for="item in selected.items" :key="item.question.id" class="bank-item"><div><small>{{ questionTypeLabels[item.default_version.type] }} · 默认 v{{ item.default_version.version_no }}</small><h3>{{ item.default_version.title }}</h3></div><div class="row-actions"><button v-if="item.default_version.id !== item.question.current_version_id" class="button secondary compact" type="button" @click="updateToLatest(item)">更新到 v{{ item.question.current_version.version_no }}</button><button class="text-button danger" type="button" @click="removeItem(item)">移出</button></div></article>
      </main>
      <div v-else class="empty-state"><h2>选择或创建一个题库</h2><p>可用题库整理课程、团队或主题相关的常用题目。</p></div>
    </div>
  </section>
</template>
