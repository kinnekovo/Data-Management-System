<script setup>
import { onMounted, ref } from 'vue'
import { fetchReadiness } from './api/health.js'

const state = ref('checking')
const message = ref('正在检查后端与 MongoDB…')

async function checkHealth() {
  state.value = 'checking'
  message.value = '正在检查后端与 MongoDB…'
  try {
    await fetchReadiness()
    state.value = 'ready'
    message.value = '后端与 MongoDB 已就绪'
  } catch (error) {
    state.value = 'error'
    message.value = `服务尚未就绪：${error.message}`
  }
}

onMounted(checkHealth)
</script>

<template>
  <main class="shell">
    <section class="card" aria-labelledby="page-title">
      <p class="eyebrow">阶段一 · M1 基础环境</p>
      <h1 id="page-title">基于 MongoDB 的问卷系统</h1>
      <p class="intro">当前页面只验证前端、FastAPI 与 MongoDB 的基础连接。</p>

      <div class="status" :class="state" role="status" aria-live="polite">
        <span class="dot" aria-hidden="true"></span>
        <span>{{ message }}</span>
      </div>

      <button type="button" :disabled="state === 'checking'" @click="checkHealth">
        {{ state === 'checking' ? '检查中…' : '重新检查' }}
      </button>
    </section>
  </main>
</template>
