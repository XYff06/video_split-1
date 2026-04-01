# Video Upload -> Backend Split -> Frontend Preview Demo

## Project Structure

```text
video_split-1/
├─ backend/
│  ├─ app/
│  │  ├─ app.py
│  │  └─ video_processing.py
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ components/
│  │  ├─ services/api.js
│  │  ├─ App.vue
│  │  ├─ main.js
│  │  └─ styles.css
│  ├─ index.html
│  ├─ package.json
│  └─ vite.config.js
└─ README.md
```

## Frontend Components

- `UploadPanel.vue`: handles click select, drag-drop, queue preview, start submit.
- `UploadFileList.vue`: card-style file list item UI and remove action.
- `FileQueueModal.vue`: full queue modal with mask and scroll body.
- `ResultPanel.vue`: right side result container + status + summary.
- `VideoTabs.vue`: top tab-like selector with previous/next page.
- `SegmentPreviewCard.vue`: merged segment player card and fail/empty card.
- `LogPanel.vue`: per-video log + task log with level colors.

## Core Frontend State

- upload queue, drag state, submitting state
- task id, task status, completed/total counters
- incremental result list from SSE
- selected video index + selected segment index
- upload error state + SSE connection status
- video logs + task logs

## Flask API

- `POST /api/tasks`: upload files, create task, spawn background worker.
- `GET /api/tasks/<task_id>/stream`: SSE endpoint that pushes one message per video completion.
- `GET /media/<path>`: serves uploaded/original split/merged files for video playback.
- `GET /health`: health check.

## Backend Processing Pipeline

1. `detect_and_split_original_scenes`: PySceneDetect detect + built-in split export.
2. `search_valid_continuous_groupings`: DFS/backtracking + pruning + max 2376 solutions.
3. `choose_final_grouping_plan`: shuffle then random pick a valid plan.
4. `merge_grouped_scene_files`: ffmpeg concat by selected groups.

## Dependencies and Setup

### 1) Install ffmpeg

- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y ffmpeg`
- Windows (choco): `choco install ffmpeg`

### 2) Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows use .venv\Scripts\activate
pip install -r requirements.txt
python -m app.app
```

### 3) Frontend setup

```bash
cd frontend
npm install
npm run dev
```

## Default Addresses

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:5000`
- Media static files: `http://127.0.0.1:5000/media/...`

## Output Directories

- Uploaded videos: `backend/data/uploads/<taskId>/`
- Original split scenes: `backend/data/tasks/<taskId>/original_scenes/<video_name>/`
- Merged final segments: `backend/data/tasks/<taskId>/merged_segments/<video_name>/`

## End-to-End Validation

1. Start backend + frontend.
2. Upload multiple local videos in left panel.
3. Click start and open browser network: SSE stream should keep open.
4. Every finished video appears immediately in right tabs (success/failed both shown).
5. Click a successful video and play merged segment directly via `<video>`.
6. Verify per-video logs and task logs update incrementally.
