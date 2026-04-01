<template>
  <section class="panel-card result-panel">
    <div class="panel-header">
      <h2>处理结果</h2>
      <p>{{ statusDescription }}</p>
    </div>

    <div v-if="allVideos.length === 0" class="empty-state-card">
      <p>暂无处理结果。请在左侧上传视频后点击“开始处理”。</p>
    </div>

    <template v-else>
      <div class="video-pagination-bar">
        <button class="secondary-button" :disabled="selectedVideoIndex <= 0" @click="selectPreviousVideo">上一页</button>
        <button
          v-for="(videoResult, index) in allVideos"
          :key="`${videoResult.video_name}_${index}`"
          class="page-index-button"
          :class="{ active: selectedVideoIndex === index }"
          @click="selectVideoByIndex(index)"
        >
          {{ index + 1 }}
        </button>
        <button
          class="secondary-button"
          :disabled="selectedVideoIndex >= allVideos.length - 1"
          @click="selectNextVideo"
        >
          下一页
        </button>
      </div>

      <div class="preview-navigation-row">
        <button class="secondary-button" :disabled="!canSelectPreviousSegment" @click="selectPreviousSegment">上一片段</button>

        <div class="preview-card" v-if="currentVideoResult.status === 'success' && currentSegment">
          <video :src="resolveMediaUrl(currentSegment.export_file_url)" controls class="preview-video-player"></video>
          <p><strong>片段编号：</strong>{{ currentSegment.group_index }}</p>
          <p><strong>片段时长：</strong>{{ currentSegment.duration_seconds.toFixed(3) }} 秒</p>
          <p>
            <strong>原始片段范围：</strong>
            {{ currentSegment.original_scene_index_range.start }} - {{ currentSegment.original_scene_index_range.end }}
          </p>
          <p class="path-text"><strong>导出地址：</strong>{{ currentSegment.export_file_url }}</p>
        </div>

        <div class="preview-card failed-preview-card" v-else>
          <h4>当前视频处理失败</h4>
          <p>{{ currentVideoResult.error_message }}</p>
        </div>

        <button class="secondary-button" :disabled="!canSelectNextSegment" @click="selectNextSegment">下一片段</button>
      </div>

      <div class="summary-box">
        <p><strong>视频名称：</strong>{{ currentVideoResult.video_name }}</p>
        <p><strong>状态：</strong>{{ currentVideoResult.status === 'success' ? '成功' : '失败' }}</p>
        <p v-if="currentVideoResult.status === 'success'">
          <strong>输出片段数：</strong>{{ currentVideoResult.merged_segment_count }}
        </p>
      </div>

      <div class="log-box">
        <h3>本次处理日志</h3>
        <div class="log-scroll-area">
          <p v-for="(oneLog, logIndex) in processingLogs" :key="`${logIndex}_${oneLog.message}`" :class="`log-${oneLog.level}`">
            [{{ oneLog.level.toUpperCase() }}] {{ oneLog.message }}
          </p>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { resolveMediaUrl } from '../api/videoApi'

const props = defineProps({
  isProcessing: { type: Boolean, required: true },
  successfulVideos: { type: Array, required: true },
  failedVideos: { type: Array, required: true },
  processingLogs: { type: Array, required: true }
})

const selectedVideoIndex = ref(0)
const selectedSegmentIndex = ref(0)

const allVideos = computed(() => {
  const successEntries = props.successfulVideos.map((videoResult) => ({ ...videoResult, status: 'success' }))
  const failedEntries = props.failedVideos.map((failedResult) => ({ ...failedResult, status: 'failed' }))
  return [...successEntries, ...failedEntries]
})

const statusDescription = computed(() => {
  if (props.isProcessing) return '后端处理中，请稍候...'
  if (allVideos.value.length === 0) return '等待处理任务开始。'
  return `共 ${allVideos.value.length} 个视频结果（成功 ${props.successfulVideos.length}，失败 ${props.failedVideos.length}）。`
})

const currentVideoResult = computed(() => allVideos.value[selectedVideoIndex.value] || { status: 'failed', video_name: '-', error_message: '-' })
const currentSegments = computed(() => currentVideoResult.value.merged_segments || [])
const currentSegment = computed(() => currentSegments.value[selectedSegmentIndex.value])

const canSelectPreviousSegment = computed(() => currentVideoResult.value.status === 'success' && selectedSegmentIndex.value > 0)
const canSelectNextSegment = computed(
  () => currentVideoResult.value.status === 'success' && selectedSegmentIndex.value < currentSegments.value.length - 1
)

watch(
  () => allVideos.value.length,
  () => {
    if (selectedVideoIndex.value >= allVideos.value.length) {
      selectedVideoIndex.value = Math.max(allVideos.value.length - 1, 0)
    }
  }
)

watch(
  () => selectedVideoIndex.value,
  () => {
    // 切换视频后重置片段索引到第 1 个，确保预览状态一致。
    selectedSegmentIndex.value = 0
  }
)

function selectVideoByIndex(index) {
  selectedVideoIndex.value = index
}

function selectPreviousVideo() {
  if (selectedVideoIndex.value > 0) {
    selectedVideoIndex.value -= 1
  }
}

function selectNextVideo() {
  if (selectedVideoIndex.value < allVideos.value.length - 1) {
    selectedVideoIndex.value += 1
  }
}

function selectPreviousSegment() {
  if (canSelectPreviousSegment.value) {
    selectedSegmentIndex.value -= 1
  }
}

function selectNextSegment() {
  if (canSelectNextSegment.value) {
    selectedSegmentIndex.value += 1
  }
}
</script>
