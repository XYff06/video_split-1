<template>
  <section class="panel panel-upload">
    <h2>视频上传</h2>
    <p class="panel-subtitle">支持多文件上传、拖拽、去重，提交后自动开启实时结果流。</p>

    <div
      class="drop-zone"
      :class="{ active: isDragActive }"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
      @click="openFilePicker"
    >
      <p class="drop-zone-title">点击选择视频或拖拽到此处</p>
      <p class="hint-text">仅接收 video/*，会自动忽略非视频文件</p>
      <input ref="fileInputRef" type="file" multiple accept="video/*" class="hidden" @change="onFileChange" />
    </div>

    <UploadFileList :files="visibleFiles" @remove="removeFile" />

    <button v-if="files.length > 3" class="ghost-button queue-more-button" @click="isModalVisible = true">
      展示更多（{{ files.length - 3 }}）
    </button>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <button class="primary-button" :disabled="isSubmitDisabled" @click="submit">
      {{ processingStatus === 'processing' ? `处理中 ${completedVideos}/${totalVideos}` : '开始处理' }}
    </button>

    <FileQueueModal
      v-if="isModalVisible"
      :files="files"
      @close="isModalVisible = false"
      @remove="removeFile"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import UploadFileList from './UploadFileList.vue'
import FileQueueModal from './FileQueueModal.vue'

const props = defineProps({
  files: { type: Array, default: () => [] },
  processingStatus: { type: String, default: 'idle' },
  completedVideos: { type: Number, default: 0 },
  totalVideos: { type: Number, default: 0 },
  errorMessage: { type: String, default: '' }
})

const emit = defineEmits(['append-files', 'remove-file', 'submit'])

const fileInputRef = ref(null)
const isDragActive = ref(false)
const isModalVisible = ref(false)

const visibleFiles = computed(() => props.files.slice(0, 3))
const isSubmitDisabled = computed(() => props.files.length === 0 || props.processingStatus === 'processing')

function openFilePicker() {
  fileInputRef.value?.click()
}

function onDragOver() {
  isDragActive.value = true
}

function onDragLeave() {
  isDragActive.value = false
}

function onDrop(event) {
  isDragActive.value = false
  emit('append-files', Array.from(event.dataTransfer.files))
}

function onFileChange(event) {
  emit('append-files', Array.from(event.target.files))
  event.target.value = ''
}

function removeFile(uniqueKey) {
  emit('remove-file', uniqueKey)
}

function submit() {
  emit('submit')
}
</script>

