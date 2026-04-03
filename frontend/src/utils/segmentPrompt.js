export function ensureSegmentLocalState(segment) {
  if (!segment) return null

  if (typeof segment.edited_prompt !== 'string' || (!segment.edited_prompt && segment.analysis?.prompt)) {
    segment.edited_prompt = segment.analysis?.prompt || ''
  }

  if (!Array.isArray(segment.prompt_addons)) {
    segment.prompt_addons = []
  }

  if (typeof segment.fission_count !== 'number' || Number.isNaN(segment.fission_count)) {
    segment.fission_count = 1
  }

  return segment
}

export function clampFissionCount(value) {
  const parsed = Number.parseInt(value, 10)
  if (Number.isNaN(parsed)) return 1
  return Math.max(0, Math.min(10, parsed))
}

export function composeSegmentGenerationPrompt(segment) {
  ensureSegmentLocalState(segment)

  const originalReversePrompt = segment.edited_prompt.trim()
  const userReplaceInstruction = segment.prompt_addons
    .map((item) => item.text?.trim?.() || '')
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
}

export function mergeVideoResultsWithLocalState(nextVideoResults, previousVideoResults = []) {
  return (nextVideoResults || []).map((videoResult, videoIndex) => {
    const previousVideoResult = previousVideoResults[videoIndex]
    if (!Array.isArray(videoResult?.merged_segments)) {
      return videoResult
    }

    return {
      ...videoResult,
      merged_segments: videoResult.merged_segments.map((segment, segmentIndex) => {
        const previousSegment = previousVideoResult?.merged_segments?.[segmentIndex]
        const previousEditedPrompt = typeof previousSegment?.edited_prompt === 'string'
          ? previousSegment.edited_prompt
          : undefined
        const nextEditedPrompt = typeof segment.edited_prompt === 'string'
          ? segment.edited_prompt
          : (segment.analysis?.prompt || '')
        return {
          ...segment,
          edited_prompt: previousEditedPrompt && previousEditedPrompt.trim()
            ? previousEditedPrompt
            : nextEditedPrompt,
          prompt_addons: previousSegment?.prompt_addons ?? segment.prompt_addons ?? [],
          fission_count: typeof previousSegment?.fission_count === 'number'
            ? previousSegment.fission_count
            : (typeof segment.fission_count === 'number' ? segment.fission_count : 1)
        }
      })
    }
  })
}
