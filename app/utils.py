import os
import uuid
from urllib.parse import urlparse
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from flask import current_app


def allowed_file(filename):
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"])


def get_file_extension(filename):
    return filename.rsplit(".", 1)[1].lower() if filename and "." in filename else ""


def validate_image_content(filepath):
    try:
        Image.MAX_IMAGE_PIXELS = 16_000_000
        with Image.open(filepath) as img:
            img.verify()
        with Image.open(filepath) as img:
            width, height = img.size
            max_width, max_height = current_app.config["MAX_IMAGE_DIMENSIONS"]
            if width < 1 or height < 1 or width > max_width or height > max_height:
                return False
            detected = (img.format or "").lower()
            return detected in {"png", "jpeg", "gif", "webp"}
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return False


def save_uploaded_file(file, subfolder):
    if subfolder not in {"artists", "moments", "sponsors"}:
        raise ValueError("Dossier d'upload invalide")
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise ValueError("Type de fichier non autorisé")
    if file.mimetype not in current_app.config["ALLOWED_MIME_TYPES"]:
        raise ValueError("Type MIME non autorisé")

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size <= 0 or size > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("Fichier vide ou trop volumineux")

    extension = get_file_extension(file.filename)
    filename = f"{uuid.uuid4().hex}.{extension}"
    upload_path = Path(current_app.root_path) / current_app.config["UPLOAD_FOLDER"] / subfolder
    upload_path.mkdir(parents=True, exist_ok=True)
    filepath = upload_path / filename

    try:
        file.save(filepath)
        if not validate_image_content(filepath):
            filepath.unlink(missing_ok=True)
            raise ValueError("Fichier image invalide ou corrompu")
        try:
            os.chmod(filepath, 0o644)
        except OSError:
            pass
        return filename
    except ValueError:
        raise
    except Exception as exc:
        filepath.unlink(missing_ok=True)
        current_app.logger.exception("Erreur sauvegarde upload")
        raise ValueError("Erreur lors de la sauvegarde du fichier") from exc


def delete_uploaded_file(filename, subfolder):
    if not filename or subfolder not in {"artists", "moments", "sponsors"}:
        return
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return
    filepath = Path(current_app.root_path) / current_app.config["UPLOAD_FOLDER"] / subfolder / safe_name
    try:
        filepath.unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Erreur suppression upload")


def get_file_url(filename, subfolder):
    if not filename or subfolder not in {"artists", "moments", "sponsors"}: return None
    return f"/uploads/{subfolder}/{filename}"


def get_file_path(filename, subfolder):
    if not filename or subfolder not in {"artists", "moments", "sponsors"}: return None
    safe_name = os.path.basename(filename)
    if safe_name != filename: return None
    return str(Path(current_app.root_path) / current_app.config["UPLOAD_FOLDER"] / subfolder / safe_name)


def validate_http_url(value):
    if not value:
        return None
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL invalide: seuls http:// et https:// sont autorisés")
    if len(value) > 255:
        raise ValueError("URL trop longue")
    return value
