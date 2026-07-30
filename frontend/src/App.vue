<template>
  <div v-if="route.meta.guest" class="guest-layout">
    <router-view />
  </div>

  <div v-else class="app-layout">
    <header class="topbar">
      <router-link class="brand" to="/dashboard">
        <span class="brand-mark">P</span>
        <span>
          <strong>PrepPilot</strong>
          <small>AI INTERVIEW STUDIO</small>
        </span>
      </router-link>

      <nav class="desktop-nav">
        <router-link to="/dashboard">控制台</router-link>
        <router-link to="/resume/new">开始面试</router-link>
      </nav>

      <div class="user-menu">
        <router-link class="avatar-link" to="/profile">
          <span class="avatar">{{ initials }}</span>
          <span class="user-copy">
            <strong>{{ auth.displayName }}</strong>
            <small>个人设置</small>
          </span>
        </router-link>
        <button class="icon-button" title="退出登录" @click="handleLogout">
          ↗
        </button>
      </div>
    </header>

    <main class="page-shell">
      <router-view />
    </main>

    <nav class="mobile-nav">
      <router-link to="/dashboard">记录</router-link>
      <router-link class="mobile-primary" to="/resume/new">＋</router-link>
      <router-link to="/profile">我的</router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const initials = computed(() =>
  auth.displayName.slice(0, 2).toLocaleUpperCase(),
)

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>
