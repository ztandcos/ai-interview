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
        <p class="eyebrow">Welcome back</p>
        <h1>继续你的面试训练</h1>
        <p class="auth-subtitle">
          登录后从上次中断的位置继续，所有回答和报告都会自动保存。
        </p>

        <form class="auth-form" @submit.prevent="handleLogin">
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
              autocomplete="current-password"
              minlength="8"
              placeholder="至少 8 位"
              required
              type="password"
            />
          </div>

          <div class="field">
            <label for="code">登录验证码</label>
            <div class="code-row">
              <input
                id="code"
                v-model.trim="form.code"
                inputmode="numeric"
                maxlength="6"
                placeholder="6 位数字"
                required
              />
              <button
                class="button button-secondary"
                :disabled="sendingCode || countdown > 0 || !form.email"
                type="button"
                @click="handleSendCode"
              >
                {{ countdown > 0 ? `${countdown}s` : sendingCode ? '发送中' : '获取验证码' }}
              </button>
            </div>
            <small v-if="debugMessage">{{ debugMessage }}</small>
          </div>

          <p v-if="error" class="form-error">{{ error }}</p>

          <button class="button button-primary" :disabled="loading" type="submit">
            <span v-if="loading" class="spinner"></span>
            {{ loading ? '正在登录' : '进入控制台' }}
          </button>
        </form>

        <p class="auth-switch">
          还没有账号？<router-link to="/register">免费注册</router-link>
        </p>
      </div>
    </section>

    <aside class="auth-visual">
      <div class="visual-content">
        <span class="visual-kicker">PRACTICE WITH CONTEXT</span>
        <h2>让每一次回答，都比上一次更具体。</h2>
        <p>
          PrepPilot 会读取你的真实项目经历，生成有依据的问题，并把每次回答变成可复盘的成长记录。
        </p>
        <div class="visual-proof">
          <div class="proof-card"><strong>RAG</strong><small>简历上下文</small></div>
          <div class="proof-card"><strong>1:1</strong><small>个性化出题</small></div>
          <div class="proof-card"><strong>24/7</strong><small>随时可练</small></div>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { sendVerificationCode } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const form = reactive({
  email: String(route.query.email || ''),
  password: '',
  code: '',
})
const error = ref('')
const loading = ref(false)
const sendingCode = ref(false)
const countdown = ref(0)
const debugMessage = ref('')
let timer

async function handleSendCode() {
  error.value = ''
  debugMessage.value = ''
  sendingCode.value = true
  try {
    const result = await sendVerificationCode(form.email)
    if (result.debug_code) {
      form.code = result.debug_code
      debugMessage.value = `本地开发验证码已自动填入：${result.debug_code}`
    } else {
      debugMessage.value = '验证码已发送，请检查邮箱。'
    }
    countdown.value = 60
    timer = window.setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        window.clearInterval(timer)
      }
    }, 1000)
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '验证码发送失败')
  } finally {
    sendingCode.value = false
  }
}

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(form)
    router.push(String(route.query.redirect || '/dashboard'))
  } catch (requestError) {
    error.value = getErrorMessage(requestError, '登录失败')
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => window.clearInterval(timer))
</script>
