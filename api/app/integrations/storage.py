from typing import Protocol, runtime_checkable

from minio import Minio


@runtime_checkable
class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def presigned_url(self, key: str, expires: int = 3600) -> str: ...


class MinioStorage:
    """S3 兼容对象存储（MinIO）。键形如 {kb_id}/{source_id}/{filename}。"""

    def __init__(
        self, *, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool
    ) -> None:
        self.bucket = bucket
        self._client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        import io

        self._client.put_object(
            self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )

    def get(self, key: str) -> bytes:
        resp = self._client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        from datetime import timedelta

        return self._client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires)
        )
