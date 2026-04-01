<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import UploadPanel from './components/UploadPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import { createVideoTask, fetchTaskStatus } from './services/api'

const queuedVideoFiles = ref([])
const isSubmittingTask = ref(false)
const uploadErrorMessage = ref('')
const currentTaskId = ref('')
const polledTaskData = ref(null)
const selectedVideoId = ref('')
const selectedSegmentIndex = ref(0)
let pollTimer = null

const availableVideos = computed(() => polledTaskData.value?.videos || [])

function toReadableSize(fileSize) {
  return `${(fileSize / 1024 / 1024).toFixed(2)} MB`
}

function appendFiles(newFiles) {
  // What: only keep video files and append (not overwrite) to queue.
  // Why: requirement asks drag/drop + click selections to keep adding files.
  // Result: user can build a batch list over multiple selection operations.
  const onlyVideoFiles = newFiles.filter((file) => file.type.startsWith('video/'))
  for (const file of onlyVideoFiles) {
    const uniqueKey = `${file.name}-${file.size}-${file.lastModified}`
    const isDuplicated = queuedVideoFiles.value.some((item) => item.uniqueKey === uniqueKey)
    if (!isDuplicated) {
      queuedVideoFiles.value.push({ ...file, uniqueKey, sizeText: toReadableSize(file.size) })
    }
  }
}

function removeFile(uniqueKey) {
  queuedVideoFiles.value = queuedVideoFiles.value.filter((item) => item.uniqueKey !== uniqueKey)
}

function keepStableVideoSelection(taskSnapshot) {
  const ids = (taskSnapshot?.videos || []).map((video) => video.videoId)
  if (!selectedVideoId.value && ids.length > 0) {
    selectedVideoId.value = ids[0]
    selectedSegmentIndex.value = 0
    return
  }
  if (selectedVideoId.value && !ids.includes(selectedVideoId.value)) {
    selectedVideoId.value = ids[0] || ''
    selectedSegmentIndex.value = 0
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function startPollingTask(taskId) {
  stopPolling()

  async function pollOnce() {
    const snapshot = await fetchTaskStatus(taskId)
    polledTaskData.value = snapshot
    keepStableVideoSelection(snapshot)

    const isFinished = ['finished', 'completed'].includes(snapshot.overallStatus)
    if (isFinished) {
      stopPolling()
    }
  }

  await pollOnce()
  pollTimer = setInterval(async () => {
    try {
      await pollOnce()
    } catch (error) {
      uploadErrorMessage.value = `轮询失败：${error.message}`
      stopPolling()
    }
  }, 1000)
}

async function submitTask() {
  if (queuedVideoFiles.value.length === 0 || isSubmittingTask.value) {
    return
  }

  uploadErrorMessage.value = ''
  isSubmittingTask.value = true

  try {
    const response = await createVideoTask(queuedVideoFiles.value)
    currentTaskId.value = response.taskId
    await startPollingTask(response.taskId)
  } catch (error) {
    uploadErrorMessage.value = `提交失败：${error.response?.data?.message || error.message}`
  } finally {
    isSubmittingTask.value = false
  }
}

function selectVideo(videoId) {
  selectedVideoId.value = videoId
  selectedSegmentIndex.value = 0
}

function cycleVideo(step) {
  if (!availableVideos.value.length) return
  const currentIndex = availableVideos.value.findIndex((video) => video.videoId === selectedVideoId.value)
  const targetIndex = (currentIndex + step + availableVideos.value.length) % availableVideos.value.length
  selectedVideoId.value = availableVideos.value[targetIndex].videoId
  selectedSegmentIndex.value = 0
}

function cycleSegment(step) {
  const selectedVideo = availableVideos.value.find((video) => video.videoId === selectedVideoId.value)
  const segments = selectedVideo?.result?.finalBusinessSegments || []
  if (!segments.length) return
  selectedSegmentIndex.value = (selectedSegmentIndex.value + step + segments.length) % segments.length
}

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <main class="page-wrapper">
    <header class="page-header">
      <h1>视频上传 → 后端分割 → 前端预览 Demo</h1>
      <p>Task ID: {{ currentTaskId || '尚未创建' }}</p>
    </header>

    <div class="main-grid">
      <UploadPanel
        :queue="queuedVideoFiles"
        :uploading="isSubmittingTask"
        :error-message="uploadErrorMessage"
        @append-files="appendFiles"
        @remove-file="removeFile"
        @submit="submitTask"
      />

      <ResultPanel
        :task="polledTaskData"
        :selected-video-id="selectedVideoId"
        :selected-segment-index="selectedSegmentIndex"
        @select-video="selectVideo"
        @prev-video="cycleVideo(-1)"
        @next-video="cycleVideo(1)"
        @prev-segment="cycleSegment(-1)"
        @next-segment="cycleSegment(1)"
      />
    </div>
  </main>
</template>
