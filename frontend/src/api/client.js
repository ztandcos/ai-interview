import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 45000,
})

let refreshPromise = null

api.interceptors.request.use((config) => {
  const accessToken = localStorage.getItem('access_token')
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config
    const isAuthRequest =
      request?.url?.includes('/auth/login') ||
      request?.url?.includes('/auth/refresh')

    if (error.response?.status !== 401 || request?._retried || isAuthRequest) {
      return Promise.reject(error)
    }

    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      clearSession()
      return Promise.reject(error)
    }

    request._retried = true
    try {
      refreshPromise ||= axios
        .post(
          `${api.defaults.baseURL}/auth/refresh`,
          { refresh_token: refreshToken },
          { timeout: 15000 },
        )
        .then((response) => response.data.access_token)
        .finally(() => {
          refreshPromise = null
        })

      const accessToken = await refreshPromise
      localStorage.setItem('access_token', accessToken)
      request.headers.Authorization = `Bearer ${accessToken}`
      return api(request)
    } catch (refreshError) {
      clearSession()
      window.location.assign('/login')
      return Promise.reject(refreshError)
    }
  },
)

export function clearSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('auth_user')
}

export function getErrorMessage(error, fallback = '请求失败，请稍后重试') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join('；')
  }
  return detail || error?.message || fallback
}

export default api
