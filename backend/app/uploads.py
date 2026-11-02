"""Safe file upload helpers (type and size checks, random stored names)."""
import hashlib
import os
import uuid

from flask import current_app, request
from flask_restx import abort
from werkzeug.utils import secure_filename


def save_upload(subdir, field="file"):
    f = request.files.get(field)
    if not f or not f.filename:
        abort(400, "Choose a file to upload.")
    original = secure_filename(f.filename) or "file"
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
        abort(400, f"File type .{ext or '?'} is not allowed. Allowed: "
                   f"{', '.join(sorted(current_app.config['ALLOWED_EXTENSIONS']))}.")
    data = f.read()
    if not data:
        abort(400, "The file is empty.")
    if len(data) > current_app.config["MAX_CONTENT_LENGTH"]:
        abort(413, "File is too large (max 10 MB).")
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subdir)
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(folder, stored), "wb") as out:
        out.write(data)
    return {"filename": original, "stored_name": f"{subdir}/{stored}", "mime": f.mimetype or "application/octet-stream",
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def upload_path(stored_name):
    return os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
