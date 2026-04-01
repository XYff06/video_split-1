<template>
  <main class="application-layout">
    <section class="left-column">
      <UploadPanel
        :visible-queued-video-files="visibleQueuedVideoFiles"
        :has-more-than-visible-limit="hasMoreThanVisibleLimit"
        :is-processing="isProcessing"
        :error-message="errorMessage"
        :has-queued-files="queuedVideoFiles.length > 0"
        @files-added="appendFilesToQueue"
        @remove-file="removeFileFromQueue"
        @show-full-queue="isQueueModalOpen = true"
        @process-all="processAllVideos"
      />
    </section>

    <section class="right-column">
      <ResultPanel
        :successful-videos="successfulVideos"
        :failed-videos="failedVideos"
        :process-logs="processLogs"
      />
    </section>

    <UploadQueueModal
      v-if="isQueueModalOpen"
      :queued-video-files="queuedVideoFiles"
      @close="isQueueModalOpen = false"
      @remove="removeFileFromQueue"
    />
  </main>
</template>

<script setup>
import { ref } from 'vue'
import ResultPanel from './components/ResultPanel.vue'
import UploadPanel from './components/UploadPanel.vue'
import UploadQueueModal from './components/UploadQueueModal.vue'
import { useVideoUploadQueue } from './composables/useVideoUploadQueue'
import { sendVideosForProcessing } from './services/videoProcessingApi'

const { queuedVideoFiles, visibleQueuedVideoFiles, hasMoreThanVisibleLimit, appendFilesToQueue, removeFileFromQueue } =
  useVideoUploadQueue()

const isQueueModalOpen = ref(false)
const isProcessing = ref(false)
const errorMessage = ref('')
const successfulVideos = ref([])
const failedVideos = ref([])
const processLogs = ref([])

async function processAllVideos() {
  if (isProcessing.value || queuedVideoFiles.value.length === 0) {
    return
  }

  try {
    isProcessing.value = true
    errorMessage.value = ''

    const responseData = await sendVideosForProcessing(queuedVideoFiles.value)
    successfulVideos.value = responseData.successful_videos || []
    failedVideos.value = responseData.failed_videos || []
    processLogs.value = responseData.process_logs || []
  } catch (requestError) {
    errorMessage.value = requestError.message || '处理失败，请检查后端日志。'
  } finally {
    isProcessing.value = false
  }
}
</script>
