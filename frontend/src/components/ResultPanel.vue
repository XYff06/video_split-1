<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: Object,
  selectedVideoId: String,
  selectedSegmentIndex: Number
})

const emit = defineEmits(['select-video', 'next-video', 'prev-video', 'next-segment', 'prev-segment'])

const selectedVideo = computed(() => props.task?.videos?.find((video) => video.videoId === props.selectedVideoId) || null)
const finalSegments = computed(() => selectedVideo.value?.result?.finalBusinessSegments || [])
const selectedSegment = computed(() => finalSegments.value[props.selectedSegmentIndex] || null)

function statusText(status) {
  if (status === 'processing') return '处理中'
  if (status === 'success') return '成功'
  if (status === 'failed') return '失败'
  return '等待中'
}
</script>

<template>
  <section class="panel-card">
    <div class="result-header">
      <h2>处理结果</h2>
      <p v-if="task">任务状态：{{ task.overallStatus }}，完成 {{ task.finishedVideoCount }}/{{ task.totalVideoCount }}</p>
      <p v-else>暂无任务，请先上传视频并开始处理。</p>
    </div>

    <div class="video-switch-bar">
      <button class="ghost-button" @click="emit('prev-video')">上一视频</button>
      <button
        v-for="video in task?.videos || []"
        :key="video.videoId"
        class="index-button"
        :class="[`state-${video.status}`, { active: video.videoId === selectedVideoId }]"
        @click="emit('select-video', video.videoId)"
      >
        {{ video.orderIndex }}
      </button>
      <button class="ghost-button" @click="emit('next-video')">下一视频</button>
    </div>

    <div class="preview-layout">
      <button class="ghost-button" @click="emit('prev-segment')">上一片段</button>
      <div class="preview-card" v-if="selectedVideo">
        <template v-if="selectedVideo.status === 'success' && selectedSegment">
          <video controls :src="selectedSegment.outputFileUrl" class="video-player"></video>
          <div class="meta-grid">
            <span>片段：{{ selectedSegmentIndex + 1 }}/{{ finalSegments.length }}</span>
            <span>时长：{{ selectedSegment.durationSeconds.toFixed(2) }}s</span>
            <span>原始范围：{{ selectedSegment.originalSegmentIndexRange.join(' ~ ') }}</span>
            <span>候选范围：{{ selectedSegment.candidateBusinessSegmentIndexRange.join(' ~ ') }}</span>
            <span>输出文件：{{ selectedSegment.outputFilePath }}</span>
            <span>连续性保护：{{ selectedSegment.exceededRecommendedDurationBecauseOfContinuity ? '是' : '否' }}</span>
          </div>
        </template>
        <template v-else-if="selectedVideo.status === 'processing'">
          <div class="state-card processing">当前视频处理中：{{ selectedVideo.progressText }}</div>
        </template>
        <template v-else-if="selectedVideo.status === 'failed'">
          <div class="state-card failed">处理失败：{{ selectedVideo.errorMessage }}</div>
        </template>
        <template v-else>
          <div class="state-card waiting">等待处理...</div>
        </template>
      </div>
      <div class="preview-card" v-else>
        <div class="state-card waiting">等待任务数据</div>
      </div>
      <button class="ghost-button" @click="emit('next-segment')">下一片段</button>
    </div>

    <div class="log-panel" v-if="selectedVideo">
      <h3>当前视频摘要</h3>
      <p>文件名：{{ selectedVideo.fileName }}，状态：{{ statusText(selectedVideo.status) }}，阶段：{{ selectedVideo.stage }}</p>
      <h3>当前视频日志（仅此视频）</h3>
      <div class="log-list">
        <div v-for="(logItem, index) in selectedVideo.logs" :key="index" class="log-item" :class="`log-${logItem.level}`">
          [{{ logItem.time }}] [{{ logItem.level }}] [{{ logItem.stage }}] {{ logItem.message }}
        </div>
      </div>
    </div>
  </section>
</template>
