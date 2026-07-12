from flask import Flask
from flask_cors import CORS


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)

    from app.api.chat import chat_bp
    from app.api.upload import upload_bp

    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(upload_bp, url_prefix="/api/upload")

    return app
