<template>
  <section class="panel unified-workbench">
    <div class="unified-header">
      <div>
        <h2>处理工作台</h2>
        <p class="panel-subtitle">{{ statusText }}</p>
      </div>

      <div v-if="currentVideoResult" class="unified-meta">
        <p>视频：{{ currentVideoResult.video_name }}</p>
        <p>片段：{{ currentSegment ? `${currentSegment.group_index} / ${segmentCount}` : `0 / ${segmentCount}` }}</p>
        <p>状态：{{ analysisStatusText }}</p>
      </div>
    </div>

    <VideoTabs
      :videos="videoResults"
      :selected-video-index="selectedVideoIndex"
      :current-page="currentVideoPage"
      :page-size="5"
      @select-video="$emit('select-video', $event)"
      @page-change="$emit('change-video-page', $event)"
    />

    <p v-if="actionErrorMessage || errorMessage" class="error-text">
      {{ actionErrorMessage || errorMessage }}
    </p>

    <div class="unified-body">
      <section class="unified-segment-panel">
        <div class="unified-section-head">
          <h3>片段列表</h3>
          <span class="hint-text">点击任意片段切换当前工作内容</span>
        </div>

        <div v-if="currentVideoResult?.status === 'failed'" class="prompt-empty error-card">
          {{ currentVideoResult.error_message || '当前视频处理失败。' }}
        </div>

        <div v-else-if="segmentList.length" class="segment-card-list">
          <button
            v-for="(segment, index) in segmentList"
            :key="`${currentVideoResult.video_name}-${segment.group_index}-${index}`"
            class="segment-card"
            :class="{ active: index === currentSegmentIndex }"
            type="button"
            @click="$emit('select-segment', index)"
          >
            <div class="segment-card-video">
              <video
                v-if="segment.export_public_url"
                :ref="(el) => setSegmentVideoRef(el, index)"
                :src="segment.export_public_url"
                class="preview-video"
                controls
                :muted="index !== currentSegmentIndex"
                autoplay
                loop
                playsinline
                preload="metadata"
              />
              <div v-else class="empty-card">暂无预览</div>
            </div>
            <div class="segment-card-copy">
              <p>片段 {{ segment.group_index }}</p>
              <p>时长 {{ formatDuration(segment.duration_seconds) }}</p>
            </div>
          </button>
        </div>

        <div v-else class="prompt-empty">
          {{ currentVideoResult ? '当前视频还没有可查看的片段。' : '请先上传并处理视频。' }}
        </div>
      </section>

      <section class="unified-main-panel">
        <div class="unified-main-top">
          <div class="unified-prompt-editor unified-prompt-editor-top">
            <div class="unified-section-head">
              <h3>片段提示词</h3>
              <span class="hint-text">当前片段反推提示词支持直接修改</span>
            </div>
            <template v-if="!currentVideoResult">
              <div class="prompt-empty">请先上传并处理视频，提示词会显示在这里。</div>
            </template>
            <template v-else-if="currentVideoResult.status === 'failed'">
              <div class="prompt-empty error-card">当前视频处理失败，无法生成片段提示词。</div>
            </template>
            <template v-else-if="!currentSegment">
              <div class="prompt-empty">当前视频还没有可查看的合并片段。</div>
            </template>
            <template v-else-if="currentSegment.analysis_status === 'failed'">
              <div class="prompt-empty error-card">
                {{ currentSegment.analysis_error_message || '提示词生成失败。' }}
              </div>
            </template>
            <template v-else-if="currentSegment.analysis_status === 'skipped'">
              <div class="prompt-empty">
                {{ currentSegment.analysis_error_message || '当前片段未执行提示词反推。' }}
              </div>
            </template>
            <template v-else>
              <textarea
                id="editable-prompt"
                class="prompt-textarea unified-prompt-textarea"
                :value="editablePrompt"
                @input="updateEditablePrompt"
              />
              <p v-if="!basePrompt" class="hint-text">当前片段提示词还没有写入，等分析结果返回后会显示在这里。</p>
            </template>
          </div>

          <div class="unified-reference-card">
            <div class="unified-section-head">
              <h3>图片参考</h3>
              <div class="prompt-addon-toolbar compact">
                <button class="add-addon-button" type="button" :disabled="!currentSegment || isAddonLimitReached" @click="addAddon">
                  <span>+</span>
                </button>
                <span class="hint-text">{{ addonItems.length }} / 5</span>
              </div>
            </div>

            <div v-if="currentSegment" class="reference-grid">
              <article v-for="item in displayedAddonItems" :key="item.id" class="prompt-addon-tile">
                <div class="prompt-addon-tile-header">
                  <span class="prompt-addon-index">参考 {{ addonIndexLabel(item.id) }}</span>
                  <button class="prompt-addon-remove" type="button" @click="removeAddon(item.id)">删除</button>
                </div>

                <label class="addon-upload-box compact" :for="`addon-upload-${item.id}`">
                  <input
                    :id="`addon-upload-${item.id}`"
                    class="hidden"
                    type="file"
                    accept="image/*"
                    @change="handleImageChange($event, item.id)"
                  />
                  <template v-if="item.imagePreviewUrl">
                    <img :src="item.imagePreviewUrl" alt="参考图预览" class="addon-preview-image compact" />
                    <span class="addon-upload-meta">{{ item.imageName }}</span>
                  </template>
                  <template v-else>
                    <span class="addon-upload-title compact">上传图片</span>
                    <span class="hint-text">仅 1 张</span>
                  </template>
                </label>

                <textarea
                  class="addon-textarea compact"
                  :value="item.text"
                  placeholder="补充说明"
                  @input="updateAddonText($event, item.id)"
                />
              </article>
            </div>

            <div v-else class="prompt-empty compact-empty">选择片段后可添加参考图和补充描述。</div>
          </div>
        </div>

        <div class="prompt-control-board">
          <div class="prompt-control-grid" :class="{ 'prompt-control-grid-empty': !currentSegment }">
            <div class="prompt-control-item prompt-control-row">
              <label class="prompt-control-text" for="fission-count">裂变视频数量</label>
              <input
                id="fission-count"
                class="fission-count-input"
                type="number"
                min="0"
                max="10"
                :value="fissionCount"
                :disabled="!currentSegment"
                @input="handleFissionCountInput"
              />
            </div>

            <div class="prompt-control-item">
              <button
                class="primary-button fission-action-button"
                :disabled="disableCurrentVideoButton"
                @click="$emit('generate-current-video')"
              >
                {{ isGeneratingCurrentVideo ? '当前视频裂变中...' : '当前视频裂变' }}
              </button>
            </div>

            <div class="prompt-control-item">
              <button
                class="ghost-button fission-action-button"
                :disabled="disableAllVideosButton"
                @click="$emit('generate-all-videos')"
              >
                {{ isGeneratingAllVideos ? '全部视频裂变中...' : '全部视频裂变' }}
              </button>
            </div>

            <div class="prompt-control-item prompt-control-row">
              <label class="prompt-control-text" for="global-size">全局 Size</label>
              <select
                id="global-size"
                class="size-select"
                :value="globalSize"
                @change="$emit('change-global-size', $event.target.value)"
              >
                <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
              </select>
            </div>

            <div class="prompt-control-item prompt-control-row">
              <label class="prompt-control-text" for="current-video-size">当前视频 Size</label>
              <select
                id="current-video-size"
                class="size-select"
                :value="currentVideoSize"
                :disabled="!currentVideoResult"
                @change="$emit('change-current-video-size', $event.target.value)"
              >
                <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
              </select>
            </div>

            <div class="prompt-control-item">
              <button
                class="ghost-button fission-action-button"
                type="button"
                :disabled="!currentVideoResult || isCurrentVideoFollowingGlobal"
                @click="$emit('reset-current-video-size')"
              >
                重置为跟随全局
              </button>
            </div>
          </div>
        </div>

        <div class="unified-variant-panel">
          <div class="unified-section-head">
            <h3>裂变视频预览</h3>
            <span class="hint-text">当前片段生成的所有裂变结果</span>
          </div>

          <div v-if="currentSegment" class="variant-grid">
            <article v-for="variant in currentVariantList" :key="variant.variant_index" class="variant-card">
              <div class="preview-video-shell variant-video-shell">
                <video v-if="variant.public_url" :src="variant.public_url" controls class="preview-video" />
                <div v-else class="empty-card">当前没有可预览的视频。</div>
              </div>
              <div class="preview-info">
                <p>{{ variantLabel(variant) }}</p>
                <p>{{ fileName(variant.file_path) || '尚未生成文件' }}</p>
              </div>
              <div class="variant-actions">
                <button
                  class="danger-button"
                  :disabled="!canDeleteVariant(variant) || isWorking"
                  @click="$emit('delete-variant', selectedVideoIndex, currentSegmentIndex, variant.variant_index)"
                >
                  删除
                </button>
                <button
                  class="ghost-button"
                  :disabled="isWorking"
                  @click="$emit('redo-variant', selectedVideoIndex, currentSegmentIndex, variant.variant_index)"
                >
                  重做
                </button>
              </div>
            </article>

            <button
              class="variant-card variant-add-card"
              type="button"
              :disabled="!currentSegment || isWorking"
              @click="$emit('add-variant', selectedVideoIndex, currentSegmentIndex)"
            >
              <span>新增一个裂变视频</span>
            </button>
          </div>

          <div v-else class="prompt-empty compact-empty">选择片段后可查看和管理裂变视频。</div>
        </div>

        <div class="unified-regroup-panel">
          <div class="unified-section-head">
            <h3>重组视频预览</h3>
            <span class="hint-text">当前视频的重组结果与下载操作</span>
          </div>

          <div class="unified-regroup-toolbar">
            <label class="regroup-toolbar-picker">
              <span>选择重组视频</span>
              <select v-model.number="selectedRegroupIndex" :disabled="!currentRegroupList.length">
                <option
                  v-for="video in currentRegroupList"
                  :key="`regroup-${video.regroup_index}`"
                  :value="video.regroup_index"
                >
                  regroup_{{ String(video.regroup_index).padStart(3, '0') }}
                </option>
              </select>
            </label>

            <div class="regroup-toolbar-actions">
              <button
                class="ghost-button"
                :disabled="!currentRegroupList.length || isWorking"
                @click="$emit('download-current-video', selectedVideoIndex)"
              >
                下载当前视频
              </button>
              <button
                class="ghost-button"
                :disabled="!hasAnyRegroupedVideo || isWorking"
                @click="$emit('download-all-videos')"
              >
                下载全部视频
              </button>
              <button
                class="ghost-button regroup-action-strong"
                :disabled="!currentVideoResult || isWorking"
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
          </div>

          <div class="preview-card">
            <div class="preview-video-shell">
              <video
                v-if="selectedRegroupVideo?.public_url"
                :src="selectedRegroupVideo.public_url"
                controls
                class="preview-video"
              />
              <div v-else class="empty-card">当前没有可预览的重组视频。</div>
            </div>
            <div v-if="selectedRegroupVideo" class="preview-info">
              <p>{{ fileName(selectedRegroupVideo.file_path) }}</p>
              <p>{{ regroupSummary || '暂无来源说明' }}</p>
            </div>
          </div>
        </div>

        <div v-if="isDeveloperMode" class="summary-card">
          <h4>处理摘要</h4>
          <p>视频名：{{ currentVideoResult?.video_name || '--' }}</p>
          <p>状态：{{ currentVideoResult?.status || '--' }}</p>
          <p>原始场景数：{{ currentVideoResult?.summary?.original_scene_count ?? 0 }}</p>
          <p>合并片段数：{{ currentVideoResult?.summary?.merged_segment_count ?? 0 }}</p>
        </div>

        <LogPanel
          v-if="isDeveloperMode"
          :current-video-logs="currentVideoLogs"
          :task-logs="taskLogs"
        />
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import LogPanel from './LogPanel.vue'
import VideoTabs from './VideoTabs.vue'
import { clampFissionCount, ensureSegmentLocalState } from '../utils/segmentPrompt'

