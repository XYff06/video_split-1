<template>
  <div class="log-panels">
    <div>
      <h4>当前视频日志</h4>
      <div class="log-list">
        <div v-for="(item, idx) in currentVideoLogs" :key="`video-${idx}`" class="log-item" :class="item.level">
          <span>[{{ item.level }}]</span> {{ item.timestamp }} - {{ item.message }}
        </div>
      </div>
    </div>
    <div>
      <h4>任务总日志</h4>
      <div class="log-list">
        <div v-for="(item, idx) in taskLogs" :key="`task-${idx}`" class="log-item" :class="item.level">
          <span>[{{ item.level }}]</span>
          {{ item.timestamp }}
          <template v-if="item.video_name"> - {{ item.video_name }}</template>
          - {{ item.message }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  currentVideoLogs: { type: Array, default: () => [] },
  taskLogs: { type: Array, default: () => [] }
})
</script>
