<template>
  <section v-if="loading" class="card loading-block">正在恢复面试现场…</section>

  <section v-else-if="error && !detail" class="card empty-state">
    <div class="empty-icon">!</div>
    <h3>面试加载失败</h3>
    <p>{{ error }}</p>
    <router-link class="button button-secondary" to="/dashboard">返回控制台</router-link>
  </section>

  <section v-else-if="detail" class="live-interview-page">
    <header class="session-header">
      <div>
        <router-link to="/dashboard">← 返回控制台</router-link>
        <p class="eyebrow">Live AI interview</p>
        <h1>{{ detail.interview.focus }}</h1>
        <p>{{ difficultyLabel[detail.interview.difficulty] }}难度 · AI 会根据你的每次回答实时调整下一题</p>
      </div>
      <div class="progress-box">
        <strong>{{ answeredCount }}</strong>
        <span>/ {{ detail.interview.question_count }}</span>
        <small>已完成轮次</small>
      </div>
    </header>

    <div class="progress-track"><i :style="{ width: `${progress}%` }"></i></div>

    <div class="interview-layout">
      <main class="card chat-panel">
        <div ref="chatWindow" class="chat-window" aria-live="polite">
          <article
            v-for="message in visibleMessages"
            :key="message.id"
            :class="['chat-message', message.role === 'user' ? 'candidate' : 'interviewer']"
          >
            <div class="avatar">{{ message.role === 'user' ? '你' : 'AI' }}</div>
            <div class="message-body">
              <span class="speaker">
                {{ message.role === 'user' ? '你' : '面试官' }}
                <em v-if="message.message_type === 'question'">问题</em>
                <em v-else-if="message.message_type === 'feedback'">反馈</em>
              </span>
              <p>{{ message.content }}</p>
            </div>
          </article>

          <article v-if="submitting" class="chat-message interviewer typing-message">
            <div class="avatar">AI</div>
            <div class="message-body">
              <span class="speaker">面试官正在思考</span>
              <p><i></i><i></i><i></i></p>
            </div>
          </article>
        </div>

        <form
          v-if="detail.interview.status === 'active' && currentQuestion"
          class="composer"
          @submit.prevent="handleSubmit"
        >
          <label for="answer">回答当前问题</label>
          <textarea
            id="answer"
            v-model.trim="answer"
            maxlength="5000"
            placeholder="直接像真实面试一样回答。可以讲背景、你的角色、做法、取舍与验证。"
            :disabled="submitting"
            required
          ></textarea>
          <div class="composer-footer">
            <small>{{ answer.length }} / 5000 · 提交后 AI 将基于你的回答继续追问</small>
            <button class="button button-primary" :disabled="submitting || !answer">
              <span v-if="submitting" class="spinner"></span>
              {{ submitting ? 'AI 正在生成下一步' : '发送回答 →' }}
            </button>
          </div>
          <p v-if="error" class="form-error">{{ error }}</p>
        </form>

        <div v-else-if="detail.interview.status === 'active'" class="complete-prompt">
          <div class="finish-mark">✓</div>
          <div>
            <p class="eyebrow">Interview finished</p>
            <h2>本场对话已完成</h2>
            <p>AI 已记录每轮表现，现在可以生成复盘报告。</p>
          </div>
          <button class="button button-primary" :disabled="completing" @click="handleComplete">
            <span v-if="completing" class="spinner"></span>
            {{ completing ? '正在生成报告' : '生成面试报告' }}
          </button>
        </div>

        <div v-else class="complete-prompt">
          <div class="finish-mark">✓</div>
          <div>
            <p class="eyebrow">Interview completed</p>
            <h2>本场面试已完成</h2>
          </div>
          <router-link class="button button-primary" :to="`/interviews/${detail.interview.id}/report`">
            查看面试报告
          </router-link>
        </div>
      </main>

      <aside class="session-aside">
        <div class="card session-card">
          <p class="eyebrow">Session status</p>
          <h3>实时面试中</h3>
          <div class="status-row"><span>目标岗位</span><strong>{{ detail.interview.focus }}</strong></div>
          <div class="status-row"><span>面试难度</span><strong>{{ difficultyLabel[detail.interview.difficulty] }}</strong></div>
          <div class="status-row"><span>下一步</span><strong>{{ currentQuestion ? '回答当前问题' : '生成报告' }}</strong></div>
          <button
            v-if="detail.interview.status === 'active' && answeredCount"
            class="end-button"
            :disabled="completing || submitting"
            @click="handleEndEarly"
          >
            结束本场面试
          </button>
        </div>

        <div class="card guide-card">
          <p class="eyebrow">How to answer</p>
          <h3>用具体经历说服面试官</h3>
          <ol>
            <li>先交代项目背景和你的职责</li>
            <li>说明实际做法与技术取舍</li>
            <li>补充结果、验证方式或复盘</li>
          </ol>
          <p>不需要背标准答案，AI 会顺着你的回答继续深挖。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getErrorMessage } from '../api/client'
