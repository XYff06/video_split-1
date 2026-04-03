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

    <PromptWorkspacePanel
      :current-video-result="currentVideoResult"
      :current-segment="currentSegment"
      :is-generating-current-video="isGeneratingCurrentVideo"
      :is-generating-all-videos="isGeneratingAllVideos"
      :action-error-message="fissionErrorMessage"
      :global-size="globalFissionSize"
      @generate-current-video="generateCurrentVideo"
      @generate-all-videos="generateAllVideos"
      @change-current-video-size="changeCurrentVideoSize"
      @change-global-size="changeGlobalSize"
      @reset-current-video-size="resetCurrentVideoSize"
    />

    <FissionRegroupPanel
      :video-results="videoResults"
      :is-working="isManagingFissionVariants"
      :error-message="variantActionError"
      @add-variant="addVariant"
      @delete-variant="deleteVariant"
      @redo-variant="redoVariant"
      @regroup-video="regroupCurrentVideo"
      @regroup-all-videos="regroupAllVideos"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import UploadPanel from './components/UploadPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import PromptWorkspacePanel from './components/PromptWorkspacePanel.vue'
import FissionRegroupPanel from './components/FissionRegroupPanel.vue'
import {
  addFissionVariant,
  createProcessingTask,
  deleteFissionVariant,
  generateAllVideoFissions,
  generateCurrentVideoFissions,
  openTaskStream,
  redoFissionVariant,
  regroupVideo,
  updateVideoFissionSize
} from './services/api'
import {
  composeSegmentGenerationPrompt,
  ensureSegmentLocalState,
  mergeVideoResultsWithLocalState
} from './utils/segmentPrompt'

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
const isGeneratingCurrentVideo = ref(false)
const isGeneratingAllVideos = ref(false)
const fissionErrorMessage = ref('')
const globalFissionSize = ref('1920*1080')
const isManagingFissionVariants = ref(false)
const variantActionError = ref('')

const allowedVideoExtensions = ['mp4', 'mov', 'mkv', 'avi', 'webm', 'm4v', 'wmv']

let eventSourceInstance = null

