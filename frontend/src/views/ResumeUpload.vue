<template>
  <section class="setup-page">
    <div class="page-heading">
      <div>
        <p class="eyebrow">New session</p>
        <h1>配置一场面试</h1>
        <p>选择简历和目标岗位，其余准备工作交给 AI。</p>
      </div>
    </div>

    <div class="setup-grid">
      <form class="card setup-form" @submit.prevent="handleStart">
        <div class="form-section">
          <div class="section-index">01</div>
          <div class="section-content">
            <h2>选择简历</h2>
            <p>可以使用已有档案，也可以上传一份新的 PDF。</p>

            <div v-if="resumes.length" class="resume-options">
              <label
                v-for="resume in resumes"
                :key="resume.id"
                :class="['resume-option', { selected: selectedResumeId === resume.id }]"
              >
                <input
                  v-model="selectedResumeId"
                  :value="resume.id"
                  type="radio"
                />
                <span class="file-icon">PDF</span>
                <span class="file-copy">
                  <strong>{{ resume.original_filename }}</strong>
                  <small>
                    {{ formatSize(resume.file_size) }} ·
                    {{ formatDate(resume.created_at) }}
                  </small>
                </span>
                <button
                  class="delete-file"
                  type="button"
                  title="删除简历"
                  @click.prevent="handleDeleteResume(resume)"
                >
                  ×
                </button>
              </label>
            </div>

            <label
              :class="['dropzone', { dragging, 'has-file': selectedFile }]"
              @dragenter.prevent="dragging = true"
              @dragleave.prevent="dragging = false"
              @dragover.prevent
              @drop.prevent="handleDrop"
            >
              <input accept=".pdf,application/pdf" type="file" @change="handleFile" />
              <span class="upload-icon">{{ selectedFile ? '✓' : '↑' }}</span>
              <span>
                <strong>
                  {{ selectedFile ? selectedFile.name : '上传新的 PDF 简历' }}
                </strong>
                <small>
                  {{ selectedFile ? formatSize(selectedFile.size) : '点击选择或拖拽到这里，最大 5 MB' }}
                </small>
              </span>
            </label>
          </div>
        </div>

        <div class="form-section">
          <div class="section-index">02</div>
          <div class="section-content">
            <h2>定义目标</h2>
            <p>岗位越具体，问题与评价越有针对性。</p>
            <div class="field">
              <label for="focus">目标岗位</label>
              <input
                id="focus"
                v-model.trim="form.focus"
                maxlength="100"
                placeholder="例如：AI 应用开发实习生"
                required
              />
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="section-index">03</div>
          <div class="section-content">
            <h2>设置强度</h2>
            <p>第一次练习建议使用进阶难度和 5 道题。</p>
            <div class="difficulty-grid">
              <label
                v-for="option in difficultyOptions"
                :key="option.value"
                :class="['difficulty-option', { selected: form.difficulty === option.value }]"
              >
                <input v-model="form.difficulty" :value="option.value" type="radio" />
                <strong>{{ option.label }}</strong>
                <small>{{ option.description }}</small>
              </label>
            </div>
            <div class="question-count">
              <span>问题数量</span>
              <div>
                <button
                  type="button"
                  :disabled="form.question_count <= 3"
                  @click="form.question_count--"
                >
                  −
                </button>
                <strong>{{ form.question_count }}</strong>
                <button
                  type="button"
                  :disabled="form.question_count >= 10"
                  @click="form.question_count++"
                >
                  ＋
                </button>
              </div>
            </div>
          </div>
        </div>

        <p v-if="error" class="form-error">{{ error }}</p>
        <button class="button button-primary start-button" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? progressText : '生成面试题并开始' }}
        </button>
      </form>

      <aside class="setup-aside">
        <div class="card preview-card">
          <p class="eyebrow">Session preview</p>
          <h3>{{ form.focus || '你的目标岗位' }}</h3>
          <div class="preview-row">
            <span>难度</span><strong>{{ currentDifficulty.label }}</strong>
          </div>
          <div class="preview-row">
            <span>问题</span><strong>{{ form.question_count }} 道</strong>
          </div>
          <div class="preview-row">
            <span>上下文</span><strong>{{ selectedFile ? '新简历' : selectedResumeName }}</strong>
          </div>
          <div class="preview-flow">
            <span>简历解析</span><i></i><span>RAG 检索</span><i></i><span>个性出题</span>
          </div>
        </div>
        <div class="privacy-note">
          <strong>本地优先</strong>
          <p>简历文件保存在你的服务端，模型只接收检索到的相关片段。</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getErrorMessage } from '../api/client'
