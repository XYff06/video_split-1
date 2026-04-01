from pathlib import Path


class ApplicationConfig:
    """集中管理后端运行时配置，避免魔法字符串分散在业务代码里。"""

    # 这里定义项目根目录，目的是让上传目录、输出目录都使用绝对路径，避免相对路径在不同启动目录下出错。
    # 这样做的结果是：无论从哪里启动 Flask，文件读写位置都稳定可控。
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    # 上传目录用于保存前端发送的原始视频文件。
    UPLOAD_DIRECTORY = PROJECT_ROOT / "backend" / "uploads"

    # 处理目录用于保存 PySceneDetect 切分出的原始场景片段和最终合并片段。
    PROCESSED_DIRECTORY = PROJECT_ROOT / "backend" / "processed"

    # Flask 的静态访问前缀，用于让前端直接访问处理输出视频。
    STATIC_URL_PREFIX = "/media"

    # 当前 Demo 允许的跨域来源；开发阶段使用 Vue 默认端口。
    CORS_ORIGINS = ["http://localhost:5173"]
