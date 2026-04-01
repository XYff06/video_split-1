/**
 * Centralized API module for backend communication.
 *
 * What this module does:
 * - Build FormData from current upload queue.
 * - Send one HTTP request for all queued videos.
 *
 * Why this design:
 * - Keep network logic out of UI components, so components stay focused on rendering.
 *
 * Result:
 * - Frontend gets normalized JSON from backend for success/failure/log display.
 */
export async function sendVideosForProcessing(videoFileQueue) {
  const formData = new FormData()
  videoFileQueue.forEach((videoFileItem) => {
    formData.append('videos', videoFileItem.file)
  })

  const response = await fetch('http://localhost:5000/api/videos/process', {
    method: 'POST',
    body: formData
  })

  const responseJson = await response.json()
  if (!response.ok) {
    throw new Error(responseJson.message || 'Video processing request failed.')
  }

  return responseJson
}
