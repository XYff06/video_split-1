<template>
  <section class="panel regroup-panel">
    <div class="regroup-panel-header">
      <div>
        <h2>裂变与重组</h2>
        <p class="panel-subtitle">这里可以独立预览裂变视频和重组视频，并对单个裂变结果做增加、删除、重做。</p>
      </div>

      <button
        class="ghost-button regroup-action-button"
        :disabled="!currentFissionVideo || isWorking"
        @click="$emit('regroup-video', selectedFissionVideoIndex)"
      >
        {{ isWorking ? '处理中...' : '重新重组当前视频' }}
      </button>
    </div>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <div class="regroup-grid">
      <section class="regroup-card">
        <h3>裂变视频预览</h3>

        <div class="regroup-filters">
          <label>
            <span>视频</span>
            <select v-model.number="selectedFissionVideoIndex">
              <option v-for="(video, index) in videoResults" :key="`${video.video_name}-${index}`" :value="index">
                {{ video.video_name }}
              </option>
            </select>
          </label>

          <label>
            <span>原片段</span>
            <select v-model.number="selectedSegmentIndex">
              <option
                v-for="(segment, index) in currentFissionVideo?.merged_segments || []"
                :key="`segment-${segment.group_index}`"
                :value="index"
              >
                group_{{ String(segment.group_index).padStart(3, '0') }}
              </option>
            </select>
          </label>

          <label>
            <span>裂变视频</span>
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
            :disabled="!currentFissionSegment || isWorking"
            @click="$emit('add-variant', selectedFissionVideoIndex, selectedSegmentIndex)"
          >
            增加一个裂变视频
          </button>
          <button
            class="danger-button"
            :disabled="!selectedVariant || isWorking"
            @click="$emit('delete-variant', selectedFissionVideoIndex, selectedSegmentIndex, selectedVariant.variant_index)"
          >
            删除当前裂变视频
          </button>
          <button
            class="ghost-button"
            :disabled="!selectedVariant || isWorking"
            @click="$emit('redo-variant', selectedFissionVideoIndex, selectedSegmentIndex, selectedVariant.variant_index)"
          >
            重做当前裂变视频
          </button>
        </div>
      </section>

      <section class="regroup-card">
        <h3>重组视频预览</h3>

        <div class="regroup-filters">
          <label>
            <span>视频</span>
            <select v-model.number="selectedRegroupVideoIndex">
              <option v-for="(video, index) in videoResults" :key="`regroup-video-${index}`" :value="index">
                {{ video.video_name }}
              </option>
            </select>
          </label>

          <label>
            <span>重组视频</span>
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

defineEmits(['add-variant', 'delete-variant', 'redo-variant', 'regroup-video'])

const selectedFissionVideoIndex = ref(0)
const selectedSegmentIndex = ref(0)
const selectedVariantIndex = ref(0)
const selectedRegroupVideoIndex = ref(0)
const selectedRegroupIndex = ref(1)

const currentFissionVideo = computed(() => props.videoResults[selectedFissionVideoIndex.value] ?? null)
const currentFissionSegment = computed(() => currentFissionVideo.value?.merged_segments?.[selectedSegmentIndex.value] ?? null)
const currentVariantList = computed(() => currentFissionSegment.value?.generated_videos || [])
const selectedVariant = computed(() => {
  return currentVariantList.value.find((item) => item.variant_index === selectedVariantIndex.value) || currentVariantList.value[0] || null
})

const currentRegroupVideoRoot = computed(() => props.videoResults[selectedRegroupVideoIndex.value] ?? null)
const currentRegroupList = computed(() => currentRegroupVideoRoot.value?.regrouped_videos || [])
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
      selectedFissionVideoIndex.value = 0
      selectedSegmentIndex.value = 0
      selectedVariantIndex.value = 0
      selectedRegroupVideoIndex.value = 0
      selectedRegroupIndex.value = 1
      return
    }

    selectedFissionVideoIndex.value = Math.min(selectedFissionVideoIndex.value, nextVideoResults.length - 1)
    selectedRegroupVideoIndex.value = Math.min(selectedRegroupVideoIndex.value, nextVideoResults.length - 1)
  },
  { deep: true, immediate: true }
)

watch(currentFissionSegment, (segment) => {
  selectedVariantIndex.value = segment?.generated_videos?.[0]?.variant_index ?? 0
})

watch(currentFissionVideo, (video) => {
  const totalSegments = video?.merged_segments?.length ?? 0
  selectedSegmentIndex.value = totalSegments ? Math.min(selectedSegmentIndex.value, totalSegments - 1) : 0
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
