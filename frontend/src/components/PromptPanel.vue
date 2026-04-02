<template>
  <section class="panel prompt-panel">
    <div class="prompt-panel-header">
      <div>
        <h2>提示词反推</h2>
        <p class="panel-subtitle">
          永久显示当前选中视频与片段的导演式提示词，可随上方视频和片段切换同步查看。
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

      <template v-else-if="currentSegment.analysis_status === 'completed' && currentSegment.analysis?.prompt">
        <textarea
          class="prompt-textarea"
          :value="currentSegment.analysis.prompt"
          readonly
        />
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
        <div class="prompt-empty">当前片段提示词正在生成中，请稍候。</div>
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

const analysisStatusText = computed(() => {
  const status = props.currentSegment?.analysis_status
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'skipped') return '已跳过'
  if (status === 'pending') return '待生成'
  return '生成中'
})
</script>
