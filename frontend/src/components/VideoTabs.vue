<template>
  <div class="video-tabs">
    <button class="ghost-button page-edge-button" :disabled="currentPage === 0" @click="$emit('page-change', currentPage - 1)">
      上一页
    </button>

    <div class="video-tab-items">
      <button
        v-for="(video, index) in pageItems"
        :key="`${video.video_name}-${index}`"
        class="tab-button video-name-button"
        :class="{ active: pageStart + index === selectedVideoIndex, failed: video.status === 'failed' }"
        @click="$emit('select-video', pageStart + index)"
      >
        {{ video.video_name }}
      </button>
    </div>

    <button
      class="ghost-button page-edge-button"
      :disabled="currentPage >= pageCount - 1"
      @click="$emit('page-change', currentPage + 1)"
    >
      下一页
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  videos: { type: Array, default: () => [] },
  selectedVideoIndex: { type: Number, default: -1 },
  currentPage: { type: Number, default: 0 },
  pageSize: { type: Number, default: 5 }
})

const pageStart = computed(() => props.currentPage * props.pageSize)
const pageItems = computed(() => props.videos.slice(pageStart.value, pageStart.value + props.pageSize))
const pageCount = computed(() => Math.max(1, Math.ceil(props.videos.length / props.pageSize)))

defineEmits(['select-video', 'page-change'])
</script>

