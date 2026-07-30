<template>
  <section v-if="loading" class="card loading-block">正在读取面试报告…</section>

  <section v-else-if="error || !detail?.report" class="card empty-state">
    <div class="empty-icon">!</div>
    <h3>报告暂时不可用</h3>
    <p>{{ error || '这场面试还没有完成。' }}</p>
    <router-link class="button button-secondary" :to="`/interviews/${route.params.id}`">
      返回面试
    </router-link>
  </section>

  <section v-else class="report-page">
    <div class="report-actions">
      <router-link to="/dashboard">← 返回控制台</router-link>
      <button class="button button-secondary button-small" @click="printReport">
        打印报告
      </button>
    </div>

    <article class="report-hero">
      <div class="hero-copy">
        <p class="eyebrow">Interview report</p>
        <h1>{{ detail.interview.focus }}</h1>
        <p>
          {{ formatDate(detail.interview.completed_at) }} ·
          {{ difficultyLabel[detail.interview.difficulty] }}难度 ·
          {{ detail.interview.question_count }} 道题
        </p>
      </div>
      <div class="score-ring" :style="{ '--score': report.overall_score }">
        <div>
          <strong>{{ report.overall_score }}</strong>
          <small>OVERALL</small>
        </div>
      </div>
    </article>

    <div class="summary-card card">
      <span>总体评价</span>
      <p>{{ report.summary }}</p>
    </div>

    <div class="insight-grid">
      <article class="card insight-card strength-card">
        <div class="insight-icon">＋</div>
        <h2>表现亮点</h2>
        <ul>
          <li v-for="item in report.strengths" :key="item">{{ item }}</li>
        </ul>
      </article>
      <article class="card insight-card weakness-card">
        <div class="insight-icon">△</div>
        <h2>需要加强</h2>
        <ul>
          <li v-for="item in report.weaknesses" :key="item">{{ item }}</li>
        </ul>
      </article>
      <article class="card insight-card suggestion-card">
        <div class="insight-icon">→</div>
        <h2>下一步建议</h2>
        <ul>
          <li v-for="item in report.suggestions" :key="item">{{ item }}</li>
        </ul>
      </article>
    </div>

    <div class="transcript-heading">
      <div>
        <h2>逐题复盘</h2>
        <p>回看每道题的回答与即时得分。</p>
      </div>
    </div>

    <div class="transcript-list">
      <details
        v-for="(item, index) in transcript"
        :key="item.question.id"
        class="card transcript-item"
        :open="index === 0"
      >
        <summary>
          <span class="question-number">{{ String(index + 1).padStart(2, '0') }}</span>
          <strong>{{ item.question.content }}</strong>
          <em>{{ item.score?.score ?? '—' }} 分</em>
        </summary>
        <div class="transcript-body">
          <div>
            <span>你的回答</span>
            <p>{{ item.answer?.content || '未作答' }}</p>
          </div>
          <div>
            <span>AI 反馈</span>
            <p>{{ item.score?.content || '暂无反馈' }}</p>
          </div>
          <div v-if="item.followUp">
            <span>追问思考</span>
            <p>{{ item.followUp.content }}</p>
          </div>
        </div>
      </details>
    </div>

    <div class="report-footer">
      <router-link class="button button-primary" to="/resume/new">
        再练一场
      </router-link>
      <router-link class="button button-secondary" to="/dashboard">
        查看全部记录
      </router-link>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getErrorMessage } from '../api/client'
import { getInterview } from '../api/interview'

const route = useRoute()
const detail = ref(null)
const loading = ref(true)
const error = ref('')
const difficultyLabel = { easy: '基础', medium: '进阶', hard: '挑战' }
const report = computed(() => detail.value.report)
const transcript = computed(() => {
  const messages = detail.value?.messages || []
  const questions = messages.filter((item) => item.message_type === 'question')
  return questions.map((question) => ({
    question,
    answer: messages.find(
      (item) =>
        item.message_type === 'answer' &&
        item.metadata.question_message_id === question.id,
    ),
    score: messages.find(
      (item) =>
        item.message_type === 'score' &&
        item.metadata.question_message_id === question.id,
    ),
    followUp: messages.find(
      (item) =>
        item.message_type === 'follow_up' &&
        item.metadata.question_message_id === question.id,
    ),
  }))
})

