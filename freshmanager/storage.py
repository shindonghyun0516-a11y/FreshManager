"""Non-overwriting raw-response and metadata storage for EG-4."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Mapping


class StorageError(OSError):
    """Raised when an approved output cannot be stored safely."""


class FileStorage:
    """Write one immutable raw file and one metadata JSON per request."""

    def __init__(self, raw_root: Path, metadata_root: Path) -> None:
        self.raw_root = raw_root
        self.metadata_root = metadata_root

    @staticmethod
    def _request_stem(area_code: str, requested_at: datetime, request_id: str) -> str:
        timestamp = requested_at.strftime("%Y%m%d_%H%M%S")
        return f"{area_code}_{timestamp}_{request_id}"

    @staticmethod
    def _dated_directory(root: Path, requested_at: datetime) -> Path:
        return root / requested_at.strftime("%Y") / requested_at.strftime("%m") / requested_at.strftime("%d")

    @staticmethod
    def _write_exclusive(path: Path, payload: bytes) -> None:
        partial_path: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, partial_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".partial",
                dir=path.parent,
            )
            partial_path = Path(partial_name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(partial_path, path)
        except FileExistsError as error:
            raise StorageError("storage_error: 기존 파일과 충돌") from error
        except OSError as error:
            raise StorageError("storage_error: 파일 저장 실패") from error
        finally:
            if partial_path is not None:
                try:
                    partial_path.unlink()
                except OSError:
                    pass

    def save_raw(self, area_code: str, requested_at: datetime, request_id: str, payload: bytes) -> Path:
        stem = self._request_stem(area_code, requested_at, request_id)
        path = self._dated_directory(self.raw_root, requested_at) / f"{stem}.json"
        self._write_exclusive(path, payload)
        return path

    def save_metadata(self, requested_at: datetime, request_id: str, metadata: Mapping[str, object]) -> Path:
        area_code = str(metadata["area_code"])
        stem = self._request_stem(area_code, requested_at, request_id)
        path = self._dated_directory(self.metadata_root, requested_at) / f"{stem}.metadata.json"
        payload = (json.dumps(dict(metadata), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        self._write_exclusive(path, payload)
        return path
