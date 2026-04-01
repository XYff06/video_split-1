const BACKEND_BASE_URL = 'http://localhost:5000'

export async function submitVideosForProcessing(videoFiles) {
  const formData = new FormData()

  // 这里把当前队列中的所有视频追加到 FormData。
  // 这样做的原因是后端接口按 files 多文件字段接收。
  // 最终后端会一次拿到全部视频并逐个处理。
  videoFiles.forEach((videoFile) => {
    formData.append('files', videoFile)
  })

  const response = await fetch(`${BACKEND_BASE_URL}/api/process-videos`, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.message || '后端处理失败，请稍后重试。')
  }

  return response.json()
}

export function resolveMediaUrl(relativeOrAbsoluteUrl) {
  if (!relativeOrAbsoluteUrl) return ''
  if (relativeOrAbsoluteUrl.startsWith('http')) return relativeOrAbsoluteUrl
  return `${BACKEND_BASE_URL}${relativeOrAbsoluteUrl}`
}