import { startInterview } from '../api/interview'
import { deleteResume, listResumes, uploadResume } from '../api/resume'

const router = useRouter()
const resumes = ref([])
const selectedResumeId = ref(null)
const selectedFile = ref(null)
const dragging = ref(false)
const loading = ref(false)
const error = ref('')
const progressText = ref('正在准备')
const form = reactive({
  focus: 'AI 应用开发实习生',
  difficulty: 'medium',
  question_count: 5,
})
const difficultyOptions = [
  { value: 'easy', label: '基础', description: '概念与项目概览' },
  { value: 'medium', label: '进阶', description: '实现、权衡与排错' },
  { value: 'hard', label: '挑战', description: '原理与系统设计' },
]

const currentDifficulty = computed(() =>
  difficultyOptions.find((item) => item.value === form.difficulty),
)
const selectedResumeName = computed(() => {
  const resume = resumes.value.find((item) => item.id === selectedResumeId.value)
  return resume?.original_filename || '尚未选择'
})

function formatSize(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatDate(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))
}

function setFile(file) {
  error.value = ''
  if (!file) return
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    error.value = '只能上传 PDF 文件'
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    error.value = 'PDF 文件不能超过 5 MB'
    return
  }
  selectedFile.value = file
  selectedResumeId.value = null
}

function handleFile(event) {
  setFile(event.target.files?.[0])
}

function handleDrop(event) {
  dragging.value = false
  setFile(event.dataTransfer.files?.[0])
}

async function handleDeleteResume(resume) {
  if (!window.confirm(`确定删除“${resume.original_filename}”吗？`)) return
  try {
    await deleteResume(resume.id)
    resumes.value = resumes.value.filter((item) => item.id !== resume.id)
    if (selectedResumeId.value === resume.id) {
      selectedResumeId.value = resumes.value[0]?.id || null
    }
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '简历删除失败')
  }
}

async function handleStart() {
  error.value = ''
  if (!selectedResumeId.value && !selectedFile.value) {
    error.value = '请先选择或上传一份简历'
    return
  }

  loading.value = true
  try {
    let resumeId = selectedResumeId.value
    if (selectedFile.value) {
      progressText.value = '正在解析简历'
      const resume = await uploadResume(selectedFile.value)
      resumeId = resume.id
    }
    progressText.value = '正在生成问题'
    const result = await startInterview({
      resume_id: resumeId,
      focus: form.focus,
      difficulty: form.difficulty,
      question_count: form.question_count,
      top_k: 5,
    })
    router.push(`/interviews/${result.interview.id}`)
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '面试创建失败')
  } finally {
    loading.value = false
    progressText.value = '正在准备'
  }
}

onMounted(async () => {
  try {
    resumes.value = await listResumes()
    selectedResumeId.value = resumes.value[0]?.id || null
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '简历列表加载失败')
  }
})
</script>

<style scoped>
.setup-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 24px;
  align-items: start;
}

.setup-form {
  padding: 0 32px 32px;
  box-shadow: none;
}

.form-section {
  display: grid;
  grid-template-columns: 52px 1fr;
  gap: 18px;
  padding: 34px 0;
  border-bottom: 1px solid #e9ede7;
}