const sizeOptions = ['1920*1080', '1080*1920', '1440*1440', '1632*1248', '1248*1632']
const isDeveloperMode = import.meta.env.DEV

const props = defineProps({
  statusText: { type: String, default: '' },
  videoResults: { type: Array, default: () => [] },
  selectedVideoIndex: { type: Number, default: -1 },
  currentVideoPage: { type: Number, default: 0 },
  currentVideoResult: { type: Object, default: null },
  currentSegment: { type: Object, default: null },
  currentSegmentIndex: { type: Number, default: 0 },
  currentVideoLogs: { type: Array, default: () => [] },
  taskLogs: { type: Array, default: () => [] },
  isGeneratingCurrentVideo: { type: Boolean, default: false },
  isGeneratingAllVideos: { type: Boolean, default: false },
  actionErrorMessage: { type: String, default: '' },
  globalSize: { type: String, default: '1920*1080' },
  isWorking: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
})

defineEmits([
  'select-video',
  'change-video-page',
  'select-segment',
  'generate-current-video',
  'generate-all-videos',
  'change-current-video-size',
  'change-global-size',
  'reset-current-video-size',
  'add-variant',
  'delete-variant',
  'redo-variant',
  'regroup-video',
  'regroup-all-videos',
  'download-current-video',
  'download-all-videos'
])

