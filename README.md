# Video Upload -> Backend Split -> Frontend Preview Demo

## 1. Recommended project structure

```text
video_split-1/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── main.py
│   │   ├── services/
│   │   │   ├── grouping_service.py
│   │   │   ├── log_service.py
│   │   │   ├── scene_detect_service.py
│   │   │   ├── video_merge_service.py
│   │   │   └── video_processor_service.py
│   │   └── utils/
│   │       └── time_utils.py
│   ├── requirements.txt
│   ├── uploads/
│   └── processed/
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── App.vue
        ├── main.js
        ├── styles/main.css
        ├── services/videoProcessingApi.js
        ├── composables/useVideoUploadQueue.js
        └── components/
            ├── UploadPanel.vue
            ├── UploadQueueModal.vue
            └── ResultPanel.vue
```

## 2. Frontend component splitting

- `UploadPanel.vue`: upload interactions (click, drag-drop, queue preview, process button state).
- `UploadQueueModal.vue`: full queue popup with delete behavior.
- `ResultPanel.vue`: top video pager + bottom segment preview, plus failed list and logs.
- `useVideoUploadQueue.js`: reusable queue append/filter/deduplicate/remove logic.
- `videoProcessingApi.js`: pure API module for FormData submit.

## 3. Frontend core state design

In `App.vue`:
- `queuedVideoFiles`: full upload queue.
- `visibleQueuedVideoFiles`: first 3 queue items for main panel.
- `hasMoreThanVisibleLimit`: show/hide “展示更多”.
- `isQueueModalOpen`: popup visibility.
- `isProcessing`: submission lock + button “处理中”.
- `successfulVideos`, `failedVideos`, `processLogs`: processing result view model.
- `errorMessage`: request error display.

## 4. Flask API design

- `GET /api/health`: backend health.
- `POST /api/videos/process`:
  - Input field: `videos` (multiple files).
  - Per video pipeline:
    1) scene detect via PySceneDetect default params.
    2) random legal grouping (100 tries) -> DFS fallback.
    3) merge/export grouped clips.
  - Output:
    - `successful_videos`
    - `failed_videos`
    - `process_logs`
    - `log_file_path`
- `GET /processed/<path>`: serves generated merged videos for preview.

## 5. Run instructions

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

Backend runs on `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`.

## 6. Frontend-backend integration flow

1. Add files by click or drag-drop.
2. Queue logic filters non-video files, appends new ones, deduplicates repeats.
3. Click “开始处理” sends all queued files in one FormData request.
4. Backend handles each video independently, never stops all on single-video failure.
5. Frontend receives success list + failure list + logs and renders right-side result panel.
