"""后端路径与公共访问地址配置。

这个模块只定义全局常量，供整个后端统一复用：
1. `BACKEND_ROOT`：后端项目根目录。
2. `DATA_ROOT`：所有运行时数据的总目录。
3. `UPLOAD_ROOT`：用户上传视频的保存目录。
4. `TASK_OUTPUT_ROOT`：任务处理产物的输出目录。
5. `BASE_PUBLIC_URL`：前端访问媒体文件时使用的服务基地址。
"""

from pathlib import Path


# `__file__` 指向当前文件，向上回退两级后就是 backend 根目录。
BACKEND_ROOT = Path(__file__).resolve().parent.parent
# `data` 目录统一存放上传文件、处理中间产物和最终输出。
DATA_ROOT = BACKEND_ROOT / "data"
# 原始上传文件目录，按 task_id 继续细分子目录。
UPLOAD_ROOT = DATA_ROOT / "uploads"
# 每个任务的输出目录，例如切分片段、重组结果、生成视频等。
TASK_OUTPUT_ROOT = DATA_ROOT / "tasks"
# 媒体预览 URL 的前缀，前端通过它拼出可直接访问的视频地址。
BASE_PUBLIC_URL = "http://127.0.0.1:5000"
