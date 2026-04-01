<script setup>
import { computed, ref } from 'vue'
import FileQueueModal from './FileQueueModal.vue'

const props = defineProps({
  queue: Array,
  uploading: Boolean,
  errorMessage: String
})

const emit = defineEmits(['append-files', 'remove-file', 'submit'])

const isDragActive = ref(false)
const fileInputElement = ref(null)
const showModal = ref(false)

const topThreeFiles = computed(() => props.queue.slice(0, 3))

function openFilePicker() {
  fileInputElement.value?.click()
}

function onFileInputChange(event) {
  const selectedFiles = [...event.target.files]
  emit('append-files', selectedFiles)
  event.target.value = ''
}

function onDrop(event) {
  event.preventDefault()
  isDragActive.value = false
  emit('append-files', [...event.dataTransfer.files])
}
</script>

<template>
  <section class="panel-card">
    <h2>视频上传</h2>
    <div
      class="drop-zone"
      :class="{ 'drop-zone-active': isDragActive }"
      @click="openFilePicker"
      @dragover.prevent="isDragActive = true"
      @dragleave.prevent="isDragActive = false"
      @drop="onDrop"
    >
      <p>点击选择视频，或拖拽视频到这里</p>
      <input ref="fileInputElement" type="file" multiple accept="video/*" hidden @change="onFileInputChange" />
    </div>

    <div class="file-list">
      <div v-for="item in topThreeFiles" :key="item.uniqueKey" class="file-item">
        <div>
          <div class="file-name">{{ item.name }}</div>
          <div class="file-meta">{{ item.sizeText }} · 等待处理</div>
        </div>
        <button class="danger-button" @click="emit('remove-file', item.uniqueKey)">删除</button>
      </div>
    </div>

    <button v-if="queue.length > 3" class="ghost-button" @click="showModal = true">展示更多 ({{ queue.length }})</button>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <button class="primary-button" :disabled="queue.length === 0 || uploading" @click="emit('submit')">
      {{ uploading ? '处理中...' : '开始处理' }}
    </button>

    <FileQueueModal :visible="showModal" :files="queue" @close="showModal = false" @remove="emit('remove-file', $event)" />
  </section>
</template>
