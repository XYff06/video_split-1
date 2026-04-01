<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-container">
      <header class="modal-header">
        <h3>完整上传队列</h3>
        <button class="icon-close-button" @click="$emit('close')">×</button>
      </header>

      <div class="modal-scroll-content">
        <p v-if="videoFileQueue.length === 0" class="empty-hint">暂无文件。</p>
        <ul v-else class="file-card-list">
          <li v-for="videoFile in videoFileQueue" :key="buildFileIdentity(videoFile)" class="file-card-item">
            <div>
              <p class="file-name">{{ videoFile.name }}</p>
              <p class="file-meta">{{ formatFileSize(videoFile.size) }} · {{ videoFile.type || '未知类型' }}</p>
            </div>
            <button class="danger-button" @click="$emit('remove-file', videoFile)">删除</button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, required: true },
  videoFileQueue: { type: Array, required: true }
})

defineEmits(['close', 'remove-file'])

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
