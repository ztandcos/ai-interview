<template>
  <section>
    <div class="page-heading">
      <div>
        <p class="eyebrow">Account settings</p>
        <h1>个人设置</h1>
        <p>管理你的公开称呼和登录密码。</p>
      </div>
    </div>

    <div class="profile-grid">
      <aside class="card identity-card">
        <span class="large-avatar">{{ initials }}</span>
        <h2>{{ auth.displayName }}</h2>
        <p>{{ auth.user?.email }}</p>
        <div class="identity-meta">
          <span>账号状态</span><strong>正常</strong>
        </div>
        <div class="identity-meta">
          <span>加入时间</span><strong>{{ joinedAt }}</strong>
        </div>
      </aside>

      <main class="settings-stack">
        <form class="card settings-card" @submit.prevent="handleProfileUpdate">
          <div class="settings-head">
            <div>
              <h2>基本资料</h2>
              <p>这个称呼会显示在控制台和报告中。</p>
            </div>
          </div>
          <div class="field">
            <label for="name">称呼</label>
            <input id="name" v-model.trim="profileForm.full_name" maxlength="100" />
          </div>
          <div class="field">
            <label for="email">登录邮箱</label>
            <input id="email" :value="auth.user?.email" disabled />
            <small>当前版本暂不支持修改登录邮箱。</small>
          </div>
          <p v-if="profileMessage" :class="profileError ? 'form-error' : 'form-success'">
            {{ profileMessage }}
          </p>
          <button class="button button-primary" :disabled="savingProfile">
            {{ savingProfile ? '保存中' : '保存资料' }}
          </button>
        </form>

        <form class="card settings-card" @submit.prevent="handlePasswordChange">
          <div class="settings-head">
            <div>
              <h2>修改密码</h2>
              <p>修改后所有已签发的刷新令牌都会失效。</p>
            </div>
          </div>
          <div class="password-grid">
            <div class="field">
              <label for="current-password">当前密码</label>
              <input
                id="current-password"
                v-model="passwordForm.current_password"
                autocomplete="current-password"
                minlength="8"
                required
                type="password"
              />
            </div>
            <div class="field">
              <label for="new-password">新密码</label>
              <input
                id="new-password"
                v-model="passwordForm.new_password"
                autocomplete="new-password"
                minlength="8"
                required
                type="password"
              />
            </div>
          </div>
          <p v-if="passwordMessage" :class="passwordError ? 'form-error' : 'form-success'">
            {{ passwordMessage }}
          </p>
          <button class="button button-secondary" :disabled="savingPassword">
            {{ savingPassword ? '修改中' : '修改密码' }}
          </button>
        </form>

        <div class="card settings-card danger-zone">
          <div>
            <h2>退出当前账号</h2>
            <p>本机保存的登录状态会被清除，项目数据仍然保留。</p>
          </div>
          <button class="button button-danger" @click="handleLogout">退出登录</button>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { changePassword, updateMe } from '../api/auth'
import { getErrorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const profileForm = reactive({ full_name: auth.user?.full_name || '' })
const passwordForm = reactive({ current_password: '', new_password: '' })
const savingProfile = ref(false)
const savingPassword = ref(false)
const profileMessage = ref('')
const profileError = ref(false)
const passwordMessage = ref('')
const passwordError = ref(false)

const initials = computed(() => auth.displayName.slice(0, 2).toUpperCase())
const joinedAt = computed(() => {
  if (!auth.user?.created_at) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
  }).format(new Date(auth.user.created_at))
})

async function handleProfileUpdate() {
  savingProfile.value = true
  profileMessage.value = ''
  profileError.value = false
  try {
    const user = await updateMe({
      full_name: profileForm.full_name || null,
    })
    auth.persistUser(user)
    profileMessage.value = '资料已保存'
  } catch (requestError) {
    profileError.value = true
    profileMessage.value = getErrorMessage(requestError)
  } finally {
    savingProfile.value = false
  }
}

async function handlePasswordChange() {
  savingPassword.value = true
  passwordMessage.value = ''
  passwordError.value = false
  try {
    await changePassword(passwordForm)
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordMessage.value = '密码已修改。下次登录请使用新密码。'
  } catch (requestError) {
    passwordError.value = true
    passwordMessage.value = getErrorMessage(requestError, '密码修改失败')
  } finally {
    savingPassword.value = false
  }
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}

.identity-card {
  position: sticky;
  top: 100px;
  padding: 30px;
  text-align: center;
  box-shadow: none;
}

.large-avatar {
  display: grid;
  width: 82px;
  height: 82px;
  margin: 0 auto 17px;
  place-items: center;
  border-radius: 27px 16px 27px 16px;
  color: var(--green-dark);
  background: var(--lime);
  font-size: 25px;
  font-weight: 700;
}

.identity-card h2 {
  margin-bottom: 5px;
}

.identity-card > p {
  margin-bottom: 28px;
  color: var(--muted);
  font-size: 12px;
}

.identity-meta {
  display: flex;
  justify-content: space-between;
  padding: 13px 0;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 11px;
}

.identity-meta strong {
  color: var(--ink);
}

.settings-stack {
  display: grid;
  gap: 16px;
}

.settings-card {
  display: grid;
  gap: 18px;
  padding: 28px;
  box-shadow: none;
}

.settings-head {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line);
}

.settings-head h2,
.danger-zone h2 {
  margin-bottom: 5px;
  font-size: 18px;
}

.settings-head p,
.danger-zone p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.settings-card .button {
  width: max-content;
}

.field input:disabled {
  color: #8d958f;
  background: #edf0eb;
}

.password-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.danger-zone {
  grid-template-columns: 1fr auto;
  align-items: center;
  border-color: #efd7d3;
}

@media (max-width: 760px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .identity-card {
    position: static;
  }
}

@media (max-width: 540px) {
  .password-grid,
  .danger-zone {
    grid-template-columns: 1fr;
  }

  .settings-card .button {
    width: 100%;
  }
}
</style>
