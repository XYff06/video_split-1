<template>
  <div class="file-list">
    <div v-for="file in files" :key="file.uniqueKey" class="file-item-card">
      <div>
        <p class="file-name">{{ file.name || '未命名文件' }}</p>
        <p class="file-meta">{{ formatSize(file.size) }} · {{ formatType(file.type) }}</p>
      </div>
      <button class="danger-button" @click="$emit('remove', file.uniqueKey)">删除</button>
    </div>
  </div>
</template>

<script setup>
defineProps({ files: { type: Array, default: () => [] } })
defineEmits(['remove'])

function formatSize(size) {
  const numericSize = Number(size)

  if (!Number.isFinite(numericSize) || numericSize < 0) {
    return '--'
  }

  if (numericSize < 1024) return `${numericSize} B`
  if (numericSize < 1024 * 1024) return `${(numericSize / 1024).toFixed(2)} KB`
  return `${(numericSize / (1024 * 1024)).toFixed(2)} MB`
}

function formatType(type) {
  return type || '视频文件'
}
</script>

