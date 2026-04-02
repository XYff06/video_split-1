<template>
  <div class="video-tabs">
    <button class="ghost-button page-edge-button" :disabled="currentPage === 0" @click="$emit('page-change', currentPage - 1)">
      上一页
    </button>

    <div class="video-tab-items">
      <button
        v-for="(video, index) in pageItems"
        :key="`${video.video_name}-${pageStart + index}`"
        class="tab-button video-name-button"
        :class="{ active: pageStart + index === selectedVideoIndex, failed: video.status === 'failed' }"
        @click="$emit('select-video', pageStart + index)"
      >
        <span class="video-name-viewport" :ref="element => setViewportRef(element, pageStart + index)">
          <span
            v-if="isOverflowing(pageStart + index)"
            class="video-name-track scrolling"
          >
            <span class="video-name-copy">{{ video.video_name }}</span>
            <span class="video-name-gap" aria-hidden="true">　　</span>
            <span class="video-name-copy" aria-hidden="true">{{ video.video_name }}</span>
          </span>

          <span
            v-else
            class="video-name-track"
            :ref="element => setTextRef(element, pageStart + index)"
          >
            {{ video.video_name }}
          </span>

          <span
            v-if="isOverflowing(pageStart + index)"
            class="video-name-measure"
            :ref="element => setTextRef(element, pageStart + index)"
          >
            {{ video.video_name }}
          </span>
        </span>
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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, watch } from 'vue'

const props = defineProps({
  videos: { type: Array, default: () => [] },
  selectedVideoIndex: { type: Number, default: -1 },
  currentPage: { type: Number, default: 0 },
  pageSize: { type: Number, default: 5 }
})

const emit = defineEmits(['select-video', 'page-change'])

const pageStart = computed(() => props.currentPage * props.pageSize)
const pageItems = computed(() => props.videos.slice(pageStart.value, pageStart.value + props.pageSize))
const pageCount = computed(() => Math.max(1, Math.ceil(props.videos.length / props.pageSize)))
const overflowStateByIndex = reactive({})
const viewportElementByIndex = new Map()
const textElementByIndex = new Map()
let resizeObserver = null

function isOverflowing(index) {
  return Boolean(overflowStateByIndex[index])
}

function setViewportRef(element, index) {
  const previousElement = viewportElementByIndex.get(index)

  if (resizeObserver && previousElement && previousElement !== element) {
    resizeObserver.unobserve(previousElement)
  }

  if (!element) {
    viewportElementByIndex.delete(index)
    delete overflowStateByIndex[index]
    return
  }

  viewportElementByIndex.set(index, element)
  resizeObserver?.observe(element)
  queueOverflowEvaluation()
}

function setTextRef(element, index) {
  if (!element) {
    textElementByIndex.delete(index)
    return
  }

  textElementByIndex.set(index, element)
  queueOverflowEvaluation()
}

async function queueOverflowEvaluation() {
  await nextTick()
  evaluateVisibleTextOverflow()
}

function evaluateVisibleTextOverflow() {
  const visibleIndexes = pageItems.value.map((_, offset) => pageStart.value + offset)

  visibleIndexes.forEach(index => {
    const viewportElement = viewportElementByIndex.get(index)
    const textElement = textElementByIndex.get(index)

    overflowStateByIndex[index] = Boolean(
      viewportElement &&
      textElement &&
      textElement.scrollWidth > viewportElement.clientWidth + 1
    )
  })
}

function handleWindowResize() {
  evaluateVisibleTextOverflow()
}

watch(
  () => [
    props.currentPage,
    props.pageSize,
    props.selectedVideoIndex,
    props.videos.map(video => `${video.video_name}-${video.status}`).join('|')
  ],
  () => {
    queueOverflowEvaluation()
  },
  { immediate: true }
)

onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    evaluateVisibleTextOverflow()
  })

  window.addEventListener('resize', handleWindowResize)
  queueOverflowEvaluation()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', handleWindowResize)
})
</script>