const selectedRegroupIndex = ref(1)
const segmentVideoRefs = ref([])

const segmentList = computed(() => props.currentVideoResult?.merged_segments || [])
const segmentCount = computed(() => segmentList.value.length)

const basePrompt = computed(() => {
  const segment = props.currentSegment
  if (!segment) return ''
  ensureSegmentLocalState(segment)
  return segment.analysis?.prompt?.trim?.() || segment.edited_prompt?.trim?.() || ''
})

const editablePrompt = computed(() => {
  const segment = props.currentSegment
  if (!segment) return ''
  ensureSegmentLocalState(segment)
  return segment.edited_prompt
})

const addonItems = computed(() => {
  const segment = props.currentSegment
  if (!segment) return []
  ensureSegmentLocalState(segment)
  return segment.prompt_addons
})

const displayedAddonItems = computed(() => addonItems.value.slice(0, 5))

const fissionCount = computed(() => {
  const segment = props.currentSegment
  if (!segment) return 1
  ensureSegmentLocalState(segment)
  return segment.fission_count
})

const isCurrentVideoFollowingGlobal = computed(() => props.currentVideoResult?.use_global_fission_size !== false)
const currentVideoSize = computed(() => props.currentVideoResult?.fission_size || props.globalSize)
const isAddonLimitReached = computed(() => addonItems.value.length >= 5)

