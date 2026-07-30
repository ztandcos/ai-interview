import api from './client'

export const listInterviews = () =>
  api.get('/interviews').then((response) => response.data)

export const startInterview = (payload) =>
  api.post('/interviews', payload).then((response) => response.data)

export const getInterview = (interviewId) =>
  api.get(`/interviews/${interviewId}`).then((response) => response.data)

export const submitAnswer = (interviewId, payload) =>
  api
    .post(`/interviews/${interviewId}/answers`, payload)
    .then((response) => response.data)

export const completeInterview = (interviewId) =>
  api
    .post(`/interviews/${interviewId}/complete`)
    .then((response) => response.data)

export const deleteInterview = (interviewId) =>
  api
    .delete(`/interviews/${interviewId}`)
    .then((response) => response.data)
