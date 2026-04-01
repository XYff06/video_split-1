<template>
  <div class="segment-layout">
    <button class="ghost-button" :disabled="!canPrev" @click="$emit('prev-segment')">上一片段</button>

    <div class="preview-card" v-if="videoResult">
      <template v-if="videoResult.status === 'success' && currentSegment">
        <video :src="currentSegment.export_public_url" controls class="preview-video" />
        <p>片段 {{ currentSegment.group_index }} / {{ videoResult.merged_segments.length }}</p>
        <p>时长：{{ currentSegment.duration_seconds.toFixed(3) }} 秒</p>
        <p>原始索引范围：{{ currentSegment.source_scene_index_range.join(' - ') }}</p>
        <p>导出文件：{{ currentSegment.export_file_path }}</p>
        <p class="status success">状态：{{ videoResult.status }}</p>
      </template>

      <template v-else-if="videoResult.status === 'failed'">
        <div class="empty-card error-card">该视频处理失败：{{ videoResult.error_message }}</div>
      </template>

      <template v-else>
        <div class="empty-card">该视频暂无可播放合并片段。</div>
      </template>
    </div>

    <div class="preview-card" v-else>
      <div class="empty-card">请先上传并处理视频，结果会实时出现在这里。</div>
    </div>

    <button class="ghost-button" :disabled="!canNext" @click="$emit('next-segment')">下一片段</button>
  </div>
</template>

<script setup>
defineProps({
  videoResult: { type: Object, default: null },
  currentSegment: { type: Object, default: null },
  canPrev: { type: Boolean, default: false },
  canNext: { type: Boolean, default: false }
})

defineEmits(['prev-segment', 'next-segment'])
</script>
