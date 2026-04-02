<template>
  <div class="segment-layout">
    <button class="ghost-button segment-side-button" :disabled="!canPrev" @click="$emit('prev-segment')">
      上一片段
    </button>

    <div class="preview-card">
      <template v-if="videoResult">
        <template v-if="currentSegment">
          <div class="preview-video-shell">
            <video :src="currentSegment.export_public_url" controls class="preview-video" />
          </div>
          <div class="preview-info">
            <p>片段 {{ currentSegment.group_index }} / {{ videoResult.merged_segments.length }}</p>
            <p>时长：{{ currentSegment.duration_seconds.toFixed(3) }} 秒</p>
            <p v-if="isDeveloperMode">原始索引范围：{{ currentSegment.source_scene_index_range.join(' - ') }}</p>
            <p v-if="isDeveloperMode" class="preview-path">导出文件：{{ currentSegment.export_file_path }}</p>
            <p class="status" :class="videoResult.status === 'failed' ? 'error' : 'success'">状态：{{ videoResult.status }}</p>
          </div>
        </template>

        <template v-else-if="videoResult.status === 'failed'">
          <div class="preview-video-shell">
            <div class="empty-card error-card">该视频处理失败：{{ videoResult.error_message }}</div>
          </div>
        </template>

        <template v-else>
          <div class="preview-video-shell">
            <div class="empty-card">该视频暂时没有可播放的合并片段。</div>
          </div>
        </template>
      </template>

      <template v-else>
        <div class="preview-video-shell">
          <div class="empty-card">请先上传并处理视频，结果会实时出现在这里。</div>
        </div>
      </template>
    </div>

    <button class="ghost-button segment-side-button" :disabled="!canNext" @click="$emit('next-segment')">
      下一片段
    </button>
  </div>
</template>

<script setup>
const isDeveloperMode = import.meta.env.DEV

defineProps({
  videoResult: { type: Object, default: null },
  currentSegment: { type: Object, default: null },
  canPrev: { type: Boolean, default: false },
  canNext: { type: Boolean, default: false }
})

defineEmits(['prev-segment', 'next-segment'])
</script>
