<template>
  <section class="panel-card upload-panel">
    <div class="panel-header">
      <h2>上传区</h2>
      <p>支持拖拽或点击选择多个视频，自动过滤非视频并去重。</p>
    </div>

    <div
      class="drop-zone"
      :class="{ 'drag-active': isDragActive }"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDropFiles"
      @click="openNativeFileDialog"
    >
      <input
        ref="nativeFileInputReference"
        type="file"
        multiple
        accept="video/*"
        class="hidden-input"
        @change="handleNativeFileChange"
      />
      <p class="drop-zone-title">拖拽视频到此处，或点击选择文件</p>
      <p class="drop-zone-description">仅接收 video/* 文件，重复文件自动忽略。</p>
    </div>

    <div class="file-list-container">
      <h3>上传队列（{{ videoFileQueue.length }}）</h3>
      <p v-if="videoFileQueue.length === 0" class="empty-hint">当前暂无待处理文件。</p>

      <ul v-else class="file-card-list">
        <li v-for="videoFile in displayedFiles" :key="buildFileIdentity(videoFile)" class="file-card-item">
          <div>
            <p class="file-name">{{ videoFile.name }}</p>
            <p class="file-meta">{{ formatFileSize(videoFile.size) }} · {{ videoFile.type || '未知类型' }}</p>
          </div>
          <button class="danger-button" @click.stop="removeOneFile(videoFile)">删除</button>
        </li>
      </ul>

      <button
        v-if="videoFileQueue.length > visibleFileLimit"
        class="secondary-button"
        @click="isQueueModalVisible = true"
      >
        展示更多（{{ videoFileQueue.length - visibleFileLimit }}）
      </button>
    </div>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

    <button class="primary-button" :disabled="isSubmitDisabled" @click="$emit('submit-processing')">
      {{ isProcessing ? '处理中...' : '开始处理' }}
    </button>

    <QueueModal
      :visible="isQueueModalVisible"
      :video-file-queue="videoFileQueue"
      @close="isQueueModalVisible = false"
      @remove-file="removeOneFile"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import QueueModal from './QueueModal.vue'

const props = defineProps({
  videoFileQueue: { type: Array, required: true },
  isProcessing: { type: Boolean, required: true },
  errorMessage: { type: String, default: '' }
})

const emit = defineEmits(['update:video-file-queue', 'submit-processing'])

const isDragActive = ref(false)
const isQueueModalVisible = ref(false)
const nativeFileInputReference = ref(null)
const visibleFileLimit = 3

const displayedFiles = computed(() => props.videoFileQueue.slice(0, visibleFileLimit))
const isSubmitDisabled = computed(() => props.videoFileQueue.length === 0 || props.isProcessing)

function openNativeFileDialog() {
  nativeFileInputReference.value?.click()
}

function handleNativeFileChange(event) {
  const selectedFiles = Array.from(event.target.files || [])
  appendValidUniqueVideoFiles(selectedFiles)
  event.target.value = ''
}

function handleDragOver() {
  isDragActive.value = true
}

function handleDragLeave() {
  isDragActive.value = false
}

function handleDropFiles(event) {
  isDragActive.value = false
  const droppedFiles = Array.from(event.dataTransfer?.files || [])
  appendValidUniqueVideoFiles(droppedFiles)
}

function appendValidUniqueVideoFiles(candidateFiles) {
  // 这里先过滤成 video/* 文件，避免非视频进入队列。
  const onlyVideoFiles = candidateFiles.filter((candidateFile) => candidateFile.type.startsWith('video/'))

  // 使用“name + size + lastModified”作为去重键。
  // 这样做的原因是同名不同内容文件可区分，重复添加同一文件会被拦截。
  const existingIdentitySet = new Set(props.videoFileQueue.map((videoFile) => buildFileIdentity(videoFile)))
  const uniqueAppendedFiles = onlyVideoFiles.filter((candidateFile) => {
    const candidateIdentity = buildFileIdentity(candidateFile)
    if (existingIdentitySet.has(candidateIdentity)) return false
    existingIdentitySet.add(candidateIdentity)
    return true
  })

  const nextQueue = [...props.videoFileQueue, ...uniqueAppendedFiles]
  emit('update:video-file-queue', nextQueue)
}

function removeOneFile(targetFile) {
  const nextQueue = props.videoFileQueue.filter((videoFile) => buildFileIdentity(videoFile) !== buildFileIdentity(targetFile))
  emit('update:video-file-queue', nextQueue)
}

function buildFileIdentity(fileObject) {
  return `${fileObject.name}_${fileObject.size}_${fileObject.lastModified}`
}

function formatFileSize(fileSizeInBytes) {
  if (fileSizeInBytes < 1024 * 1024) {
    return `${(fileSizeInBytes / 1024).toFixed(1)} KB`
  }
  return `${(fileSizeInBytes / (1024 * 1024)).toFixed(2)} MB`
}
</script>
