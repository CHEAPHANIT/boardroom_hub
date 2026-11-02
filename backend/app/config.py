import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-boardroom-hub-dev-secret-key-2026")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "boardroom.db").replace("\\", "/")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(INSTANCE_DIR, "uploads"))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB per upload
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg", "txt"}
    ACCESS_TOKEN_TTL = timedelta(hours=2)
    REFRESH_TOKEN_TTL = timedelta(days=7)
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15
    LATE_THRESHOLD_MINUTES = 10      # joined more than 10 min after start = late
    EARLY_THRESHOLD_MINUTES = 10     # left more than 10 min before end = early departure
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    VIDEO_BASE_URL = os.environ.get("VIDEO_BASE_URL", "https://meet.jit.si")
    DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"  # show invite/reset links (no SMTP server)
    RESTX_MASK_SWAGGER = False
    RESTX_ERROR_404_HELP = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