const analysisStatusText = computed(() => {
  if (!props.currentSegment) return '待选择片段'
  const status = props.currentSegment.analysis_status
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'skipped') return '已跳过'
  if (status === 'pending') return '待生成'
  return '生成中'
})

const disableCurrentVideoButton = computed(() => {
  return !props.currentVideoResult || !props.currentSegment || props.isGeneratingCurrentVideo || props.isGeneratingAllVideos
})

const disableAllVideosButton = computed(() => {
  return !props.currentVideoResult || !props.currentSegment || props.isGeneratingAllVideos || props.isGeneratingCurrentVideo
})

const currentVariantList = computed(() => props.currentSegment?.generated_videos || [])
const currentRegroupList = computed(() => props.currentVideoResult?.regrouped_videos || [])
const hasAnyRegroupedVideo = computed(() => props.videoResults.some((video) => (video?.regrouped_videos || []).length > 0))
const selectedRegroupVideo = computed(() => {
  return currentRegroupList.value.find((item) => item.regroup_index === selectedRegroupIndex.value) || currentRegroupList.value[0] || null
})

const regroupSummary = computed(() => {
  const sourceVariants = selectedRegroupVideo.value?.source_variants || []
  return sourceVariants
    .map((item) => `group_${String(item.group_index).padStart(3, '0')}:${String(item.variant_index).padStart(3, '0')}`)
    .join(' / ')
})

