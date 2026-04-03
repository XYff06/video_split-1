import axios from 'axios'

const backendClient = axios.create({
  baseURL: 'http://127.0.0.1:5000'
})

export async function createProcessingTask(videoFiles) {
  const formData = new FormData()

  videoFiles.forEach((file) => {
    const actualFile = file?.rawFile instanceof File ? file.rawFile : file
    if (actualFile instanceof File) {
      formData.append('videos', actualFile, actualFile.name)
    }
  })

  const response = await backendClient.post('/api/tasks', formData)
  return response.data
}

export async function generateCurrentVideoFissions(taskId, payload) {
  const response = await backendClient.post(`/api/tasks/${taskId}/fission/current-video`, payload)
  return response.data
}

export async function generateAllVideoFissions(taskId, payload) {
  const response = await backendClient.post(`/api/tasks/${taskId}/fission/all-videos`, payload)
  return response.data
}

export async function updateVideoFissionSize(taskId, videoIndex, payload) {
  const response = await backendClient.post(`/api/tasks/${taskId}/videos/${videoIndex}/size`, payload)
  return response.data
}

export async function addFissionVariant(taskId, videoIndex, segmentIndex) {
  const response = await backendClient.post(`/api/tasks/${taskId}/videos/${videoIndex}/segments/${segmentIndex}/variants`)
  return response.data
}

export async function deleteFissionVariant(taskId, videoIndex, segmentIndex, variantIndex) {
  const response = await backendClient.delete(
    `/api/tasks/${taskId}/videos/${videoIndex}/segments/${segmentIndex}/variants/${variantIndex}`
  )
  return response.data
}

export async function redoFissionVariant(taskId, videoIndex, segmentIndex, variantIndex) {
  const response = await backendClient.post(
    `/api/tasks/${taskId}/videos/${videoIndex}/segments/${segmentIndex}/variants/${variantIndex}/redo`
  )
  return response.data
}

export async function regroupVideo(taskId, videoIndex) {
  const response = await backendClient.post(`/api/tasks/${taskId}/videos/${videoIndex}/regroup`)
  return response.data
}

export async function downloadCurrentVideoRegroups(taskId, videoIndex) {
  const response = await backendClient.get(`/api/tasks/${taskId}/videos/${videoIndex}/regroup/download`, {
    responseType: 'blob'
  })
  return response
}

export async function downloadAllVideoRegroups(taskId) {
  const response = await backendClient.get(`/api/tasks/${taskId}/regroup/download`, {
    responseType: 'blob'
  })
  return response
}

export function openTaskStream(taskId, handlers) {
  const eventSource = new EventSource(`http://127.0.0.1:5000/api/tasks/${taskId}/stream`)

  eventSource.addEventListener('task_snapshot', (event) => {
    handlers.onSnapshot?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('video_result', (event) => {
    handlers.onVideoResult?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('video_processing_started', (event) => {
    handlers.onVideoProcessingStarted?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('segments_ready', (event) => {
    handlers.onSegmentsReady?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('segment_analysis', (event) => {
    handlers.onSegmentAnalysis?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('task_completed', (event) => {
    handlers.onCompleted?.(JSON.parse(event.data))
    eventSource.close()
  })

  eventSource.addEventListener('segment_generation_update', (event) => {
    handlers.onSegmentGenerationUpdate?.(JSON.parse(event.data))
  })

  eventSource.addEventListener('video_regrouped', (event) => {
    handlers.onVideoRegrouped?.(JSON.parse(event.data))
  })

  eventSource.onerror = (error) => {
    handlers.onError?.(error)
  }

  return eventSource
}
