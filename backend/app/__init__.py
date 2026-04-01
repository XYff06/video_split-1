from flask import Flask
from flask_cors import CORS

from app.config import ApplicationConfig
from app.routes import api_blueprint, configure_routes
from app.services.video_processing_service import VideoProcessingService
from app.utils.file_utils import ensure_directory_exists


def create_app() -> Flask:
    """
    创建 Flask 应用。

    做了什么：初始化目录、注册 CORS、注册路由和处理服务。
    为什么这样做：把启动逻辑集中化，便于调试和后续扩展。
    结果：得到可直接运行的 Flask 应用实例。
    """
    app = Flask(__name__)
    app.config.from_object(ApplicationConfig)

    ensure_directory_exists(ApplicationConfig.UPLOAD_DIRECTORY)
    ensure_directory_exists(ApplicationConfig.PROCESSED_DIRECTORY)

    CORS(app, resources={r"/api/*": {"origins": ApplicationConfig.CORS_ORIGINS}})

    processing_service = VideoProcessingService(
        upload_directory=ApplicationConfig.UPLOAD_DIRECTORY,
        processed_directory=ApplicationConfig.PROCESSED_DIRECTORY,
        media_url_prefix=ApplicationConfig.STATIC_URL_PREFIX,
    )
    configure_routes(processing_service, ApplicationConfig.PROCESSED_DIRECTORY)

    app.register_blueprint(api_blueprint, url_prefix="/api")
    return app
