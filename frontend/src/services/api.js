import axios from 'axios'

const backendClient = axios.create({
  baseURL: 'http://127.0.0.1:5000'
})

export async function createProcessingTask(videoFiles) {
  const formData = new FormData()
  videoFiles.forEach((file) => formData.append('videos', file))
  const response = await backendClient.post('/api/tasks', formData)
  return response.data
}

export function openTaskStream(taskId, handlers) {
  const eventSource = new EventSource(`http://127.0.0.1:5000/api/tasks/${taskId}/stream`)

  eventSource.addEventListener('task_snapshot', (event) => {
    handlers.onSnapshot?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('video_result', (event) => {
    handlers.onVideoResult?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('task_completed', (event) => {
    handlers.onCompleted?.(JSON.parse(event.data))
    eventSource.close()
  })

  eventSource.onerror = (error) => {
    handlers.onError?.(error)
  }

  return eventSource
}
