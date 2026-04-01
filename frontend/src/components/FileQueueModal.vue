<script setup>
defineProps({
  visible: Boolean,
  files: Array
})

const emit = defineEmits(['close', 'remove'])
</script>

<template>
  <div v-if="visible" class="modal-mask" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h3>完整上传队列</h3>
        <button class="ghost-button" @click="emit('close')">关闭</button>
      </div>
      <div class="modal-body">
        <div v-for="file in files" :key="file.uniqueKey" class="file-item">
          <div>
            <div class="file-name">{{ file.name }}</div>
            <div class="file-meta">{{ file.sizeText }}</div>
          </div>
          <button class="danger-button" @click="emit('remove', file.uniqueKey)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>
