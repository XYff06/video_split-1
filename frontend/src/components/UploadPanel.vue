<template>
  <section class="panel-section">
    <h2>一、上传区</h2>

    <div
      class="upload-drop-zone"
      :class="{ 'drag-active': isDragActive }"
      @dragenter.prevent="handleDragEnter"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
      @click="openFilePicker"
    >
      <input
        ref="hiddenFileInputElement"
        class="hidden-input"
        type="file"
        accept="video/*"
        multiple
        @change="handleFileInputChange"
      />
      <p>点击选择或拖拽视频到此处（支持多文件）</p>
    </div>

    <ul class="file-list">
      <li v-for="queueItem in previewFileList" :key="queueItem.fileUniqueKey" class="file-item">
        <span>{{ queueItem.fileObject.name }}</span>
        <button class="danger-button" @click="emit('remove-file', queueItem.fileUniqueKey)">删除</button>
      </li>
    </ul>

    <button
      v-if="uploadFileQueue.length > 3"
      class="secondary-button"
      @click="isQueueModalVisible = true"
    >
      展示更多
    </button>

    <div v-if="isQueueModalVisible" class="modal-overlay" @click.self="isQueueModalVisible = false">
      <div class="modal-panel">
        <h3>完整上传队列</h3>
        <ul class="file-list">
          <li v-for="queueItem in uploadFileQueue" :key="queueItem.fileUniqueKey" class="file-item">
            <span>{{ queueItem.fileObject.name }}</span>
            <button class="danger-button" @click="emit('remove-file', queueItem.fileUniqueKey)">删除</button>
          </li>
        </ul>
        <button class="secondary-button" @click="isQueueModalVisible = false">关闭</button>
      </div>
    </div>

    <button
      class="primary-button"
      :disabled="uploadFileQueue.length === 0 || isSubmitting"
      @click="emit('request-submit')"
    >
      {{ isSubmitting ? '处理中...' : '开始处理' }}
    </button>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  uploadFileQueue: {
    type: Array,
    required: true
  },
  isSubmitting: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['append-files', 'remove-file', 'request-submit'])

const hiddenFileInputElement = ref(null)
const isDragActive = ref(false)
const isQueueModalVisible = ref(false)

const previewFileList = computed(() => props.uploadFileQueue.slice(0, 3))

function openFilePicker() {
  hiddenFileInputElement.value?.click()
}

function handleFileInputChange(event) {
  const selectedFileList = event.target.files
  if (selectedFileList && selectedFileList.length > 0) {
    // 文件追加和过滤逻辑由父组件统一管理。
    // 这里仅负责把输入源中的 FileList 透传出去。
    emit('append-files', selectedFileList)
  }
  // 清空 input 值，确保同名文件可再次触发 change 事件。
  event.target.value = ''
}

function handleDragEnter() {
  isDragActive.value = true
}

function handleDragOver() {
  isDragActive.value = true
}

function handleDragLeave() {
  isDragActive.value = false
}

function handleDrop(event) {
  isDragActive.value = false
  const droppedFiles = event.dataTransfer?.files
  if (droppedFiles && droppedFiles.length > 0) {
    emit('append-files', droppedFiles)
  }
}
</script>
