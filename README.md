# Video Upload -> Backend Split -> Frontend Preview Demo

## 1. Recommended directory structure

```text
video_split-1/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── app/
│   │   ├── server.py
│   │   ├── routes.py
│   │   ├── models/task_models.py
│   │   └── services/
│   │       ├── task_store.py
│   │       ├── task_processor.py
│   │       └── video_pipeline.py
│   └── storage/
│       ├── uploads/
│       ├── tasks/
│       └── exports/
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── styles.css
│       ├── services/api.js
│       └── components/
│           ├── UploadPanel.vue
│           ├── FileQueueModal.vue
│           └── ResultPanel.vue
└── README.md
```

## 2. Backend setup (Flask)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Backend runs at `http://localhost:5000`.

## 3. Frontend setup (Vue 3 + Composition API)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

## 4. API and flow

- `POST /api/tasks`
  - Accepts multi-video upload via `FormData(videos[])`
  - Saves files and returns `taskId` immediately.
- `GET /api/tasks/<taskId>`
  - Returns full task state + per-video status + per-video logs + result segments.
- `GET /media/<path>`
  - Serves generated segments so `<video :src="url">` can play directly.

Flow:
1. Frontend uploads batch.
2. Backend creates task and starts one background thread.
3. Backend serially processes each video (scene detect/split -> continuity fix -> DFS grouping -> ffmpeg merge).
4. Frontend polls every 1s and incrementally renders results.

## 5. Dependencies / runtime requirements

- Python 3.10+
- Node.js 18+
- ffmpeg installed and available in PATH
- PySceneDetect dependencies (opencv)

Ubuntu quick install for ffmpeg:

```bash
sudo apt update && sudo apt install -y ffmpeg
```

## 6. Notes

- This demo uses **task-based polling** (not websocket).
- Logs are isolated per video: UI shows only currently selected video logs.
- If one video fails, remaining videos continue.
