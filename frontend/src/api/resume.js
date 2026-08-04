import api from './client'

export const listResumes = () =>
  api.get('/resumes').then((response) => response.data)

export const getResume = (resumeId) =>
  api.get(`/resumes/${resumeId}`).then((response) => response.data)

export const uploadResume = (file, onUploadProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return api
    .post('/resumes', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
    })
    .then((response) => response.data)
}

export const deleteResume = (resumeId) =>
  api.delete(`/resumes/${resumeId}`).then((response) => response.data)