watch(currentRegroupList, (videos) => {
  selectedRegroupIndex.value = videos?.[0]?.regroup_index ?? 1
}, { immediate: true })

watch(
  () => [props.currentSegmentIndex, segmentList.value.length, props.currentVideoResult?.video_name],
  async () => {
    await nextTick()
    syncSegmentVideos()
  },
  { immediate: true }
)

function updateEditablePrompt(event) {
  const segment = props.currentSegment
  if (!segment) return
  ensureSegmentLocalState(segment)
  segment.edited_prompt = event.target.value
}

function handleFissionCountInput(event) {
  const segment = props.currentSegment
  if (!segment) return
  ensureSegmentLocalState(segment)
  segment.fission_count = clampFissionCount(event.target.value)
}

function addAddon() {
  const segment = props.currentSegment
  if (!segment || isAddonLimitReached.value) return
  ensureSegmentLocalState(segment)
  segment.prompt_addons.push(createAddonItem())
}

function removeAddon(addonId) {
  const segment = props.currentSegment
  if (!segment) return
  ensureSegmentLocalState(segment)
  const target = segment.prompt_addons.find((item) => item.id === addonId)
  if (target?.imagePreviewUrl) {
    URL.revokeObjectURL(target.imagePreviewUrl)
  }
  segment.prompt_addons = segment.prompt_addons.filter((item) => item.id !== addonId)
}

function handleImageChange(event, addonId) {
  const segment = props.currentSegment
  const file = event.target.files?.[0]
  if (!segment || !file) return
  ensureSegmentLocalState(segment)
  const target = segment.prompt_addons.find((item) => item.id === addonId)
  if (!target || !file.type.startsWith('image/')) {
    event.target.value = ''
    return
  }

  if (target.imagePreviewUrl) {
    URL.revokeObjectURL(target.imagePreviewUrl)
  }

  target.imageName = file.name
  target.imageFile = file
  target.imagePreviewUrl = URL.createObjectURL(file)
  event.target.value = ''
}

function updateAddonText(event, addonId) {
  const segment = props.currentSegment
  if (!segment) return
  ensureSegmentLocalState(segment)
  const target = segment.prompt_addons.find((item) => item.id === addonId)
  if (!target) return
  target.text = event.target.value
}

function addonIndexLabel(addonId) {
  const index = addonItems.value.findIndex((item) => item.id === addonId)
  return index >= 0 ? index + 1 : ''
}

function createAddonItem() {
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    imageName: '',
    imageFile: null,
    imagePreviewUrl: '',
    text: ''
  }
}

function canDeleteVariant(variant) {
  if (!variant) return false
  return !(currentVariantList.value.length === 1 && variant.variant_index === 0)
}

function variantLabel(variant) {
  return variant.variant_index === 0
    ? 'group_000 原片复制'
    : `group_${String(variant.variant_index).padStart(3, '0')}`
}

function fileName(filePath) {
  return (filePath || '').split('/').pop().split('\\').pop()
}

function formatDuration(seconds) {
  const value = Number(seconds)
  if (!Number.isFinite(value)) return '--'
  return `${value.toFixed(2)} 秒`
}

function setSegmentVideoRef(element, index) {
  if (element) {
    segmentVideoRefs.value[index] = element
  } else {
    segmentVideoRefs.value[index] = null
  }
}

function syncSegmentVideos() {
  segmentVideoRefs.value.forEach((videoElement, index) => {
    if (!videoElement) return
    const isActive = index === props.currentSegmentIndex
    videoElement.loop = true
    videoElement.autoplay = true
    videoElement.playsInline = true
    videoElement.muted = !isActive

    const playPromise = videoElement.play?.()
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch(() => {})
    }
  })
}
</script>
