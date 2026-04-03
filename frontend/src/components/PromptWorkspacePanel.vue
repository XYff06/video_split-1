<template>
  <section class="panel prompt-panel">
    <div class="prompt-panel-topbar">
      <div class="prompt-panel-copy">
        <h2>提示词反推</h2>
        <p class="panel-subtitle">
          当前片段的反推提示词支持直接修改，也可以在下方追加图片参考和补充指令。
        </p>
      </div>

      <div v-if="currentVideoResult && currentSegment" class="prompt-meta">
        <p>视频：{{ currentVideoResult.video_name }}</p>
        <p>片段：{{ currentSegment.group_index }} / {{ currentVideoResult.merged_segments.length }}</p>
        <p>状态：{{ analysisStatusText }}</p>
      </div>
    </div>

    <div class="prompt-control-board">
      <div class="prompt-control-grid" v-if="currentVideoResult && currentSegment">
        <div class="prompt-control-item prompt-control-row">
          <label class="prompt-control-text" for="fission-count">裂变视频数量</label>
          <input
            id="fission-count"
            class="fission-count-input"
            type="number"
            min="0"
            max="10"
            :value="fissionCount"
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
            @change="$emit('change-current-video-size', $event.target.value)"
          >
            <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </div>

        <div class="prompt-control-item">
          <button
            class="ghost-button fission-action-button"
            type="button"
            :disabled="isCurrentVideoFollowingGlobal"
            @click="$emit('reset-current-video-size')"
          >
            重置为跟随全局
          </button>
        </div>
      </div>

      <div v-else class="prompt-control-grid prompt-control-grid-empty">
        <div class="prompt-control-item prompt-control-row">
          <span class="prompt-control-text">裂变视频数量</span>
          <input class="fission-count-input" type="number" value="1" disabled />
        </div>

        <div class="prompt-control-item">
          <button class="primary-button fission-action-button" disabled>当前视频裂变</button>
        </div>

        <div class="prompt-control-item">
          <button class="ghost-button fission-action-button" disabled>全部视频裂变</button>
        </div>

        <div class="prompt-control-item prompt-control-row">
          <span class="prompt-control-text">全局 Size</span>
          <select class="size-select" disabled>
            <option>{{ globalSize }}</option>
          </select>
        </div>

        <div class="prompt-control-item prompt-control-row">
          <span class="prompt-control-text">当前视频 Size</span>
          <select class="size-select" disabled>
            <option>{{ globalSize }}</option>
          </select>
        </div>

        <div class="prompt-control-item">
          <button class="ghost-button fission-action-button" disabled>重置为跟随全局</button>
        </div>
      </div>
    </div>

    <p v-if="actionErrorMessage" class="error-text prompt-action-error">{{ actionErrorMessage }}</p>

    <div class="prompt-shell">
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
        <div class="prompt-editor-block">
          <label class="prompt-label" for="editable-prompt">片段提示词</label>
          <textarea
            id="editable-prompt"
            class="prompt-textarea"
            :value="editablePrompt"
            @input="updateEditablePrompt"
          />
          <p v-if="!basePrompt" class="hint-text">当前片段提示词还没有写入，等分析结果返回后会显示在这里。</p>
        </div>

        <div class="prompt-addon-toolbar compact">
          <button class="add-addon-button" type="button" :disabled="isAddonLimitReached" @click="addAddon">
            <span>+</span>
          </button>
          <p class="hint-text">最多 5 组补充组件，当前 {{ addonItems.length }} / 5。</p>
        </div>

        <div v-if="addonItems.length" class="prompt-addon-grid">
          <article v-for="item in addonItems" :key="item.id" class="prompt-addon-tile">
            <div class="prompt-addon-tile-header">
              <span class="prompt-addon-index">补充 {{ addonIndexLabel(item.id) }}</span>
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
              :id="`addon-text-${item.id}`"
              class="addon-textarea compact"
              :value="item.text"
              placeholder="例如：将 xx 替换成 xxx"
              @input="updateAddonText($event, item.id)"
            />
          </article>
        </div>

        <div v-if="isDeveloperMode" class="prompt-merged-preview">
          <h3>拼接结果预览</h3>
          <textarea class="prompt-textarea prompt-textarea-preview" :value="mergedPrompt" readonly />
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { clampFissionCount, composeSegmentGenerationPrompt, ensureSegmentLocalState } from '../utils/segmentPrompt'

const sizeOptions = ['1920*1080', '1080*1920', '1440*1440', '1632*1248', '1248*1632']

const props = defineProps({
  currentVideoResult: { type: Object, default: null },
  currentSegment: { type: Object, default: null },
  isGeneratingCurrentVideo: { type: Boolean, default: false },
  isGeneratingAllVideos: { type: Boolean, default: false },
  actionErrorMessage: { type: String, default: '' },
  globalSize: { type: String, default: '1920*1080' }
})

defineEmits([
  'generate-current-video',
  'generate-all-videos',
  'change-current-video-size',
  'change-global-size',
  'reset-current-video-size'
])

const isDeveloperMode = import.meta.env.DEV

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

const fissionCount = computed(() => {
  const segment = props.currentSegment
  if (!segment) return 1
  ensureSegmentLocalState(segment)
  return segment.fission_count
})

const isCurrentVideoFollowingGlobal = computed(() => props.currentVideoResult?.use_global_fission_size !== false)
const currentVideoSize = computed(() => props.currentVideoResult?.fission_size || props.globalSize)
const isAddonLimitReached = computed(() => addonItems.value.length >= 5)

const mergedPrompt = computed(() => {
  if (!props.currentSegment) return ''
  return composeSegmentGenerationPrompt(props.currentSegment)
})

const analysisStatusText = computed(() => {
  const status = props.currentSegment?.analysis_status
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
</script>
