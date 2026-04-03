<template>
  <section class="panel regroup-panel">
    <div class="regroup-panel-header">
      <div>
        <h2>裂变与重组</h2>
        <p class="panel-subtitle">这里可以独立预览裂变视频和重组视频，并对单个裂变结果做增加、删除、重做。</p>
      </div>

      <label class="regroup-header-picker" v-if="videoResults.length">
        <span>选择视频</span>
        <select v-model.number="selectedVideoIndex">
          <option v-for="(video, index) in videoResults" :key="`${video.video_name}-${index}`" :value="index">
            {{ video.video_name }}
          </option>
        </select>
      </label>
    </div>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <div class="regroup-grid">
      <section class="regroup-card">
        <h3>裂变视频预览</h3>

        <div class="regroup-filters">
          <label>
            <span>选择片段</span>
            <select v-model.number="selectedSegmentIndex">
              <option
                v-for="(segment, index) in currentVideo?.merged_segments || []"
                :key="`segment-${segment.group_index}`"
                :value="index"
              >
                group_{{ String(segment.group_index).padStart(3, '0') }}
              </option>
            </select>
          </label>

          <label>
            <span>选择裂变视频</span>
            <select v-model.number="selectedVariantIndex">
              <option
                v-for="variant in currentVariantList"
                :key="`variant-${variant.variant_index}`"
                :value="variant.variant_index"
              >
                {{ variantLabel(variant) }}
              </option>
            </select>
          </label>
        </div>

        <div class="preview-card regroup-preview-card">
          <div class="preview-video-shell">
            <video
              v-if="selectedVariant?.public_url"
              class="preview-video"
              :src="selectedVariant.public_url"
              controls
            />
            <div v-else class="empty-card">当前没有可预览的裂变视频。</div>
          </div>
          <div class="preview-info" v-if="selectedVariant">
            <p>文件：{{ fileName(selectedVariant.file_path) }}</p>
            <p>编号：{{ String(selectedVariant.variant_index).padStart(3, '0') }}</p>
          </div>
        </div>

        <div class="regroup-actions">
          <button
            class="primary-button"
            :disabled="!currentSegment || isWorking"
            @click="$emit('add-variant', selectedVideoIndex, selectedSegmentIndex)"
          >
            增加一个裂变视频
          </button>
          <button
            class="danger-button"
            :disabled="!canDeleteSelectedVariant || isWorking"
            @click="$emit('delete-variant', selectedVideoIndex, selectedSegmentIndex, selectedVariant.variant_index)"
          >
            删除当前裂变视频
          </button>
          <button
            class="ghost-button"
            :disabled="!selectedVariant || isWorking"
            @click="$emit('redo-variant', selectedVideoIndex, selectedSegmentIndex, selectedVariant.variant_index)"
          >
            重做当前裂变视频
          </button>
        </div>
      </section>

      <section class="regroup-card">
        <h3>重组视频预览</h3>

        <div class="regroup-filters regroup-filters-actions">
          <label>
            <span>选择要预览的重组视频</span>
            <select v-model.number="selectedRegroupIndex">
              <option
                v-for="video in currentRegroupList"
                :key="`regroup-${video.regroup_index}`"
                :value="video.regroup_index"
              >
                regroup_{{ String(video.regroup_index).padStart(3, '0') }}
              </option>
            </select>
          </label>

          <button
            class="ghost-button"
            :disabled="!currentVideo || isWorking"
            @click="$emit('regroup-video', selectedVideoIndex)"
          >
            重组当前视频
          </button>
          <button
            class="primary-button"
            :disabled="!videoResults.length || isWorking"
            @click="$emit('regroup-all-videos')"
          >
            重组全部视频
          </button>
        </div>

        <div class="preview-card regroup-preview-card">
          <div class="preview-video-shell">
            <video
              v-if="selectedRegroupVideo?.public_url"
              class="preview-video"
              :src="selectedRegroupVideo.public_url"
              controls
            />
            <div v-else class="empty-card">当前没有可预览的重组视频。</div>
          </div>
          <div class="preview-info" v-if="selectedRegroupVideo">
            <p>文件：{{ fileName(selectedRegroupVideo.file_path) }}</p>
            <p>来源：{{ regroupSummary }}</p>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  videoResults: { type: Array, default: () => [] },
  isWorking: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
})

defineEmits(['add-variant', 'delete-variant', 'redo-variant', 'regroup-video', 'regroup-all-videos'])

const selectedVideoIndex = ref(0)
const selectedSegmentIndex = ref(0)
const selectedVariantIndex = ref(0)
const selectedRegroupIndex = ref(1)

const currentVideo = computed(() => props.videoResults[selectedVideoIndex.value] ?? null)
const currentSegment = computed(() => currentVideo.value?.merged_segments?.[selectedSegmentIndex.value] ?? null)
const currentVariantList = computed(() => currentSegment.value?.generated_videos || [])
const selectedVariant = computed(() => {
  return currentVariantList.value.find((item) => item.variant_index === selectedVariantIndex.value) || currentVariantList.value[0] || null
})
const canDeleteSelectedVariant = computed(() => {
  if (!selectedVariant.value) return false
  return !(currentVariantList.value.length === 1 && selectedVariant.value.variant_index === 0)
})

const currentRegroupList = computed(() => currentVideo.value?.regrouped_videos || [])
const selectedRegroupVideo = computed(() => {
  return currentRegroupList.value.find((item) => item.regroup_index === selectedRegroupIndex.value) || currentRegroupList.value[0] || null
})

const regroupSummary = computed(() => {
  const sourceVariants = selectedRegroupVideo.value?.source_variants || []
  return sourceVariants
    .map((item) => `group_${String(item.group_index).padStart(3, '0')}:${String(item.variant_index).padStart(3, '0')}`)
    .join(' / ')
})

watch(
  () => props.videoResults,
  (nextVideoResults) => {
    if (!nextVideoResults.length) {
      selectedVideoIndex.value = 0
      selectedSegmentIndex.value = 0
      selectedVariantIndex.value = 0
      selectedRegroupIndex.value = 1
      return
    }

    selectedVideoIndex.value = Math.min(selectedVideoIndex.value, nextVideoResults.length - 1)
  },
  { deep: true, immediate: true }
)

watch(currentVideo, (video) => {
  const totalSegments = video?.merged_segments?.length ?? 0
  selectedSegmentIndex.value = totalSegments ? Math.min(selectedSegmentIndex.value, totalSegments - 1) : 0
})

watch(currentSegment, (segment) => {
  selectedVariantIndex.value = segment?.generated_videos?.[0]?.variant_index ?? 0
})

watch(currentRegroupList, (videos) => {
  selectedRegroupIndex.value = videos?.[0]?.regroup_index ?? 1
})

function variantLabel(variant) {
  return variant.variant_index === 0
    ? 'group_000 原片复制'
    : `group_${String(variant.variant_index).padStart(3, '0')}`
}

function fileName(filePath) {
  return (filePath || '').split('/').pop().split('\\').pop()
}
</script>
