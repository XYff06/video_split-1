<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal-card">
      <header class="modal-header">
        <h3>完整上传队列</h3>
        <button class="ghost-button" @click="$emit('close')">关闭</button>
      </header>
      <div class="modal-body">
        <UploadFileList :files="files" @remove="$emit('remove', $event)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import UploadFileList from './UploadFileList.vue'
defineProps({ files: { type: Array, default: () => [] } })
defineEmits(['close', 'remove'])
</script>