import { completeInterview, getInterview, submitAnswer } from '../api/interview'

const route = useRoute()
const router = useRouter()
const detail = ref(null)
const chatWindow = ref(null)
const loading = ref(true)
const submitting = ref(false)
const completing = ref(false)
const error = ref('')
const answer = ref('')
const difficultyLabel = { easy: '基础', medium: '进阶', hard: '挑战' }

const visibleMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type !== 'score') || [],
)
const questionMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type === 'question') || [],
)
const answerMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type === 'answer') || [],
)
const answeredQuestionIds = computed(
  () => new Set(answerMessages.value.map((message) => message.metadata.question_message_id)),
)
const currentQuestion = computed(() =>
  questionMessages.value.find((message) => !answeredQuestionIds.value.has(message.id)),
)
const answeredCount = computed(() => answerMessages.value.length)
const progress = computed(() =>
  detail.value?.interview.question_count
    ? Math.round((answeredCount.value / detail.value.interview.question_count) * 100)
    : 0,
)

async function scrollToLatest() {
  await nextTick()
  if (chatWindow.value) chatWindow.value.scrollTop = chatWindow.value.scrollHeight
}

async function loadInterview() {
  error.value = ''
  try {
    detail.value = await getInterview(route.params.id)
    await scrollToLatest()
  } catch (requestError) {
    error.value = getErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!currentQuestion.value || !answer.value) return
  error.value = ''
  submitting.value = true
  try {
    await submitAnswer(route.params.id, {
      question_message_id: currentQuestion.value.id,
      answer: answer.value,
      top_k: 5,
    })
    answer.value = ''
    await loadInterview()
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '回答提交失败')
  } finally {
    submitting.value = false
    await scrollToLatest()
  }
}

async function handleComplete(force = false) {
  completing.value = true
  error.value = ''
  try {
    await completeInterview(route.params.id, { force })
    router.push(`/interviews/${route.params.id}/report`)
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '报告生成失败')
  } finally {
    completing.value = false
  }
}

async function handleEndEarly() {
  if (!window.confirm('现在结束面试吗？系统会根据已完成的回答生成报告。')) return
  await handleComplete(true)
}

onMounted(loadInterview)
</script>

<style scoped>
.session-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
}

