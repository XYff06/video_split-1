# 视频上传 -> 后端切分 -> 前端预览 Demo

## 项目结构

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

## 前端组件

- `UploadPanel.vue`：负责点击选择、拖拽上传、队列预览和开始提交。
- `UploadFileList.vue`：负责上传文件卡片列表和单条删除操作。
- `FileQueueModal.vue`：负责展示完整上传队列弹窗。
- `ResultPanel.vue`：负责结果区容器、状态说明和当前视频结果展示。
- `VideoTabs.vue`：负责顶部视频分页切换条。
- `SegmentPreviewCard.vue`：负责片段播放器、空态和失败态展示。
- `LogPanel.vue`：负责单视频日志与任务总日志展示。

## 前端核心状态

- 上传文件队列
- 拖拽高亮状态
- 是否正在提交任务
- 当前任务 ID
- 当前任务总体状态
- 已完成数量 / 总数量
- SSE 增量返回的视频结果列表
- 当前选中的视频索引
- 当前选中的片段索引
- 上传错误信息
- SSE 连接状态
- 当前视频日志
- 任务总日志

## Flask 接口

- `POST /api/tasks`：接收多个视频文件，创建任务并启动后台处理。
- `GET /api/tasks/<task_id>/stream`：SSE 实时推送每个视频的处理结果。
- `GET /media/<path>`：提供上传原视频、原始场景片段、合并片段的静态访问。
- `GET /health`：健康检查接口。

## 后端处理流程

1. `detect_and_split_original_scenes`：使用 PySceneDetect 做场景检测并调用内置分割导出原始场景文件。
2. `search_valid_continuous_groupings`：基于有序原始片段做 DFS / 回溯 + 剪枝搜索。
3. `choose_final_grouping_plan`：从合法方案集合中打乱后随机选择一组最终方案。
4. `merge_grouped_scene_files`：使用 ffmpeg concat 合并原始场景文件，导出最终片段。

## 安装与启动

### 1. 安装 ffmpeg

- macOS：`brew install ffmpeg`
- Ubuntu / Debian：`sudo apt-get update && sudo apt-get install -y ffmpeg`
- Windows（Chocolatey）：`choco install ffmpeg`

### 2. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
python -m app.app
```

```bash
cd backend
pip install -r requirements.txt
python -m app.app
```

### 3. 启动前端

```bash
# 开发者模式
cd frontend
npm install
npm run dev
```

```bash
# 生产预览模式
cd frontend
npm install
npm run build
npm run preview
```

## 开发者模式说明

- 前端使用 Vite 的开发模式判断开发者模式。
- 当你执行 `npm run dev` 时，页面会显示开发调试信息，例如处理摘要、单视频日志、任务总日志、原始片段索引范围和导出本地文件路径。
- 当你执行生产构建或部署产物时，这些调试信息会自动隐藏，页面只保留普通用户需要的播放器和基础处理状态。

## 默认访问地址

- 前端：`http://127.0.0.1:5173`
- 后端 API：`http://127.0.0.1:5000`
- 媒体静态文件：`http://127.0.0.1:5000/media/...`

## 输出目录

- 上传原视频：`backend/data/uploads/<taskId>/`
- 原始场景片段：`backend/data/tasks/<taskId>/original_scenes/<video_name>/`
- 合并后的最终片段：`backend/data/tasks/<taskId>/merged_segments/<video_name>/`

## 联调验证方式

1. 先启动 Flask 后端，再启动前端开发服务器。
2. 在左侧上传区选择一个或多个本地视频。
3. 点击“开始处理”后，观察浏览器网络面板中的 SSE 连接是否持续打开。
4. 每处理完成一个视频，右侧结果区应立即出现对应结果，无论成功还是失败。
5. 点击成功视频后，能够直接播放合并后的片段文件。
6. 在开发模式下，可以继续查看当前视频日志、任务总日志和处理摘要是否增量更新。
