from pathlib import Path
import uuid
from fastapi import UploadFile, HTTPException, status

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media" / "users"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 097 152 байт
EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

async def save_user_image(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPG, PNG or WebP images are allowed")

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image is too large")

    # Расширение на основе MIME-типа
    extension = EXTENSION_MAP.get(file.content_type, ".jpg")
    file_name = f"{uuid.uuid4().hex}{extension}"
    file_path = MEDIA_ROOT / file_name
    file_path.write_bytes(content)

    return f"/media/users/{file_name}"

def remove_user_image(url: str | None) -> None:
    """
    Удаляет файл изображения, если он существует.
    """
    if not url or url == "/media/default_avatar.webp":
        return
    relative_path = url.lstrip("/")
    file_path = BASE_DIR / relative_path
    if file_path.exists():
        file_path.unlink()