const currentVideoResult = computed(() => videoResults.value[selectedVideoIndex.value] ?? null)
const currentSegment = computed(() => {
  const activeVideo = currentVideoResult.value
  if (!activeVideo) return null
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
        videoResults.value = mergeVideoResultsWithLocalState(snapshot.videoResults, videoResults.value)
        ensureSelectedVideoExists()
      }
    },
    onVideoProcessingStarted(payload) {
      taskStatus.value = payload.taskStatus
      taskLogs.value = payload.taskLogs || []
      videoResults.value[payload.videoIndex] = payload.videoResult
      hydrateVideoResults()
      ensureSelectedVideoExists()
    },
    onSegmentsReady(payload) {
      taskStatus.value = payload.taskStatus
      taskLogs.value = payload.taskLogs || []

      const targetVideo = videoResults.value[payload.videoIndex]
      if (!targetVideo) return

      targetVideo.merged_segments = payload.mergedSegments
      targetVideo.status = 'processing'
      hydrateVideoResults()
    },
    onSegmentAnalysis(payload) {
      taskStatus.value = payload.taskStatus
      taskLogs.value = payload.taskLogs || []

      const targetVideo = videoResults.value[payload.videoIndex]
      if (!targetVideo || !Array.isArray(targetVideo.merged_segments)) return

      const previousSegment = targetVideo.merged_segments[payload.segmentIndex]
      const nextEditedPrompt = payload.segment.analysis?.prompt || payload.segment.edited_prompt || ''
      targetVideo.merged_segments[payload.segmentIndex] = {
        ...payload.segment,
        edited_prompt:
          typeof previousSegment?.edited_prompt === 'string' && previousSegment.edited_prompt.trim()
            ? previousSegment.edited_prompt
            : nextEditedPrompt,
        prompt_addons: previousSegment?.prompt_addons,
        fission_count: previousSegment?.fission_count ?? payload.segment.fission_count ?? 1
      }
      ensureSegmentLocalState(targetVideo.merged_segments[payload.segmentIndex])
    },
    onSegmentGenerationUpdate(payload) {
      taskLogs.value = payload.taskLogs || []
      const targetVideo = videoResults.value[payload.videoIndex]
      if (!targetVideo?.merged_segments) return
      const previousSegment = targetVideo.merged_segments[payload.segmentIndex]
      targetVideo.merged_segments[payload.segmentIndex] = {
        ...previousSegment,
        ...payload.segment
      }
      ensureSegmentLocalState(targetVideo.merged_segments[payload.segmentIndex])
    },
    onVideoRegrouped(payload) {
      taskLogs.value = payload.taskLogs || []
      const previousVideoResult = videoResults.value[payload.videoIndex]
      videoResults.value[payload.videoIndex] = mergeVideoResultsWithLocalState([payload.videoResult], [previousVideoResult])[0]
    },
    onVideoResult(payload) {
      completedVideos.value = payload.completedVideos
      totalVideos.value = payload.totalVideos
      taskStatus.value = payload.taskStatus
      taskLogs.value = payload.taskLogs || []
      const targetIndex = payload.completedVideos - 1
      const previousVideoResult = videoResults.value[targetIndex]
      videoResults.value[targetIndex] = mergeVideoResultsWithLocalState([payload.videoResult], [previousVideoResult])[0]
      videoResults.value[targetIndex]?.merged_segments?.forEach((segment) => ensureSegmentLocalState(segment))

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

function hydrateVideoResults() {
  videoResults.value.forEach((videoResult) => {
    videoResult?.merged_segments?.forEach((segment) => {
      ensureSegmentLocalState(segment)
    })
  })
}

function buildVideoGenerationPayload(videoResult, videoIndex) {
  const useGlobalSize = videoResult?.use_global_fission_size !== false
  const segments = (videoResult?.merged_segments || []).map((segment, segmentIndex) => {
    ensureSegmentLocalState(segment)
    return {
      segmentIndex,
      fissionCount: segment.fission_count,
      generationPrompt: composeSegmentGenerationPrompt(segment)
    }
  })

  return {
    videoIndex,
    videoSize: useGlobalSize ? null : (videoResult?.fission_size || globalFissionSize.value),
    segments
  }
}

async function generateCurrentVideo() {
  if (!taskId.value || !currentVideoResult.value) return

  fissionErrorMessage.value = ''
  isGeneratingCurrentVideo.value = true

  try {
    const payload = buildVideoGenerationPayload(currentVideoResult.value, selectedVideoIndex.value)
    const response = await generateCurrentVideoFissions(taskId.value, payload)
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    fissionErrorMessage.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '当前视频裂变失败，请稍后重试。'
  } finally {
    isGeneratingCurrentVideo.value = false
  }
}

async function generateAllVideos() {
  if (!taskId.value || !videoResults.value.length) return

  fissionErrorMessage.value = ''
  isGeneratingAllVideos.value = true

  try {
    const payload = {
      globalSize: globalFissionSize.value,
      videos: videoResults.value.map((videoResult, videoIndex) => buildVideoGenerationPayload(videoResult, videoIndex))
    }
    const response = await generateAllVideoFissions(taskId.value, payload)
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    fissionErrorMessage.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '全部视频裂变失败，请稍后重试。'
  } finally {
    isGeneratingAllVideos.value = false
  }
}

async function changeCurrentVideoSize(size) {
  if (!taskId.value || selectedVideoIndex.value < 0 || !currentVideoResult.value) return
  variantActionError.value = ''
  currentVideoResult.value.fission_size = size
  currentVideoResult.value.use_global_fission_size = false

  try {
    const response = await updateVideoFissionSize(taskId.value, selectedVideoIndex.value, {
      size,
      useGlobal: false
    })
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '更新当前视频 size 失败。'
  }
}

async function resetCurrentVideoSize() {
  if (!taskId.value || selectedVideoIndex.value < 0 || !currentVideoResult.value) return
  variantActionError.value = ''
  currentVideoResult.value.fission_size = null
  currentVideoResult.value.use_global_fission_size = true

  try {
    const response = await updateVideoFissionSize(taskId.value, selectedVideoIndex.value, {
      size: null,
      useGlobal: true
    })
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '重置当前视频为跟随全局 Size 失败。'
  }
}

function changeGlobalSize(size) {
  globalFissionSize.value = size
}

async function addVariant(videoIndex, segmentIndex) {
  if (!taskId.value) return
  variantActionError.value = ''
  isManagingFissionVariants.value = true

  try {
    const response = await addFissionVariant(taskId.value, videoIndex, segmentIndex)
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '增加裂变视频失败。'
  } finally {
    isManagingFissionVariants.value = false
  }
}

async function deleteVariant(videoIndex, segmentIndex, variantIndex) {
  if (!taskId.value) return
  variantActionError.value = ''
  isManagingFissionVariants.value = true

  try {
    const response = await deleteFissionVariant(taskId.value, videoIndex, segmentIndex, variantIndex)
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '删除裂变视频失败。'
  } finally {
    isManagingFissionVariants.value = false
  }
}

async function redoVariant(videoIndex, segmentIndex, variantIndex) {
  if (!taskId.value) return
  variantActionError.value = ''
  isManagingFissionVariants.value = true

  try {
    const response = await redoFissionVariant(taskId.value, videoIndex, segmentIndex, variantIndex)
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '重做裂变视频失败。'
  } finally {
    isManagingFissionVariants.value = false
  }
}

async function regroupCurrentVideo(videoIndex) {
  if (!taskId.value || videoIndex < 0) return
  variantActionError.value = ''
  isManagingFissionVariants.value = true

  try {
    const response = await regroupVideo(taskId.value, videoIndex)
    videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
    taskLogs.value = response.taskLogs || taskLogs.value
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '重新重组失败。'
  } finally {
    isManagingFissionVariants.value = false
  }
}

async function regroupAllVideos() {
  if (!taskId.value || !videoResults.value.length) return
  variantActionError.value = ''
  isManagingFissionVariants.value = true

  try {
    for (let videoIndex = 0; videoIndex < videoResults.value.length; videoIndex += 1) {
      const response = await regroupVideo(taskId.value, videoIndex)
      videoResults.value = mergeVideoResultsWithLocalState(response.videoResults, videoResults.value)
      taskLogs.value = response.taskLogs || taskLogs.value
    }
  } catch (error) {
    variantActionError.value =
      error?.response?.data?.error ||
      error?.response?.data?.message ||
      error?.message ||
      '重组全部视频失败。'
  } finally {
    isManagingFissionVariants.value = false
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
