import { defineStore } from 'pinia'

import {
  getMe,
  login as loginRequest,
  logout as logoutRequest,
} from '../api/auth'
import { clearSession } from '../api/client'

function storedUser() {
  try {
    return JSON.parse(localStorage.getItem('auth_user') || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: storedUser(),
    accessToken: localStorage.getItem('access_token'),
    refreshToken: localStorage.getItem('refresh_token'),
    ready: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
    displayName: (state) =>
      state.user?.full_name || state.user?.email?.split('@')[0] || '同学',
  },
  actions: {
    persistUser(user) {
      this.user = user
      localStorage.setItem('auth_user', JSON.stringify(user))
    },
    async initialize() {
      if (!this.accessToken) {
        this.ready = true
        return
      }
      try {
        this.persistUser(await getMe())
      } catch {
        this.clear()
      } finally {
        this.ready = true
      }
    },
    async login(payload) {
      const tokens = await loginRequest(payload)
      this.accessToken = tokens.access_token
      this.refreshToken = tokens.refresh_token
      localStorage.setItem('access_token', this.accessToken)
      localStorage.setItem('refresh_token', this.refreshToken)
      this.persistUser(await getMe())
    },
    async logout() {
      try {
        if (this.refreshToken) {
          await logoutRequest(this.refreshToken)
        }
      } finally {
        this.clear()
      }
    },
    clear() {
      clearSession()
      this.user = null
      this.accessToken = null
      this.refreshToken = null
    },
  },
})
