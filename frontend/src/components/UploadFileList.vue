<template>
  <div class="file-list">
    <div v-for="file in files" :key="file.uniqueKey" class="file-item-card">
      <div>
        <p class="file-name">{{ file.name }}</p>
        <p class="file-meta">{{ formatSize(file.size) }} · {{ file.type || 'unknown' }}</p>
      </div>
      <button class="danger-button" @click="$emit('remove', file.uniqueKey)">删除</button>
    </div>
  </div>
</template>

<script setup>
defineProps({ files: { type: Array, default: () => [] } })
defineEmits(['remove'])

function formatSize(size) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}
</script>
