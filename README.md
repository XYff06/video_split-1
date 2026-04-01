# Video Upload → Backend Split → Frontend Preview Demo

一个完整可运行的 Demo：
- 前端：Vue 3 + 组合式 API
- 后端：Flask + PySceneDetect
- 支持多视频上传、真实场景切分、连续片段随机合法分组、合并导出与前端预览。

## 1. 项目目录结构

```text
video_split-1/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── routes.py
│   │   ├── services/
│   │   │   └── video_processing_service.py
│   │   └── utils/
│   │       └── file_utils.py
│   ├── processed/               # 处理输出目录（运行后生成内容）
│   ├── uploads/                 # 上传缓存目录
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── api/
│       │   └── videoApi.js
│       ├── components/
│       │   ├── QueueModal.vue
│       │   ├── ResultPanel.vue
│       │   └── UploadPanel.vue
│       ├── App.vue
│       ├── main.js
│       └── styles.css
└── README.md
```

## 2. 前端组件拆分方案

- `App.vue`
  - 页面顶层布局和核心状态管理（上传队列、处理中、成功结果、失败结果、日志）。
- `UploadPanel.vue`
  - 上传区：点击选择、拖拽上传、文件过滤、去重、删除、提交按钮状态。
- `QueueModal.vue`
  - “展示更多”弹窗：完整队列查看与删除。
- `ResultPanel.vue`
  - 结果区四层结构：标题状态、视频切换条、片段预览区、日志区。
- `videoApi.js`
  - 统一封装接口调用和媒体 URL 拼接。

## 3. Flask 接口设计

- `GET /api/health`
  - 健康检查。
- `POST /api/process-videos`
  - 接收多视频 `files` 字段。
  - 对每个视频独立处理，返回：
    - `successful_videos`
    - `failed_videos`
    - `processing_logs`
- `GET /api/media/<path>`
  - 提供处理后视频文件的静态访问。

## 4. 后端处理流程（关键逻辑）

`VideoProcessingService` 的单视频处理分 3 步：

1. `detect_and_split_original_scenes`
   - 使用 PySceneDetect 默认 `ContentDetector()` 检测场景。
   - 立即调用 `split_video_ffmpeg` 输出真实原始场景文件。
2. `create_random_valid_continuous_groups`
   - 先做无解预检查。
   - 随机尝试最多 100 次。
   - 失败后使用 DFS/回溯+剪枝收集合法方案并随机选取。
3. `merge_grouped_scene_files`
   - 按分组用 ffmpeg concat 合并片段。
   - 返回每个合并片段的完整元信息和前端可播放 URL。

## 5. 依赖安装

> 需要系统已安装 `ffmpeg`（命令行可直接使用）。

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 前端

```bash
cd frontend
npm install
```

## 6. 运行方式（前后端联调）

### 启动后端

```bash
cd backend
source .venv/bin/activate
python run.py
```

后端默认：`http://localhost:5000`

### 启动前端

```bash
cd frontend
npm run dev
```

前端默认：`http://localhost:5173`

打开前端页面后：
1. 在左侧拖拽/选择多个视频；
2. 点击“开始处理”；
3. 右侧查看视频切换、片段预览、摘要与日志。

## 7. 错误处理与扩展点

- 已实现跨域（Flask-CORS）。
- 已实现多视频独立处理，单视频失败不影响其他视频。
- 已实现前端错误提示、禁用态、空态、处理中状态。
- 代码结构已分层，后续新增“片段反推提示词”建议新增：
  - `backend/app/services/prompt_generation_service.py`
  - `frontend/src/components/PromptPanel.vue`
