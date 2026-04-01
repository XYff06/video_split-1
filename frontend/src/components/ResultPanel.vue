<template>
  <section class="result-panel">
    <h2>结果展示区</h2>

    <div class="video-selector">
      <button @click="goToPreviousVideo" :disabled="activeVideoIndex === 0">上一页</button>
      <button
        v-for="(videoItem, index) in successfulVideos"
        :key="videoItem.video_name"
        :class="{ active: index === activeVideoIndex }"
        @click="selectVideo(index)"
      >
        {{ index + 1 }}
      </button>
      <button
        @click="goToNextVideo"
        :disabled="activeVideoIndex >= successfulVideos.length - 1 || successfulVideos.length === 0"
      >
        下一页
      </button>
    </div>

    <div v-if="activeMergedSegment" class="segment-preview-wrapper">
      <button @click="goToPreviousSegment" :disabled="activeSegmentIndex === 0">上一片段</button>

      <div class="video-preview-center">
        <video :src="activeSegmentVideoSource" controls class="preview-video"></video>
        <p>组编号: {{ activeMergedSegment.group_number }}</p>
        <p>
          时间范围: {{ activeMergedSegment.start_timestamp }} - {{ activeMergedSegment.end_timestamp }}
        </p>
        <p>总时长: {{ activeMergedSegment.duration_timestamp }}</p>
        <p>
          原始片段范围:
          {{ activeMergedSegment.included_segment_index_start }} -
          {{ activeMergedSegment.included_segment_index_end }}
        </p>
      </div>

      <button
        @click="goToNextSegment"
        :disabled="activeSegmentIndex >= activeVideoMergedSegments.length - 1"
      >
        下一片段
      </button>
    </div>

    <div v-else class="empty-hint">暂无可预览片段，请先完成处理。</div>

    <h3>失败视频</h3>
    <ul>
      <li v-for="failedItem in failedVideos" :key="failedItem.video_name">
        {{ failedItem.video_name }} - {{ failedItem.error }}
      </li>
    </ul>

    <h3>处理日志</h3>
    <pre class="log-block">{{ processLogs.join('\n') }}</pre>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  successfulVideos: { type: Array, required: true },
  failedVideos: { type: Array, required: true },
  processLogs: { type: Array, required: true }
})

const activeVideoIndex = ref(0)
const activeSegmentIndex = ref(0)

const activeVideoMergedSegments = computed(() => {
  const activeVideo = props.successfulVideos[activeVideoIndex.value]
  return activeVideo ? activeVideo.merged_segments : []
})

const activeMergedSegment = computed(() => activeVideoMergedSegments.value[activeSegmentIndex.value] || null)

const activeSegmentVideoSource = computed(() => {
  if (!activeMergedSegment.value) {
    return ''
  }
  const normalizedPath = activeMergedSegment.value.export_file_path.replace('/workspace/video_split-1/backend', '')
  return `http://localhost:5000${normalizedPath}`
})

function selectVideo(targetVideoIndex) {
  activeVideoIndex.value = targetVideoIndex
  activeSegmentIndex.value = 0
}

function goToPreviousVideo() {
  if (activeVideoIndex.value > 0) {
    selectVideo(activeVideoIndex.value - 1)
  }
}

function goToNextVideo() {
  if (activeVideoIndex.value < props.successfulVideos.length - 1) {
    selectVideo(activeVideoIndex.value + 1)
  }
}

function goToPreviousSegment() {
  if (activeSegmentIndex.value > 0) {
    activeSegmentIndex.value -= 1
  }
}

function goToNextSegment() {
  if (activeSegmentIndex.value < activeVideoMergedSegments.value.length - 1) {
    activeSegmentIndex.value += 1
  }
}

watch(
  () => props.successfulVideos,
  () => {
    activeVideoIndex.value = 0
    activeSegmentIndex.value = 0
  }
)
</script>
