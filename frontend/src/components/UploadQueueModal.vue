<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-container">
      <h3>完整上传队列</h3>
      <ul class="queue-list">
        <li v-for="queuedItem in queuedVideoFiles" :key="queuedItem.deduplicationKey" class="queue-row">
          <span>{{ queuedItem.fileName }}</span>
          <button @click="$emit('remove', queuedItem.deduplicationKey)">删除</button>
        </li>
      </ul>
      <button class="close-button" @click="$emit('close')">关闭</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  queuedVideoFiles: {
    type: Array,
    required: true
  }
})
</script>
