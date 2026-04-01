import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from app.routes import api_blueprint


def create_app() -> Flask:
    """Create Flask application and register routes.

    We keep all app initialization in one place so future scaling (factory pattern,
    testing config, different environments) is straightforward.
    """

    app = Flask(__name__)
    CORS(app)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    storage_root = os.path.join(project_root, "storage")
    app.config["UPLOAD_FOLDER"] = os.path.join(storage_root, "uploads")
    app.config["TASK_FOLDER"] = os.path.join(storage_root, "tasks")
    app.config["EXPORT_FOLDER"] = os.path.join(storage_root, "exports")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["TASK_FOLDER"], exist_ok=True)
    os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)

    app.register_blueprint(api_blueprint, url_prefix="/api")

    @app.get("/media/<path:filename>")
    def serve_media(filename: str):
        """Expose generated files to frontend video tag playback.

        Why: Browser video players need an HTTP URL. Returning file paths alone is
        not sufficient. This endpoint converts exported files into playable URLs.
        """
        return send_from_directory(storage_root, filename, as_attachment=False)

    return app
