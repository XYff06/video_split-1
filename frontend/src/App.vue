<template>
  <div class="application-shell">
    <header class="page-header">
      <h1>视频上传 → 后端分割 → 前端结果预览 Demo</h1>
      <p>支持多视频上传、真实场景切分、随机合法分组与片段预览。</p>
    </header>

    <main class="content-layout">
      <UploadPanel
        :video-file-queue="videoFileQueue"
        :is-processing="isProcessing"
        :error-message="requestErrorMessage"
        @update:video-file-queue="updateVideoFileQueue"
        @submit-processing="handleSubmitProcessing"
      />

      <ResultPanel
        :is-processing="isProcessing"
        :successful-videos="successfulVideos"
        :failed-videos="failedVideos"
        :processing-logs="processingLogs"
      />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import UploadPanel from './components/UploadPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import { submitVideosForProcessing } from './api/videoApi'

// 上传队列，存放用户当前准备提交的 File 列表。
const videoFileQueue = ref([])

// 处理中标记用于控制按钮禁用态、防止重复提交。
const isProcessing = ref(false)

// 接口错误信息用于在上传区显式提示失败原因。
const requestErrorMessage = ref('')

// 后端返回的成功视频结果。
const successfulVideos = ref([])

// 后端返回的失败视频结果。
const failedVideos = ref([])

// 后端返回的统一处理日志。
const processingLogs = ref([])

function updateVideoFileQueue(nextQueue) {
  videoFileQueue.value = nextQueue
}

async function handleSubmitProcessing() {
  requestErrorMessage.value = ''
  if (videoFileQueue.value.length === 0 || isProcessing.value) {
    return
  }

  try {
    isProcessing.value = true
    const responseData = await submitVideosForProcessing(videoFileQueue.value)

    successfulVideos.value = responseData.successful_videos || []
    failedVideos.value = responseData.failed_videos || []
    processingLogs.value = responseData.processing_logs || []
  } catch (requestError) {
    requestErrorMessage.value = requestError.message || '处理失败，请检查网络或后端日志。'
  } finally {
    isProcessing.value = false
  }
}
</script>
