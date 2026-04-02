<template>
  <section class="panel panel-result">
    <h2>处理结果</h2>
    <p class="panel-subtitle">{{ statusText }}</p>

    <VideoTabs
      :videos="videoResults"
      :selected-video-index="selectedVideoIndex"
      :current-page="currentVideoPage"
      :page-size="5"
      @select-video="$emit('select-video', $event)"
      @page-change="$emit('change-video-page', $event)"
    />

    <SegmentPreviewDisplay
      :video-result="currentVideoResult"
      :current-segment="currentSegment"
      :can-prev="canPreviousSegment"
      :can-next="canNextSegment"
      @prev-segment="$emit('prev-segment')"
      @next-segment="$emit('next-segment')"
    />

    <div v-if="isDeveloperMode && currentVideoResult" class="summary-card">
      <h4>处理摘要</h4>
      <p>视频名：{{ currentVideoResult.video_name }}</p>
      <p>状态：{{ currentVideoResult.status }}</p>
      <p>原始场景数：{{ currentVideoResult.summary?.original_scene_count ?? 0 }}</p>
      <p>合并片段数：{{ currentVideoResult.summary?.merged_segment_count ?? 0 }}</p>
    </div>

    <LogPanel
      v-if="isDeveloperMode"
      :current-video-logs="currentVideoLogs"
      :task-logs="taskLogs"
    />
  </section>
</template>

<script setup>
import LogPanel from './LogPanel.vue'
import SegmentPreviewDisplay from './SegmentPreviewDisplay.vue'
import VideoTabs from './VideoTabs.vue'

const isDeveloperMode = import.meta.env.DEV

defineProps({
  statusText: { type: String, default: '' },
  videoResults: { type: Array, default: () => [] },
  selectedVideoIndex: { type: Number, default: -1 },
  currentVideoPage: { type: Number, default: 0 },
  currentVideoResult: { type: Object, default: null },
  currentSegment: { type: Object, default: null },
  currentVideoLogs: { type: Array, default: () => [] },
  taskLogs: { type: Array, default: () => [] },
  canPreviousSegment: { type: Boolean, default: false },
  canNextSegment: { type: Boolean, default: false }
})

defineEmits(['select-video', 'change-video-page', 'prev-segment', 'next-segment'])
</script>