.session-header a { display: inline-block; margin-bottom: 16px; color: var(--muted); font-size: 12px; font-weight: 700; }
.session-header h1 { margin: 5px 0 7px; font-size: clamp(28px, 4vw, 42px); letter-spacing: -0.04em; }
.session-header > div > p:last-child { margin: 0; color: var(--muted); font-size: 13px; }
.progress-box { display: grid; grid-template-columns: auto auto; align-items: baseline; column-gap: 6px; min-width: 104px; }
.progress-box strong { font-size: 36px; line-height: 1; }
.progress-box span { color: var(--muted); }
.progress-box small { grid-column: 1 / -1; margin-top: 5px; color: var(--muted); font-size: 10px; }
.progress-track { height: 5px; margin: 24px 0 30px; overflow: hidden; border-radius: 10px; background: #dfe5dd; }
.progress-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--green), #79a94e); transition: width 300ms ease; }
.interview-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 22px; align-items: start; }
.chat-panel { min-height: 650px; padding: 0; overflow: hidden; box-shadow: none; }
.chat-window { display: grid; max-height: 620px; gap: 18px; padding: clamp(22px, 4vw, 42px); overflow-y: auto; background: linear-gradient(180deg, #fbfcfa, #fff); }
.chat-message { display: flex; max-width: 88%; align-items: flex-start; gap: 10px; }
.chat-message.candidate { align-self: end; flex-direction: row-reverse; }
.avatar { display: grid; width: 31px; height: 31px; flex: 0 0 31px; place-items: center; border-radius: 10px; color: var(--green-dark); background: var(--green-soft); font-size: 10px; font-weight: 800; }
.candidate .avatar { color: #fff; background: var(--green); }
.message-body { min-width: 0; }
.speaker { display: block; margin: 0 0 5px 2px; color: var(--muted); font-size: 10px; font-weight: 700; }
.speaker em { margin-left: 7px; color: var(--green-dark); font-style: normal; }
.message-body p { margin: 0; padding: 13px 15px; border: 1px solid #e5ebe4; border-radius: 5px 16px 16px; background: #f6f8f4; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.candidate .message-body p { border-color: var(--green); border-radius: 16px 5px 16px 16px; color: #fff; background: var(--green); }
.typing-message .message-body p { display: flex; align-items: center; gap: 5px; min-width: 66px; }
.typing-message i { width: 6px; height: 6px; border-radius: 50%; background: #8b9b90; animation: pulse 1.1s infinite ease-in-out; }
.typing-message i:nth-child(2) { animation-delay: 140ms; }.typing-message i:nth-child(3) { animation-delay: 280ms; }
.composer { padding: 22px clamp(22px, 4vw, 42px) 26px; border-top: 1px solid var(--line); background: #fff; }
.composer label { display: block; margin-bottom: 9px; font-size: 12px; font-weight: 800; }
.composer textarea { width: 100%; min-height: 126px; resize: vertical; line-height: 1.65; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 15px; margin-top: 12px; }
.composer-footer small { color: var(--muted); font-size: 10px; }
.complete-prompt { display: flex; align-items: center; gap: 18px; padding: 29px clamp(22px, 4vw, 42px); border-top: 1px solid var(--line); background: #fbfcfa; }
.complete-prompt h2 { margin: 4px 0; font-size: 20px; }.complete-prompt p:not(.eyebrow) { margin: 0; color: var(--muted); font-size: 13px; }.complete-prompt .button { margin-left: auto; white-space: nowrap; }
.finish-mark { display: grid; width: 44px; height: 44px; flex: 0 0 44px; place-items: center; border-radius: 50%; color: var(--green-dark); background: var(--lime); font-size: 20px; font-weight: 700; }
.session-aside { position: sticky; top: 98px; display: grid; gap: 16px; }.session-card, .guide-card { padding: 22px; box-shadow: none; }.session-card h3, .guide-card h3 { margin: 4px 0 18px; font-size: 18px; }.status-row { display: grid; gap: 5px; padding: 11px 0; border-top: 1px solid var(--line); }.status-row span { color: var(--muted); font-size: 10px; }.status-row strong { font-size: 12px; line-height: 1.4; }.end-button { width: 100%; margin-top: 17px; padding: 10px; border: 1px solid #e6c9c3; border-radius: 10px; color: #9b413d; background: #fff8f6; font-size: 12px; font-weight: 700; }.end-button:disabled { opacity: .55; cursor: not-allowed; }.guide-card ol { margin: 0; padding-left: 20px; color: var(--muted); font-size: 12px; line-height: 1.8; }.guide-card > p:last-child { margin: 16px 0 0; color: var(--muted); font-size: 11px; line-height: 1.6; }
@keyframes pulse { 50% { opacity: .25; transform: translateY(-2px); } }
@media (max-width: 850px) { .interview-layout { grid-template-columns: 1fr; }.session-aside { position: static; grid-template-columns: 1fr 1fr; }.chat-panel { min-height: 0; } }
@media (max-width: 560px) { .session-header, .composer-footer, .complete-prompt { align-items: stretch; flex-direction: column; }.progress-box { align-self: flex-start; }.chat-window { max-height: none; min-height: 430px; }.chat-message { max-width: 96%; }.composer-footer .button, .complete-prompt .button { width: 100%; margin-left: 0; }.session-aside { grid-template-columns: 1fr; } }
</style>
