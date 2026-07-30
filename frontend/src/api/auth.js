import api from './client'

export const register = (payload) =>
  api.post('/auth/register', payload).then((response) => response.data)

export const sendVerificationCode = (email) =>
  api
    .post('/verification/send', { email })
    .then((response) => response.data)

export const login = (payload) =>
  api.post('/auth/login', payload).then((response) => response.data)

export const logout = (refreshToken) =>
  api
    .post('/auth/logout', { refresh_token: refreshToken })
    .then((response) => response.data)

export const getMe = () =>
  api.get('/auth/me').then((response) => response.data)

export const updateMe = (payload) =>
  api.patch('/auth/me', payload).then((response) => response.data)

export const changePassword = (payload) =>
  api
    .post('/auth/change-password', payload)
    .then((response) => response.data)
