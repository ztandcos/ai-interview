<template>
  <div class="auth-page">
    <section class="auth-panel">
      <router-link class="brand" to="/login">
        <span class="brand-mark">P</span>
        <span>
          <strong>PrepPilot</strong>
          <small>AI INTERVIEW STUDIO</small>
        </span>
      </router-link>

      <div class="auth-form-wrap">
        <p class="eyebrow">Create account</p>
        <h1>建立你的训练档案</h1>
        <p class="auth-subtitle">
          一个账号保存简历、面试记录和每次改进轨迹。
        </p>

        <form class="auth-form" @submit.prevent="handleRegister">
          <div class="field">
            <label for="name">怎么称呼你</label>
            <input
              id="name"
              v-model.trim="form.full_name"
              autocomplete="name"
              maxlength="100"
              placeholder="例如：小林"
            />
          </div>
          <div class="field">
            <label for="email">邮箱</label>
            <input
              id="email"
              v-model.trim="form.email"
              autocomplete="email"
              placeholder="you@example.com"
              required
              type="email"
            />
          </div>
          <div class="field">
            <label for="password">密码</label>
            <input
              id="password"
              v-model="form.password"
              autocomplete="new-password"
              minlength="8"
              placeholder="至少 8 位"
              required
              type="password"
            />
          </div>
          <div class="field">
            <label for="confirm">确认密码</label>
            <input
              id="confirm"
              v-model="confirmPassword"
              autocomplete="new-password"
              minlength="8"
              placeholder="再次输入密码"
              required
              type="password"
            />
          </div>

          <p v-if="error" class="form-error">{{ error }}</p>
          <button class="button button-primary" :disabled="loading" type="submit">
            <span v-if="loading" class="spinner"></span>
            {{ loading ? '正在创建' : '创建账号' }}
          </button>
        </form>

        <p class="auth-switch">
          已经有账号？<router-link to="/login">直接登录</router-link>
        </p>
      </div>
    </section>

    <aside class="auth-visual">
      <div class="visual-content">
        <span class="visual-kicker">FROM RESUME TO READINESS</span>
        <h2>简历只是起点，表达才是结果。</h2>
        <p>
          上传一份 PDF，选择目标岗位，AI 会围绕你的项目细节持续追问，并在面试后给出清晰的下一步。
        </p>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { register } from '../api/auth'
import { getErrorMessage } from '../api/client'

const router = useRouter()
const form = reactive({ email: '', password: '', full_name: '' })
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleRegister() {
  error.value = ''
  if (form.password !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await register({
      ...form,
      full_name: form.full_name || null,
    })
    router.push({ path: '/login', query: { email: form.email } })
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '注册失败')
  } finally {
    loading.value = false
  }
}
</script>
