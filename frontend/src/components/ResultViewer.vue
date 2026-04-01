<template>
  <section class="panel-section">
    <h2>三、结果展示区</h2>

    <div class="pagination-row">
      <button class="secondary-button" :disabled="currentVideoIndex === 0" @click="goToPreviousVideo">上一页</button>
      <button
        v-for="(videoItem, index) in processedVideoList"
        :key="`${videoItem.original_file_name}-${index}`"
        class="page-button"
        :class="{ active: index === currentVideoIndex }"
        @click="selectVideoByIndex(index)"
      >
        {{ index + 1 }}
      </button>
      <button
        class="secondary-button"
        :disabled="currentVideoIndex === processedVideoList.length - 1"
        @click="goToNextVideo"
      >
        下一页
      </button>
    </div>

    <p class="current-video-title">当前视频：{{ currentVideoItem?.original_file_name }}</p>

    <div class="segment-preview-row" v-if="currentSegmentItem">
      <button class="secondary-button" :disabled="currentSegmentIndex === 0" @click="goToPreviousSegment">上一片段</button>

      <div class="preview-center">
        <video :src="currentSegmentPreviewUrl" controls class="preview-video"></video>
        <p>组编号：{{ currentSegmentItem.group_number }}</p>
        <p>
          时间范围：{{ currentSegmentItem.start_seconds }}s - {{ currentSegmentItem.end_seconds }}s，
          总时长：{{ currentSegmentItem.total_duration_seconds }}s
        </p>
        <p>
          原始片段索引范围：{{ currentSegmentItem.source_scene_index_range?.[0] }} -
          {{ currentSegmentItem.source_scene_index_range?.[1] }}
        </p>
      </div>

      <button
        class="secondary-button"
        :disabled="currentSegmentIndex === currentVideoSegments.length - 1"
        @click="goToNextSegment"
      >
        下一片段
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  processedVideoList: {
    type: Array,
    required: true
  },
  backendBaseUrl: {
    type: String,
    required: true
  }
})

const currentVideoIndex = ref(0)
const currentSegmentIndex = ref(0)

const currentVideoItem = computed(() => props.processedVideoList[currentVideoIndex.value])
const currentVideoSegments = computed(() => currentVideoItem.value?.grouped_segments || [])
const currentSegmentItem = computed(() => currentVideoSegments.value[currentSegmentIndex.value])

const currentSegmentPreviewUrl = computed(() => {
  const exportedRelativePath = currentSegmentItem.value?.exported_file_path
  return exportedRelativePath ? `${props.backendBaseUrl}${exportedRelativePath}` : ''
})

/**
 * 切换视频时重置片段索引到第1个片段（索引0），
 * 以满足“切换视频后默认第1个片段”的交互要求。
 */
watch(currentVideoIndex, () => {
  currentSegmentIndex.value = 0
})

function selectVideoByIndex(videoIndex) {
  currentVideoIndex.value = videoIndex
}

function goToPreviousVideo() {
  if (currentVideoIndex.value > 0) {
    currentVideoIndex.value -= 1
  }
}

function goToNextVideo() {
  if (currentVideoIndex.value < props.processedVideoList.length - 1) {
    currentVideoIndex.value += 1
  }
}

function goToPreviousSegment() {
  if (currentSegmentIndex.value > 0) {
    currentSegmentIndex.value -= 1
  }
}

function goToNextSegment() {
  if (currentSegmentIndex.value < currentVideoSegments.value.length - 1) {
    currentSegmentIndex.value += 1
  }
}
</script>
