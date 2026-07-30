<template>
  <section v-if="loading" class="card loading-block">正在恢复面试现场…</section>

  <section v-else-if="error && !detail" class="card empty-state">
    <div class="empty-icon">!</div>
    <h3>面试加载失败</h3>
    <p>{{ error }}</p>
    <router-link class="button button-secondary" to="/dashboard">返回控制台</router-link>
  </section>

  <section v-else-if="detail" class="interview-page">
    <header class="session-header">
      <div>
        <router-link to="/dashboard">← 返回控制台</router-link>
        <h1>{{ detail.interview.focus }}</h1>
        <p>
          {{ difficultyLabel[detail.interview.difficulty] }}难度 ·
          {{ detail.interview.question_count }} 道问题
        </p>
      </div>
      <div class="progress-box">
        <div>
          <strong>{{ answeredIds.size }}</strong>
          <span>/ {{ questionMessages.length }}</span>
        </div>
        <small>当前进度</small>
      </div>
    </header>

    <div class="progress-track">
      <i :style="{ width: `${progress}%` }"></i>
    </div>

    <div class="interview-layout">
      <main class="question-stage">
        <article v-if="currentQuestion" class="card question-card">
          <div class="question-label">
            <span>QUESTION {{ currentIndex + 1 }}</span>
            <em>{{ currentQuestion.metadata.difficulty || detail.interview.difficulty }}</em>
          </div>
          <h2>{{ currentQuestion.content }}</h2>
          <p class="coach-note">
            建议按“背景—方案—实现—验证—反思”组织回答，尽量给出具体细节。
          </p>

          <form class="answer-form" @submit.prevent="handleSubmit">
            <div class="field">
              <label for="answer">你的回答</label>
              <textarea
                id="answer"
                v-model.trim="answer"
                maxlength="5000"
                placeholder="像真实面试一样作答。可以先交代背景，再说明你具体做了什么……"
                required
              ></textarea>
              <small>{{ answer.length }} / 5000</small>
            </div>
            <p v-if="error" class="form-error">{{ error }}</p>
            <div class="answer-actions">
              <span>回答提交后会立即生成评分和追问</span>
              <button
                class="button button-primary"
                :disabled="submitting || answer.length < 1"
              >
                <span v-if="submitting" class="spinner"></span>
                {{ submitting ? 'AI 正在评估' : '提交回答' }}
              </button>
            </div>
          </form>
        </article>

        <article v-else-if="detail.interview.status === 'active'" class="card finish-card">
          <div class="finish-mark">✓</div>
          <p class="eyebrow">All questions answered</p>
          <h2>这场面试已经完成作答</h2>
          <p>系统将汇总每道题的表现，生成优势、薄弱点和下一轮训练建议。</p>
          <button class="button button-primary" :disabled="completing" @click="handleComplete">
            <span v-if="completing" class="spinner"></span>
            {{ completing ? '正在生成报告' : '生成面试报告' }}
          </button>
        </article>

        <article v-else class="card finish-card">
          <div class="finish-mark">✓</div>
          <h2>本场面试已完成</h2>
          <router-link
            class="button button-primary"
            :to="`/interviews/${detail.interview.id}/report`"
          >
            查看面试报告
          </router-link>
        </article>

        <article v-if="latestFeedback" class="card feedback-card">
          <div class="feedback-head">
            <div>
              <p class="eyebrow">AI feedback</p>
              <h3>上一题即时反馈</h3>
            </div>
            <strong>{{ latestFeedback.score }}<small>/100</small></strong>
          </div>
          <p>{{ latestFeedback.content }}</p>
          <div class="feedback-columns">
            <div>
              <span>做得不错</span>
              <ul>
                <li v-for="item in latestFeedback.metadata.strengths" :key="item">
                  {{ item }}
                </li>
              </ul>
            </div>
            <div>
              <span>继续改进</span>
              <ul>
                <li v-for="item in latestFeedback.metadata.improvements" :key="item">
                  {{ item }}
                </li>
              </ul>
            </div>
          </div>
          <div v-if="latestFollowUp" class="follow-up">
            <strong>追问思考</strong>
            <p>{{ latestFollowUp.content }}</p>
          </div>
        </article>
      </main>

      <aside class="question-nav card">
        <p class="eyebrow">Question map</p>
        <h3>问题列表</h3>
        <div class="question-list">
          <div
            v-for="(question, index) in questionMessages"
            :key="question.id"
            :class="[
              'question-item',
              {
                current: currentQuestion?.id === question.id,
                answered: answeredIds.has(question.id),
              },
            ]"
          >
            <span>{{ answeredIds.has(question.id) ? '✓' : index + 1 }}</span>
            <div>
              <strong>{{ question.content }}</strong>
              <small>
                {{
                  answeredIds.has(question.id)
                    ? `${scoreFor(question.id)?.score || '—'} 分`
                    : currentQuestion?.id === question.id
                      ? '正在作答'
                      : '等待作答'
                }}
              </small>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getErrorMessage } from '../api/client'
