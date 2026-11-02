import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from .config import BASE_DIR, Config


def create_app(config_class=Config):
    app = Flask(__name__, instance_path=os.path.join(BASE_DIR, "instance"))
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from .extensions import db
    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}},
         expose_headers=["Content-Disposition"], supports_credentials=False)

    from .api import blueprint
    app.register_blueprint(blueprint)

    from .audit import register_hooks
    register_hooks(app)

    with app.app_context():
        from . import models  # noqa: F401
        from .audit import install_triggers
        db.create_all()
        install_triggers()

    from .seed import register_cli
    register_cli(app)

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(message="File is too large (max 10 MB)."), 413

    # Optional: serve the built Vue app (frontend/dist) from Flask for a one-server deployment.
    dist = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend", "dist"))

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path):
        if path.startswith("api/"):
            return jsonify(message="Not found"), 404
        if os.path.isdir(dist):
            full = os.path.join(dist, path)
            if path and os.path.isfile(full):
                return send_from_directory(dist, path)
            return send_from_directory(dist, "index.html")
        return jsonify(app="Boardroom Hub API", docs="/api/docs", health="/api/health")

    return app
