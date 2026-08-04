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

export async function streamAnswer(interviewId, payload, onEvent) {
  const accessToken = localStorage.getItem('access_token')
  const response = await fetch(`${api.defaults.baseURL}/interviews/${interviewId}/answers/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) {
    let detail = '回答提交失败'
    try {
      detail = (await response.json()).detail || detail
    } catch {
      // Keep the fallback message when the streaming response cannot be decoded.
    }
    throw new Error(detail)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const rawEvent of events) {
      const eventName = rawEvent.match(/^event: (.+)$/m)?.[1]
      const rawData = rawEvent.match(/^data: (.+)$/m)?.[1]
      if (eventName && rawData) onEvent(eventName, JSON.parse(rawData))
    }
    if (done) break
  }
}

export const completeInterview = (interviewId, payload = {}) =>
  api
    .post(`/interviews/${interviewId}/complete`, payload)
    .then((response) => response.data)

export const deleteInterview = (interviewId) =>
  api
    .delete(`/interviews/${interviewId}`)
    .then((response) => response.data)