import {
  completeInterview,
  getInterview,
  submitAnswer,
} from '../api/interview'

const route = useRoute()
const router = useRouter()
const detail = ref(null)
const loading = ref(true)
const submitting = ref(false)
const completing = ref(false)
const error = ref('')
const answer = ref('')
const latestFeedbackId = ref(null)
const difficultyLabel = { easy: '基础', medium: '进阶', hard: '挑战' }

const questionMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type === 'question') || [],
)
const answerMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type === 'answer') || [],
)
const scoreMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type === 'score') || [],
)
const followUpMessages = computed(() =>
  detail.value?.messages.filter((message) => message.message_type === 'follow_up') || [],
)
const answeredIds = computed(
  () =>
    new Set(
      answerMessages.value.map((message) => message.metadata.question_message_id),
    ),
)
const currentQuestion = computed(() =>
  questionMessages.value.find((question) => !answeredIds.value.has(question.id)),
)
const currentIndex = computed(() =>
  Math.max(
    questionMessages.value.findIndex(
      (question) => question.id === currentQuestion.value?.id,
    ),
    0,
  ),
)
const progress = computed(() =>
  questionMessages.value.length
    ? Math.round((answeredIds.value.size / questionMessages.value.length) * 100)
    : 0,
)
const latestFeedback = computed(() => {
  if (latestFeedbackId.value) {
    return scoreMessages.value.find(
      (message) => message.id === latestFeedbackId.value,
    )
  }
  return scoreMessages.value.at(-1)
})
const latestFollowUp = computed(() => {
  const questionId = latestFeedback.value?.metadata.question_message_id
  return followUpMessages.value.find(
    (message) => message.metadata.question_message_id === questionId,
  )
})

function scoreFor(questionId) {
  return scoreMessages.value.find(
    (message) => message.metadata.question_message_id === questionId,
  )
}

async function loadInterview() {
  error.value = ''
  try {
    detail.value = await getInterview(route.params.id)
  } catch (requestError) {
    error.value = getErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!currentQuestion.value) return
  error.value = ''
  submitting.value = true
  try {
    const result = await submitAnswer(route.params.id, {
      question_message_id: currentQuestion.value.id,
      answer: answer.value,
      top_k: 5,
    })
    latestFeedbackId.value = result.score_message.id
    answer.value = ''
    await loadInterview()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '回答提交失败')
  } finally {
    submitting.value = false
  }
}

async function handleComplete() {
  completing.value = true
  error.value = ''
  try {
    await completeInterview(route.params.id)
    router.push(`/interviews/${route.params.id}/report`)
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '报告生成失败')
  } finally {
    completing.value = false
  }
}

onMounted(loadInterview)
</script>

