<template>
  <section class="panel prompt-panel">
    <div class="prompt-panel-header">
      <div>
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

      <template v-else-if="!basePrompt">
        <div class="prompt-empty">当前片段提示词正在生成中，请稍候。</div>
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
        </div>

        <div class="prompt-addon-toolbar">
          <button class="add-addon-button" type="button" @click="addAddon">
            <span>+</span>
          </button>
          <p class="hint-text">点击加号添加一组图片参考和补充指令。</p>
        </div>

        <div v-if="addonItems.length" class="prompt-addon-list">
          <article v-for="item in addonItems" :key="item.id" class="prompt-addon-card">
            <div class="prompt-addon-card-header">
              <h3>补充组件 {{ addonIndexLabel(item.id) }}</h3>
              <button class="danger-button prompt-addon-delete" type="button" @click="removeAddon(item.id)">
                删除
              </button>
            </div>

            <label class="prompt-label">图片上传</label>
            <label class="addon-upload-box" :for="`addon-upload-${item.id}`">
              <input
                :id="`addon-upload-${item.id}`"
                class="hidden"
                type="file"
                accept="image/*"
                @change="handleImageChange($event, item.id)"
              />
              <template v-if="item.imagePreviewUrl">
                <img :src="item.imagePreviewUrl" alt="参考图预览" class="addon-preview-image" />
                <span class="addon-upload-meta">{{ item.imageName }}</span>
              </template>
              <template v-else>
                <span class="addon-upload-title">点击上传图片或拖拽到此处</span>
                <span class="hint-text">仅支持一张图片</span>
              </template>
            </label>

            <label class="prompt-label" :for="`addon-text-${item.id}`">补充指令</label>
            <textarea
              :id="`addon-text-${item.id}`"
              class="addon-textarea"
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

const props = defineProps({
  currentVideoResult: { type: Object, default: null },
  currentSegment: { type: Object, default: null }
})

const isDeveloperMode = import.meta.env.DEV

const basePrompt = computed(() => props.currentSegment?.analysis?.prompt?.trim?.() || '')

const editablePrompt = computed(() => {
  const segment = props.currentSegment
  if (!segment) return ''
  initializeSegmentEditorState(segment)
  return segment.edited_prompt
})

const addonItems = computed(() => {
  const segment = props.currentSegment
  if (!segment) return []
  initializeSegmentEditorState(segment)
  return segment.prompt_addons
})

const mergedPrompt = computed(() => {
  const segment = props.currentSegment
  if (!segment) return ''
  initializeSegmentEditorState(segment)

  const textParts = [
    segment.edited_prompt.trim(),
    ...segment.prompt_addons
      .map((item) => item.text.trim())
      .filter(Boolean)
  ].filter(Boolean)

  return textParts.join('\n\n')
})

const analysisStatusText = computed(() => {
  const status = props.currentSegment?.analysis_status
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'skipped') return '已跳过'
  if (status === 'pending') return '待生成'
  return '生成中'
})

function initializeSegmentEditorState(segment) {
  if (typeof segment.edited_prompt !== 'string') {
    segment.edited_prompt = segment.analysis?.prompt || ''
  }

  if (!Array.isArray(segment.prompt_addons)) {
    segment.prompt_addons = []
  }
}

function syncPromptIfNeeded(segment) {
  if (
    typeof segment.edited_prompt === 'string' &&
    typeof segment.analysis?.prompt === 'string' &&
    segment.edited_prompt.trim() === ''
  ) {
    segment.edited_prompt = segment.analysis.prompt
  }
}

function updateEditablePrompt(event) {
  const segment = props.currentSegment
  if (!segment) return
  initializeSegmentEditorState(segment)
  segment.edited_prompt = event.target.value
}

function addAddon() {
  const segment = props.currentSegment
  if (!segment) return
  initializeSegmentEditorState(segment)
  segment.prompt_addons.push(createAddonItem())
}

function removeAddon(addonId) {
  const segment = props.currentSegment
  if (!segment) return
  initializeSegmentEditorState(segment)
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
  initializeSegmentEditorState(segment)

  const target = segment.prompt_addons.find((item) => item.id === addonId)
  if (!target) return

  if (!file.type.startsWith('image/')) {
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
  initializeSegmentEditorState(segment)
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

if (props.currentSegment) {
  initializeSegmentEditorState(props.currentSegment)
  syncPromptIfNeeded(props.currentSegment)
}
</script>
