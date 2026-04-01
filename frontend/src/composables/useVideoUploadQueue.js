import { computed, ref } from 'vue'

/**
 * Upload queue state manager.
 *
 * What this composable does:
 * - Maintain a persistent file queue.
 * - Append new valid files instead of replacing old queue.
 * - Deduplicate by stable file signature.
 *
 * Why this design:
 * - Upload rules are non-trivial and reused by click-select and drag-drop paths.
 *
 * Result:
 * - Components receive clean queue APIs with guaranteed business constraints.
 */
export function useVideoUploadQueue() {
  const queuedVideoFiles = ref([])

  const visibleQueuedVideoFiles = computed(() => queuedVideoFiles.value.slice(0, 3))
  const hasMoreThanVisibleLimit = computed(() => queuedVideoFiles.value.length > 3)

  function createFileDeduplicationKey(fileObject) {
    return `${fileObject.name}_${fileObject.size}_${fileObject.lastModified}`
  }

  function appendFilesToQueue(candidateFileList) {
    const fileArray = Array.from(candidateFileList || [])
    const existingKeys = new Set(queuedVideoFiles.value.map((item) => item.deduplicationKey))

    fileArray.forEach((fileObject) => {
      const isVideoFile = fileObject.type.startsWith('video/')
      if (!isVideoFile) {
        return
      }

      const deduplicationKey = createFileDeduplicationKey(fileObject)
      if (existingKeys.has(deduplicationKey)) {
        return
      }

      queuedVideoFiles.value.push({
        deduplicationKey,
        file: fileObject,
        fileName: fileObject.name,
        fileSize: fileObject.size
      })
      existingKeys.add(deduplicationKey)
    })
  }

  function removeFileFromQueue(targetDeduplicationKey) {
    queuedVideoFiles.value = queuedVideoFiles.value.filter(
      (queuedItem) => queuedItem.deduplicationKey !== targetDeduplicationKey
    )
  }

  return {
    queuedVideoFiles,
    visibleQueuedVideoFiles,
    hasMoreThanVisibleLimit,
    appendFilesToQueue,
    removeFileFromQueue
  }
}
