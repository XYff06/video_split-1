<template>
  <div class="page">
    <main class="main-grid">
      <UploadPanel
        :files="uploadFileQueue"
        :processing-status="taskStatus"
        :completed-videos="completedVideos"
        :total-videos="totalVideos"
        :error-message="uploadErrorMessage"
        @append-files="appendFiles"
        @remove-file="removeFileFromQueue"
        @submit="startProcessing"
      />

      <ResultPanel
        :status-text="resultStatusText"
        :video-results="videoResults"
        :selected-video-index="selectedVideoIndex"
        :current-video-page="currentVideoPage"
        :current-video-result="currentVideoResult"
        :current-segment="currentSegment"
        :current-video-logs="currentVideoLogs"
        :task-logs="taskLogs"
        :can-previous-segment="canPreviousSegment"
        :can-next-segment="canNextSegment"
        @select-video="selectVideo"
        @change-video-page="setVideoPage"
        @prev-segment="goToPreviousSegment"
        @next-segment="goToNextSegment"
      />
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import UploadPanel from './components/UploadPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import { createProcessingTask, openTaskStream } from './services/api'

const uploadFileQueue = ref([])
const taskId = ref('')
const taskStatus = ref('idle')
const completedVideos = ref(0)
const totalVideos = ref(0)
const videoResults = ref([])
const selectedVideoIndex = ref(-1)
const selectedSegmentIndex = ref(0)
const uploadErrorMessage = ref('')
const taskLogs = ref([])
const currentVideoPage = ref(0)

const allowedVideoExtensions = ['mp4', 'mov', 'mkv', 'avi', 'webm', 'm4v', 'wmv']

let eventSourceInstance = null

const currentVideoResult = computed(() => videoResults.value[selectedVideoIndex.value] ?? null)
const currentSegment = computed(() => {
  const activeVideo = currentVideoResult.value
  if (!activeVideo || activeVideo.status !== 'success') return null
  return activeVideo.merged_segments[selectedSegmentIndex.value] ?? null
})
const currentVideoLogs = computed(() => currentVideoResult.value?.logs ?? [])
const canPreviousSegment = computed(() => selectedSegmentIndex.value > 0)
const canNextSegment = computed(() => {
  const totalSegments = currentVideoResult.value?.merged_segments?.length ?? 0
  return selectedSegmentIndex.value < totalSegments - 1
})
const resultStatusText = computed(() => {
  if (taskStatus.value === 'processing') {
    return `正在持续接收处理结果，已完成 ${completedVideos.value} / ${totalVideos.value}`
  }

  if (taskStatus.value === 'completed') {
    return `处理完成，共 ${totalVideos.value} 个视频。`
  }

  return '尚未开始处理。上传后点击“开始处理”，结果会实时出现在右侧。'
})

function buildFileUniqueKey(file) {
  return `${file.name}__${file.size}__${file.lastModified}`
}

function isVideoFile(file) {
  const fileExtension = file.name?.split('.').pop()?.toLowerCase() || ''
  return file.type?.startsWith('video/') || allowedVideoExtensions.includes(fileExtension)
}

function appendFiles(candidateFiles) {
  const acceptedFiles = candidateFiles.filter((file) => isVideoFile(file))
  const existingKeys = new Set(uploadFileQueue.value.map((item) => item.uniqueKey))

  acceptedFiles.forEach((file) => {
    const uniqueKey = buildFileUniqueKey(file)
    if (!existingKeys.has(uniqueKey)) {
      uploadFileQueue.value.push({
        uniqueKey,
        rawFile: file,
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified
      })
      existingKeys.add(uniqueKey)
    }
  })

  if (acceptedFiles.length === 0 && candidateFiles.length > 0) {
    uploadErrorMessage.value = '当前选择的文件里没有可用的视频文件。'
  } else if (acceptedFiles.length !== candidateFiles.length) {
    uploadErrorMessage.value = '检测到非视频文件，已自动忽略。'
  } else {
    uploadErrorMessage.value = ''
  }
}

function removeFileFromQueue(uniqueKey) {
  uploadFileQueue.value = uploadFileQueue.value.filter((item) => item.uniqueKey !== uniqueKey)
}

async function startProcessing() {
  if (!uploadFileQueue.value.length || taskStatus.value === 'processing') return

  uploadErrorMessage.value = ''
  taskStatus.value = 'processing'
  videoResults.value = []
  taskLogs.value = []
  selectedVideoIndex.value = -1
  selectedSegmentIndex.value = 0
  currentVideoPage.value = 0

  try {
    const response = await createProcessingTask(uploadFileQueue.value.map((item) => item.rawFile))
    taskId.value = response.taskId
    totalVideos.value = response.totalVideos
    completedVideos.value = 0
    connectSseStream(response.taskId)
  } catch (error) {
    taskStatus.value = 'idle'
    uploadErrorMessage.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '创建任务失败，请检查后端服务。'
  }
}

function connectSseStream(newTaskId) {
  eventSourceInstance?.close()

  eventSourceInstance = openTaskStream(newTaskId, {
    onSnapshot(snapshot) {
      taskStatus.value = snapshot.taskStatus
      completedVideos.value = snapshot.completedVideos
      totalVideos.value = snapshot.totalVideos
      taskLogs.value = snapshot.taskLogs || []
      if (Array.isArray(snapshot.videoResults) && snapshot.videoResults.length) {
        videoResults.value = snapshot.videoResults
        ensureSelectedVideoExists()
      }
    },
    onVideoResult(payload) {
      completedVideos.value = payload.completedVideos
      totalVideos.value = payload.totalVideos
      taskStatus.value = payload.taskStatus
      taskLogs.value = payload.taskLogs || []
      videoResults.value.push(payload.videoResult)

      if (selectedVideoIndex.value === -1) {
        selectedVideoIndex.value = 0
        selectedSegmentIndex.value = 0
        currentVideoPage.value = 0
      }
    },
    onCompleted(payload) {
      taskStatus.value = payload.taskStatus
      completedVideos.value = payload.completedVideos
      totalVideos.value = payload.totalVideos
      taskLogs.value = payload.taskLogs || []
    },
    onError() {
      uploadErrorMessage.value = 'SSE 连接已断开，请刷新页面后重试。'
      eventSourceInstance?.close()
    }
  })
}

function ensureSelectedVideoExists() {
  if (!videoResults.value.length) {
    selectedVideoIndex.value = -1
    return
  }

  if (selectedVideoIndex.value < 0 || selectedVideoIndex.value >= videoResults.value.length) {
    selectedVideoIndex.value = 0
    selectedSegmentIndex.value = 0
  }
}

function selectVideo(index) {
  selectedVideoIndex.value = index
  selectedSegmentIndex.value = 0
}

function setVideoPage(page) {
  currentVideoPage.value = page
}

function goToPreviousSegment() {
  if (canPreviousSegment.value) selectedSegmentIndex.value -= 1
}

function goToNextSegment() {
  if (canNextSegment.value) selectedSegmentIndex.value += 1
}

onBeforeUnmount(() => {
  eventSourceInstance?.close()
})
</script>