<style scoped>
.session-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.session-header a {
  display: inline-block;
  margin-bottom: 16px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.session-header h1 {
  margin-bottom: 6px;
  font-size: clamp(28px, 4vw, 42px);
  letter-spacing: -0.04em;
}

.session-header p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.progress-box {
  display: flex;
  align-items: center;
  gap: 13px;
}

.progress-box strong {
  font-size: 34px;
}

.progress-box span {
  color: var(--muted);
}

.progress-box small {
  width: 45px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.3;
}

.progress-track {
  height: 5px;
  margin: 24px 0 30px;
  overflow: hidden;
  border-radius: 10px;
  background: #dfe5dd;
}

.progress-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--green), #79a94e);
  transition: width 300ms ease;
}

.interview-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 22px;
  align-items: start;
}

.question-stage {
  display: grid;
  gap: 18px;
}

.question-card {
  padding: clamp(24px, 5vw, 50px);
}

.question-label {
  display: flex;
  justify-content: space-between;
  color: var(--green);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.question-label em {
  color: var(--orange);
  font-style: normal;
}

.question-card h2 {
  margin: 24px 0 13px;
  font-size: clamp(23px, 3vw, 34px);
  line-height: 1.35;
  letter-spacing: -0.035em;
}

.coach-note {
  margin-bottom: 30px;
  color: var(--muted);
  font-size: 13px;
}

.answer-form {
  padding-top: 26px;
  border-top: 1px solid var(--line);
}

.answer-form textarea {
  min-height: 210px;
  line-height: 1.7;
}

.answer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
}

.answer-actions > span {
  color: var(--muted);
  font-size: 11px;
}

.question-nav {
  position: sticky;
  top: 98px;
  padding: 22px;
  box-shadow: none;
}

.question-nav h3 {
  margin-bottom: 18px;
}

.question-list {
  display: grid;
  gap: 6px;
}

.question-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 11px;
}

.question-item.current {
  background: #f0f5ef;
}

.question-item > span {
  display: grid;
  width: 25px;
  height: 25px;
  flex: 0 0 25px;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
}

.question-item.answered > span {
  color: var(--green-dark);
  border-color: transparent;
  background: var(--lime);
}

.question-item div {
  min-width: 0;
}

.question-item strong,
.question-item small {
  display: block;
}

.question-item strong {
  overflow: hidden;
  font-size: 11px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-item small {
  margin-top: 3px;
  color: var(--muted);
  font-size: 9px;
}

.feedback-card {
  padding: 26px;
  box-shadow: none;
}

.feedback-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
}

.feedback-head h3 {
  margin: 0;
}

.feedback-head > strong {
  color: var(--green);
  font-size: 34px;
}

.feedback-head small {
  color: var(--muted);
  font-size: 11px;
}

.feedback-card > p {
  color: var(--muted);
  line-height: 1.65;
}

.feedback-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.feedback-columns > div {
  padding: 16px;
  border-radius: 13px;
  background: #f6f8f4;
}

.feedback-columns span,
.follow-up strong {
  color: var(--green-dark);
  font-size: 11px;
  font-weight: 700;
}

.feedback-columns ul {
  margin: 10px 0 0;
  padding-left: 17px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}

.follow-up {
  margin-top: 12px;
  padding: 16px;
  border-left: 3px solid var(--orange);
  border-radius: 4px 12px 12px 4px;
  background: #fff7ed;
}

.follow-up p {
  margin: 7px 0 0;
  font-size: 13px;
  line-height: 1.6;
}

.finish-card {
  padding: 64px 28px;
  text-align: center;
}

.finish-mark {
  display: grid;
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  place-items: center;
  border-radius: 50%;
  color: var(--green-dark);
  background: var(--lime);
  font-size: 28px;
  font-weight: 700;
}

.finish-card > p:not(.eyebrow) {
  max-width: 500px;
  margin: 0 auto 24px;
  color: var(--muted);
}

@media (max-width: 850px) {
  .interview-layout {
    grid-template-columns: 1fr;
  }

  .question-nav {
    position: static;
    grid-row: 1;
  }

  .question-list {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 560px) {
  .session-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .answer-actions,
  .feedback-columns {
    align-items: stretch;
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .answer-actions .button {
    width: 100%;
  }

  .question-list {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
