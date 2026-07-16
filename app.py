"""
app.py — Flask Application Entry Point
Intelligent Fire & Gas Leak Detection System — AT Command Version
"""
from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from server.models.database import db, init_db
from server.routes.api      import api_bp
from server.routes.dashboard import dashboard_bp
import os


def create_app(config: dict = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="dashboard/templates",
        static_folder="dashboard/static",
    )

    app.config["SQLALCHEMY_DATABASE_URI"]        = os.getenv("DATABASE_URL", "sqlite:///detector.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"]                     = os.getenv("SECRET_KEY", "change-me")

    if config:
        app.config.update(config)

    db.init_app(app)
    app.register_blueprint(api_bp,       url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/")

    with app.app_context():
        init_db()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
