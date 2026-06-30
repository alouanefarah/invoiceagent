import io
import uuid
from datetime import timedelta

from minio import Minio
from app.core.config import settings

client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False,
)


def upload_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload fichier dans MinIO, retourne le minio_path (bucket/object-key)."""
    object_key = f"{uuid.uuid4()}/{filename}"
    client.put_object(
        settings.MINIO_BUCKET_RAW,
        object_key,
        io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )
    return f"{settings.MINIO_BUCKET_RAW}/{object_key}"


def get_file_bytes(minio_path: str) -> bytes:
    """Télécharge un fichier depuis MinIO et retourne ses bytes."""
    bucket, *parts = minio_path.split("/")
    object_key = "/".join(parts)
    response = client.get_object(bucket, object_key)
    data = response.read()
    response.close()
    response.release_conn()
    return data


# Alias pour compatibilité
download_file = get_file_bytes


def get_presigned_url(minio_path: str, expires_seconds: int = 3600) -> str:
    """Génère une URL signée pour accéder au fichier."""
    bucket, *parts = minio_path.split("/")
    object_key = "/".join(parts)
    return client.presigned_get_object(
        bucket, object_key, expires=timedelta(seconds=expires_seconds)
    )
