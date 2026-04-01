import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'http://localhost:5000/api',
  timeout: 30000
})

export async function createVideoTask(videoFiles) {
  const formData = new FormData()
  videoFiles.forEach((videoFile) => {
    formData.append('videos', videoFile)
  })

  const response = await apiClient.post('/tasks', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return response.data
}

export async function fetchTaskStatus(taskId) {
  const response = await apiClient.get(`/tasks/${taskId}`)
  return response.data
}