.section-index {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 13px;
  color: var(--green-dark);
  background: var(--green-soft);
  font-size: 11px;
  font-weight: 700;
}

.section-content h2 {
  margin-bottom: 4px;
  font-size: 18px;
}

.section-content > p {
  margin-bottom: 22px;
  color: var(--muted);
  font-size: 13px;
}

.resume-options {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}

.resume-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: 14px;
  cursor: pointer;
}

.resume-option.selected {
  border-color: #80aa94;
  background: #f2f8f4;
}

.resume-option input,
.difficulty-option input,
.dropzone input {
  display: none;
}

.file-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 10px;
  color: #9b413d;
  background: #fae8e5;
  font-size: 9px;
  font-weight: 800;
}

.file-copy {
  min-width: 0;
  flex: 1;
}

.file-copy strong,
.file-copy small {
  display: block;
}

.file-copy strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-copy small {
  margin-top: 4px;
  color: var(--muted);
  font-size: 10px;
}

.delete-file {
  border: 0;
  color: #a2aaa4;
  background: transparent;
  font-size: 18px;
}

.dropzone {
  display: flex;
  min-height: 94px;
  align-items: center;
  justify-content: center;
  gap: 14px;
  border: 1px dashed #b8c4ba;
  border-radius: 15px;
  cursor: pointer;
  background: #f9fbf8;
  text-align: left;
}

.dropzone.dragging,
.dropzone.has-file {
  border-color: var(--green);
  background: var(--green-soft);
}

.upload-icon {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 12px;
  color: var(--green-dark);
  background: #fff;
  font-size: 19px;
  font-weight: 700;
}

.dropzone strong,
.dropzone small {
  display: block;
}

.dropzone strong {
  font-size: 13px;
}

.dropzone small {
  margin-top: 4px;
  color: var(--muted);
  font-size: 10px;
}

.difficulty-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.difficulty-option {
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 13px;
  cursor: pointer;
}

.difficulty-option.selected {
  border-color: var(--green);
  color: var(--green-dark);
  background: var(--green-soft);
}

.difficulty-option strong,
.difficulty-option small {
  display: block;
}

.difficulty-option strong {
  font-size: 13px;
}

.difficulty-option small {
  margin-top: 5px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.4;
}

.question-count {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  font-size: 13px;
  font-weight: 700;
}

.question-count div {
  display: flex;
  align-items: center;
  gap: 12px;
}

.question-count button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
}

.start-button {
  width: 100%;
  min-height: 52px;
  margin-top: 24px;
}

.setup-aside {
  position: sticky;
  top: 100px;
  display: grid;
  gap: 16px;
}

.preview-card {
  padding: 24px;
  color: #fff;
  border-color: var(--green-dark);
  background: var(--green-dark);
}

.preview-card .eyebrow {
  color: var(--lime);
}

.preview-card h3 {
  min-height: 60px;
  margin-bottom: 26px;
  font-size: 24px;
  line-height: 1.25;
}

.preview-row {
  display: flex;
  justify-content: space-between;
  padding: 11px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
}

.preview-row strong {
  max-width: 160px;
  overflow: hidden;
  color: #fff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-flow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24px;
  color: rgba(255, 255, 255, 0.65);
  font-size: 9px;
}

.preview-flow i {
  width: 15px;
  height: 1px;
  background: rgba(201, 239, 142, 0.5);
}

.privacy-note {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 17px;
  background: rgba(255, 255, 255, 0.55);
}

.privacy-note strong {
  font-size: 13px;
}

.privacy-note p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

@media (max-width: 850px) {
  .setup-grid {
    grid-template-columns: 1fr;
  }

  .setup-aside {
    display: none;
  }
}

@media (max-width: 560px) {
  .setup-form {
    padding: 0 18px 20px;
  }

  .form-section {
    grid-template-columns: 1fr;
  }

  .difficulty-grid {
    grid-template-columns: 1fr;
  }
}
</style>
