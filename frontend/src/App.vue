<template>
  <main class="application-container">
    <h1>视频上传 → 后端分割 → 前端预览 Demo</h1>

    <UploadPanel
      :upload-file-queue="uploadFileQueue"
      :is-submitting="isSubmitting"
      @append-files="appendFilesToQueue"
      @remove-file="removeFileFromQueue"
      @request-submit="submitVideosForProcessing"
    />

    <section class="status-section" v-if="requestErrorMessage">
      <p class="error-text">{{ requestErrorMessage }}</p>
    </section>

    <ResultViewer
      v-if="processedVideoList.length > 0"
      :processed-video-list="processedVideoList"
      :backend-base-url="backendBaseUrl"
    />
  </main>
</template>

<script setup>
import { ref } from 'vue'
import UploadPanel from './components/UploadPanel.vue'
import ResultViewer from './components/ResultViewer.vue'

const backendBaseUrl = 'http://localhost:5000'
const uploadFileQueue = ref([])
const isSubmitting = ref(false)
const requestErrorMessage = ref('')
const processedVideoList = ref([])

/**
 * 用文件可稳定识别的特征构建唯一键，避免重复加入队列。
 */
function buildFileDeduplicationKey(selectedFile) {
  return [selectedFile.name, selectedFile.size, selectedFile.lastModified, selectedFile.type].join('__')
}

/**
 * 将新文件追加到已有队列并去重；非视频文件会被过滤掉。
 */
function appendFilesToQueue(fileListFromInputOrDrop) {
  const incomingFileArray = Array.from(fileListFromInputOrDrop)
  const existingFileKeySet = new Set(uploadFileQueue.value.map((queueItem) => queueItem.fileUniqueKey))

  const appendedQueueItems = incomingFileArray
    .filter((candidateFile) => candidateFile.type.startsWith('video/'))
    .map((videoFile) => ({
      fileObject: videoFile,
      fileUniqueKey: buildFileDeduplicationKey(videoFile)
    }))
    .filter((candidateQueueItem) => !existingFileKeySet.has(candidateQueueItem.fileUniqueKey))

  uploadFileQueue.value = [...uploadFileQueue.value, ...appendedQueueItems]
}

/**
 * 根据唯一键删除单个文件。
 */
function removeFileFromQueue(fileUniqueKey) {
  uploadFileQueue.value = uploadFileQueue.value.filter((queueItem) => queueItem.fileUniqueKey !== fileUniqueKey)
}

/**
 * 将当前队列全部提交给后端处理，并在成功后展示结果。
 */
async function submitVideosForProcessing() {
  if (uploadFileQueue.value.length === 0 || isSubmitting.value) {
    return
  }

  isSubmitting.value = true
  requestErrorMessage.value = ''
  processedVideoList.value = []

  const uploadFormData = new FormData()
  uploadFileQueue.value.forEach((queueItem) => {
    uploadFormData.append('videos', queueItem.fileObject)
  })

  try {
    const response = await fetch(`${backendBaseUrl}/api/process-videos`, {
      method: 'POST',
      body: uploadFormData
    })

    const responseBody = await response.json()

    if (!response.ok || !responseBody.success) {
      throw new Error(responseBody.error || '处理失败，请稍后重试。')
    }

    processedVideoList.value = responseBody.videos
  } catch (requestError) {
    requestErrorMessage.value = requestError.message
  } finally {
    isSubmitting.value = false
  }
}
</script>
