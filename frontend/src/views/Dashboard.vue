<template>
  <section>
    <div class="page-heading">
      <div>
        <p class="eyebrow">Your practice room</p>
        <h1>你好，{{ auth.displayName }}</h1>
        <p>回顾最近表现，或者开始一场围绕真实简历的模拟面试。</p>
      </div>
      <router-link class="button button-primary" to="/resume/new">
        ＋ 开始新面试
      </router-link>
    </div>

    <div class="stats-grid">
      <article class="stat-card stat-primary">
        <span>累计训练</span>
        <strong>{{ interviews.length }}</strong>
        <small>场模拟面试</small>
      </article>
      <article class="stat-card">
        <span>已完成</span>
        <strong>{{ completed.length }}</strong>
        <small>份复盘报告</small>
      </article>
      <article class="stat-card">
        <span>平均得分</span>
        <strong>{{ averageScore || '—' }}</strong>
        <small>{{ averageScore ? '满分 100' : '完成面试后生成' }}</small>
      </article>
      <article class="stat-card">
        <span>简历档案</span>
        <strong>{{ resumes.length }}</strong>
        <small>份可用简历</small>
      </article>
    </div>

    <div class="section-heading">
      <div>
        <h2>最近面试</h2>
        <p>每一场都保留问题、回答、评分和改进建议。</p>
      </div>
      <span v-if="interviews.length" class="record-count">
        {{ interviews.length }} records
      </span>
    </div>

    <div v-if="loading" class="card loading-block">正在整理训练记录…</div>

    <div v-else-if="error" class="card empty-state">
      <div class="empty-icon">!</div>
      <h3>记录加载失败</h3>
      <p>{{ error }}</p>
      <button class="button button-secondary" @click="loadData">重新加载</button>
    </div>

    <div v-else-if="!interviews.length" class="card empty-state">
      <div class="empty-icon">◎</div>
      <h3>从第一场模拟面试开始</h3>
      <p>上传 PDF 简历，AI 会围绕你的目标岗位开启一场实时面试对话。</p>
      <router-link class="button button-primary" to="/resume/new">
        上传简历并开始
      </router-link>
    </div>

    <div v-else class="interview-grid">
      <article
        v-for="item in interviews"
        :key="item.id"
        class="card interview-card"
      >
        <div class="interview-top">
          <span :class="['status-badge', `status-${item.status}`]">
            {{ item.status === 'completed' ? '已完成' : '进行中' }}
          </span>
          <button
            class="more-button"
            title="删除记录"
            @click="handleDelete(item)"
          >
            ×
          </button>
        </div>

        <div class="interview-main">
          <span class="difficulty">{{ difficultyLabel[item.difficulty] }}</span>
          <h3>{{ item.focus }}</h3>
          <p>{{ item.title }}</p>
        </div>

        <div class="interview-meta">
          <span><b>{{ item.question_count || 'AI' }}</b> {{ item.question_count ? '道问题' : '自主结束' }}</span>
          <span>{{ formatDate(item.created_at) }}</span>
        </div>

        <router-link
          class="card-link"
          :to="
            item.status === 'completed'
              ? `/interviews/${item.id}/report`
              : `/interviews/${item.id}`
          "
        >
          {{ item.status === 'completed' ? '查看复盘报告' : '继续面试' }}
          <span>→</span>
        </router-link>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { getErrorMessage } from '../api/client'
import { deleteInterview, listInterviews } from '../api/interview'
import { listResumes } from '../api/resume'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const interviews = ref([])
const resumes = ref([])
const loading = ref(true)
const error = ref('')
const difficultyLabel = { easy: '基础', medium: '进阶', hard: '挑战' }

const completed = computed(() =>
  interviews.value.filter((item) => item.status === 'completed'),
)
const averageScore = computed(() => {
  const scores = completed.value
    .map((item) => Number(item.overall_score))
    .filter(Number.isFinite)
  if (!scores.length) return null
  return Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
})

function formatDate(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    ;[interviews.value, resumes.value] = await Promise.all([
      listInterviews(),
      listResumes(),
    ])
  } catch (requestError) {
    error.value = getErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function handleDelete(item) {
  if (!window.confirm(`确定删除“${item.focus}”这场面试吗？`)) return
  try {
    await deleteInterview(item.id)
    interviews.value = interviews.value.filter((record) => record.id !== item.id)
  } catch (requestError) {
    window.alert(getErrorMessage(requestError, '删除失败'))
  }
}

onMounted(loadData)
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  min-height: 152px;
  padding: 23px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
}

.stat-card span,
.stat-card small,
.stat-card strong {
  display: block;
}

.stat-card span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.stat-card strong {
  margin: 14px 0 4px;
  font-size: 38px;
  line-height: 1;
  letter-spacing: -0.05em;
}

.stat-card small {
  color: #8a948d;
  font-size: 11px;
}

.stat-primary {
  color: #fff;
  border-color: var(--green);
  background: var(--green);
}

.stat-primary::after {
  position: absolute;
  right: -40px;
  bottom: -70px;
  width: 150px;
  height: 150px;
  border: 24px solid rgba(201, 239, 142, 0.14);
  border-radius: 50%;
  content: '';
}

.stat-primary span,
.stat-primary small {
  color: rgba(255, 255, 255, 0.65);
}

.section-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  margin: 48px 0 18px;
}

.section-heading h2 {
  margin-bottom: 5px;
  font-size: 22px;
}

.section-heading p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.record-count {
  color: #8a948d;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.interview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.interview-card {
  overflow: hidden;
  padding: 20px 20px 0;
  box-shadow: none;
  transition: 180ms ease;
}

.interview-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
}

.interview-top,
.interview-meta,
.card-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.more-button {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  color: #a2aaa4;
  background: transparent;
  font-size: 19px;
}

.more-button:hover {
  color: var(--red);
  background: #fae8e5;
}

.interview-main {
  min-height: 125px;
  padding-top: 28px;
}

.difficulty {
  color: var(--orange);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.interview-main h3 {
  margin: 8px 0 7px;
  font-size: 19px;
  line-height: 1.35;
}

.interview-main p {
  color: var(--muted);
  font-size: 12px;
}

.interview-meta {
  padding: 15px 0;
  border-top: 1px solid #edf0eb;
  color: var(--muted);
  font-size: 11px;
}

.interview-meta b {
  color: var(--ink);
}

.card-link {
  margin: 0 -20px;
  padding: 15px 20px;
  color: var(--green-dark);
  background: #f6f9f5;
  font-size: 13px;
  font-weight: 700;
}

@media (max-width: 900px) {
  .stats-grid,
  .interview-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 560px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .interview-grid {
    grid-template-columns: 1fr;
  }

  .stat-card {
    min-height: 128px;
    padding: 18px;
  }
}
</style>
