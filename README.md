# Video Split Demo (Vue 3 + Flask)

## 项目结构

- `frontend/`: Vue 3 组合式 API 前端。
- `backend/`: Flask 后端，包含场景检测、随机合法分组、视频导出。

## 后端启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

后端默认地址：`http://localhost:5000`

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:5173`

## 说明

1. 前端上传区支持：点击/拖拽、多文件、仅视频过滤、队列追加、去重、删除、展示更多弹窗、提交状态锁定。
2. 后端处理流程：PySceneDetect 默认检测 -> 6-14 秒随机合法分组（随机100次 + DFS回溯兜底）-> 导出合并片段。
3. 前端结果区支持：按视频分页切换 + 按片段前后切换 + 视频切换时片段索引重置。

> 运行导出功能依赖系统安装 `ffmpeg` 与 `ffprobe`。