function formatDate(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function printReport() {
  window.print()
}

onMounted(async () => {
  try {
    detail.value = await getInterview(route.params.id)
  } catch (requestError) {
    error.value = getErrorMessage(requestError)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.report-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.report-hero {
  display: flex;
  min-height: 310px;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  padding: clamp(32px, 7vw, 78px);
  border-radius: 28px;
  color: #fff;
  background:
    radial-gradient(circle at 90% 20%, rgba(201, 239, 142, 0.18), transparent 22rem),
    var(--green-dark);
}

.hero-copy .eyebrow {
  color: var(--lime);
}

.hero-copy p:last-child {
  color: rgba(255, 255, 255, 0.62);
}

.score-ring {
  display: grid;
  width: 174px;
  height: 174px;
  flex: 0 0 174px;
  place-items: center;
  border-radius: 50%;
  background:
    radial-gradient(circle at center, var(--green-dark) 59%, transparent 60%),
    conic-gradient(var(--lime) calc(var(--score) * 1%), rgba(255, 255, 255, 0.13) 0);
}

.score-ring div {
  text-align: center;
}

.score-ring strong,
.score-ring small {
  display: block;
}

.score-ring strong {
  font-size: 52px;
  line-height: 1;
  letter-spacing: -0.06em;
}

.score-ring small {
  margin-top: 7px;
  color: rgba(255, 255, 255, 0.58);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.summary-card {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 20px;
  margin-top: 18px;
  padding: 27px;
  box-shadow: none;
}

.summary-card span {
  color: var(--green);
  font-size: 12px;
  font-weight: 700;
}

.summary-card p {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.insight-card {
  min-height: 280px;
  padding: 26px;
  box-shadow: none;
}

.insight-icon {
  display: grid;
  width: 38px;
  height: 38px;
  margin-bottom: 25px;
  place-items: center;
  border-radius: 12px;
  font-weight: 700;
}

.strength-card .insight-icon {
  color: var(--green-dark);
  background: var(--lime);
}

.weakness-card .insight-icon {
  color: #93433c;
  background: #f8ded9;
}

.suggestion-card .insight-icon {
  color: #855522;
  background: #ffedd2;
}

.insight-card h2 {
  font-size: 18px;
}

.insight-card ul {
  display: grid;
  gap: 10px;
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.55;
}

.transcript-heading {
  margin: 50px 0 17px;
}

.transcript-heading h2 {
  margin-bottom: 5px;
}

.transcript-heading p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.transcript-list {
  display: grid;
  gap: 9px;
}

.transcript-item {
  overflow: hidden;
  box-shadow: none;
}

.transcript-item summary {
  display: grid;
  grid-template-columns: 42px 1fr auto;
  gap: 15px;
  align-items: center;
  padding: 19px 22px;
  cursor: pointer;
  list-style: none;
}

.question-number {
  color: var(--green);
  font-size: 11px;
  font-weight: 700;
}

.transcript-item summary strong {
  font-size: 14px;
}

.transcript-item summary em {
  color: var(--green);
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
}

.transcript-body {
  display: grid;
  gap: 16px;
  padding: 0 22px 22px 79px;
}

.transcript-body > div {
  padding: 15px;
  border-radius: 12px;
  background: #f6f8f4;
}

.transcript-body span {
  color: var(--green);
  font-size: 10px;
  font-weight: 700;
}

.transcript-body p {
  margin: 7px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}

.report-footer {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 32px;
}

@media (max-width: 800px) {
  .insight-grid {
    grid-template-columns: 1fr;
  }

  .insight-card {
    min-height: 0;
  }
}

@media (max-width: 560px) {
  .report-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .score-ring {
    width: 130px;
    height: 130px;
    flex-basis: 130px;
  }

  .summary-card {
    grid-template-columns: 1fr;
  }

  .transcript-body {
    padding-left: 22px;
  }

  .report-footer {
    align-items: stretch;
    flex-direction: column;
  }
}

@media print {
  .report-actions,
  .report-footer {
    display: none;
  }
}
</style>
