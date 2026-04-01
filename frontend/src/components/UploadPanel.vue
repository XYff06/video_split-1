<template>
  <section class="upload-panel">
    <h2>视频上传区</h2>

    <div
      class="upload-drop-zone"
      :class="{ 'is-drag-over': isDragOverActive }"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDropFiles"
      @click="openFilePicker"
    >
      <p>点击选择视频，或拖拽视频到此区域</p>
      <p class="hint-text">支持多选，自动过滤非视频文件，自动去重并追加到队列</p>
      <input
        ref="videoFileInputReference"
        type="file"
        accept="video/*"
        multiple
        class="hidden-file-input"
        @change="onFileInputChange"
      />
    </div>

    <ul class="queue-preview-list">
      <li v-for="queuedItem in visibleQueuedVideoFiles" :key="queuedItem.deduplicationKey" class="queue-row">
        <span>{{ queuedItem.fileName }}</span>
        <button @click="$emit('remove-file', queuedItem.deduplicationKey)">删除</button>
      </li>
    </ul>

    <button v-if="hasMoreThanVisibleLimit" @click="$emit('show-full-queue')">展示更多</button>

    <button :disabled="isProcessButtonDisabled" @click="$emit('process-all')">
      {{ isProcessing ? '处理中' : '开始处理' }}
    </button>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  visibleQueuedVideoFiles: { type: Array, required: true },
  hasMoreThanVisibleLimit: { type: Boolean, required: true },
  isProcessing: { type: Boolean, required: true },
  errorMessage: { type: String, default: '' },
  hasQueuedFiles: { type: Boolean, required: true }
})

const emit = defineEmits(['files-added', 'remove-file', 'show-full-queue', 'process-all'])

const isDragOverActive = ref(false)
const videoFileInputReference = ref(null)

const isProcessButtonDisabled = computed(() => props.isProcessing || !props.hasQueuedFiles)

function openFilePicker() {
  videoFileInputReference.value?.click()
}

function onFileInputChange(event) {
  emit('files-added', event.target.files)
  event.target.value = ''
}

function onDragOver() {
  isDragOverActive.value = true
}

function onDragLeave() {
  isDragOverActive.value = false
}

function onDropFiles(event) {
  isDragOverActive.value = false
  emit('files-added', event.dataTransfer.files)
}
</script>
