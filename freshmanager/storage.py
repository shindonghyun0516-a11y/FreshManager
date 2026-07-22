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


class BatchReservationConflict(StorageError):
    """Raised when a Batch ID already has authoritative source evidence."""


class BatchReservationError(StorageError):
    """Raised when exclusive Batch ID ownership cannot be established safely."""


_BATCH_RESERVATION_TOKEN = object()


class BatchReservation:
    """Opaque proof that this process atomically created one Batch directory."""

    __slots__ = ("batch_directory", "_token")

    def __init__(self, batch_directory: Path, token: object) -> None:
        if token is not _BATCH_RESERVATION_TOKEN:
            raise BatchReservationError("batch_reservation_error")
        self.batch_directory = batch_directory
        self._token = token


def reserve_batch_directory(batch_directory: Path) -> BatchReservation:
    """Atomically reserve a new Batch ID and retain the directory on every exit path."""

    try:
        batch_directory.parent.mkdir(parents=True, exist_ok=True)
        batch_directory.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as error:
        raise BatchReservationConflict("batch_id_conflict") from error
    except OSError as error:
        raise BatchReservationError("batch_reservation_error") from error

    try:
        descriptor = os.open(batch_directory.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        # The directory remains authoritative evidence even if durability confirmation fails.
        raise BatchReservationError("batch_reservation_error") from error
    return BatchReservation(batch_directory, _BATCH_RESERVATION_TOKEN)


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


class BatchStorage:
    """Write one immutable collection log and manifest for a batch."""

    def __init__(self, reservation: BatchReservation) -> None:
        if (
            not isinstance(reservation, BatchReservation)
            or reservation._token is not _BATCH_RESERVATION_TOKEN
        ):
            raise BatchReservationError("batch_reservation_error")
        self.batch_directory = reservation.batch_directory

    @staticmethod
    def json_payload(document: Mapping[str, object]) -> bytes:
        return (json.dumps(dict(document), ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    def _save_json(self, filename: str, document: Mapping[str, object]) -> Path:
        path = self.batch_directory / filename
        FileStorage._write_exclusive(path, self.json_payload(document))
        return path

    def save_collection_log(self, document: Mapping[str, object]) -> Path:
        return self._save_json("collection_log.json", document)

    def save_manifest(self, document: Mapping[str, object]) -> Path:
        return self._save_json("manifest.json", document)
