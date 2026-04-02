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

const isAddonLimitReached = computed(() => addonItems.value.length >= 5)

const mergedPrompt = computed(() => {
  const segment = props.currentSegment
  if (!segment) return ''
  initializeSegmentEditorState(segment)

  const originalReversePrompt = segment.edited_prompt.trim()
  const userReplaceInstruction = segment.prompt_addons
    .map((item) => item.text.trim())
    .filter(Boolean)
    .join('\n')

  if (!originalReversePrompt) {
    return ''
  }

  if (!userReplaceInstruction) {
    return originalReversePrompt
  }

  return [
    originalReversePrompt,
    '',
    '在保留原视频整体镜头结构、场景切换顺序、动作逻辑、情绪推进、人物关系和视觉质感的前提下，执行以下替换:',
    userReplaceInstruction,
    '',
    '参考图片使用规则:',
    '1. 参考图仅用于我明确指定的替换目标',
    '2. 只参考指定属性，不要自动继承图片里的背景、构图、光线、姿势或其他无关元素',
    '3. 未明确要求替换的内容全部保持原反推提示词设定',
    '4. 保持同一角色在所有镜头中的外观一致',
    '5. 不要破坏原有动作衔接、台词情绪和镜头节奏'
  ].join('\n')
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

function updateEditablePrompt(event) {
  const segment = props.currentSegment
  if (!segment) return
  initializeSegmentEditorState(segment)
  segment.edited_prompt = event.target.value
}

function addAddon() {
  const segment = props.currentSegment
  if (!segment || isAddonLimitReached.value) return
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
</script>
