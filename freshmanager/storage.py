"""Non-overwriting raw-response and metadata storage for EG-4."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Mapping

from .batch_id import BatchIdValidationError, canonical_batch_id


class StorageError(OSError):
    """Raised when an approved output cannot be stored safely."""


class BatchReservationConflict(StorageError):
    """Raised when a Batch ID already has authoritative source evidence."""


class BatchReservationError(StorageError):
    """Raised when exclusive Batch ID ownership cannot be established safely."""


_BATCH_RESERVATION_TOKEN = object()


class BatchReservation:
    """Opaque proof that this process owns one exact filesystem directory."""

    __slots__ = (
        "_batch_directory",
        "_batch_id",
        "_device",
        "_directory_fd",
        "_inode",
        "_token",
    )

    def __init__(
        self,
        batch_directory: Path,
        batch_id: str,
        device: int,
        inode: int,
        directory_fd: int,
        token: object,
    ) -> None:
        if token is not _BATCH_RESERVATION_TOKEN:
            raise BatchReservationError("batch_reservation_error")
        self._batch_directory = batch_directory
        self._batch_id = batch_id
        self._device = device
        self._inode = inode
        self._directory_fd = directory_fd
        self._token = token

    @property
    def batch_directory(self) -> Path:
        return self._batch_directory

    @property
    def batch_id(self) -> str:
        return self._batch_id

    def verify_identity(self) -> None:
        """Fail closed unless the reserved pathname still names the created directory."""

        if self._token is not _BATCH_RESERVATION_TOKEN or self._directory_fd < 0:
            raise BatchReservationError("batch_reservation_integrity_error")
        try:
            descriptor_stat = os.fstat(self._directory_fd)
            path_stat = os.lstat(self._batch_directory)
        except OSError as error:
            raise BatchReservationError("batch_reservation_integrity_error") from error
        expected_identity = (self._device, self._inode)
        if (
            not stat.S_ISDIR(descriptor_stat.st_mode)
            or not stat.S_ISDIR(path_stat.st_mode)
            or (descriptor_stat.st_dev, descriptor_stat.st_ino) != expected_identity
            or (path_stat.st_dev, path_stat.st_ino) != expected_identity
            or self._batch_directory.name != self._batch_id
        ):
            raise BatchReservationError("batch_reservation_integrity_error")

    def probe_existing_directory(self, prefix: str, payload: bytes) -> None:
        """Probe the owned directory through its descriptor without recreating its path."""

        self.verify_identity()
        probe_name = f"{prefix}{uuid.uuid4().hex}.probe"
        try:
            descriptor = os.open(
                probe_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=self._directory_fd,
            )
            with os.fdopen(descriptor, "wb") as probe:
                probe.write(payload)
                probe.flush()
                os.fsync(probe.fileno())
            self.verify_identity()
        except BatchReservationError:
            raise
        except OSError as error:
            raise BatchReservationError("batch_reservation_integrity_error") from error
        finally:
            try:
                os.unlink(probe_name, dir_fd=self._directory_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        self.verify_identity()

    def write_exclusive(self, filename: str, payload: bytes) -> Path:
        """Atomically publish a file inside the owned directory without path recreation."""

        if not filename or Path(filename).name != filename:
            raise BatchReservationError("batch_reservation_integrity_error")
        self.verify_identity()
        partial_name = f".{filename}.{uuid.uuid4().hex}.partial"
        try:
            descriptor = os.open(
                partial_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=self._directory_fd,
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            self.verify_identity()
            os.link(
                partial_name,
                filename,
                src_dir_fd=self._directory_fd,
                dst_dir_fd=self._directory_fd,
                follow_symlinks=False,
            )
            self.verify_identity()
        except FileExistsError as error:
            raise StorageError("storage_error: 기존 파일과 충돌") from error
        except BatchReservationError:
            raise
        except OSError as error:
            raise StorageError("storage_error: 파일 저장 실패") from error
        finally:
            try:
                os.unlink(partial_name, dir_fd=self._directory_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        return self._batch_directory / filename

    def close(self) -> None:
        """Release only the in-process descriptor; never delete reservation evidence."""

        descriptor = self._directory_fd
        if descriptor < 0:
            return
        self._directory_fd = -1
        try:
            os.close(descriptor)
        except OSError:
            pass


def reserve_batch_directory(batch_directory: Path) -> BatchReservation:
    """Atomically reserve a new Batch ID and retain the directory on every exit path."""

    try:
        batch_id = canonical_batch_id(batch_directory.name)
    except BatchIdValidationError as error:
        raise BatchReservationError("batch_reservation_error") from error
    try:
        batch_directory.parent.mkdir(parents=True, exist_ok=True)
        batch_directory.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as error:
        raise BatchReservationConflict("batch_id_conflict") from error
    except OSError as error:
        raise BatchReservationError("batch_reservation_error") from error

    directory_fd = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(batch_directory, flags)
        directory_stat = os.fstat(directory_fd)
        path_stat = os.lstat(batch_directory)
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or not stat.S_ISDIR(path_stat.st_mode)
            or (directory_stat.st_dev, directory_stat.st_ino)
            != (path_stat.st_dev, path_stat.st_ino)
        ):
            raise BatchReservationError("batch_reservation_integrity_error")
        parent_descriptor = os.open(batch_directory.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except BatchReservationError:
        if directory_fd >= 0:
            os.close(directory_fd)
        raise
    except OSError as error:
        if directory_fd >= 0:
            os.close(directory_fd)
        # The directory remains authoritative evidence even if durability confirmation fails.
        raise BatchReservationError("batch_reservation_error") from error
    return BatchReservation(
        batch_directory,
        batch_id,
        directory_stat.st_dev,
        directory_stat.st_ino,
        directory_fd,
        _BATCH_RESERVATION_TOKEN,
    )


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


class ReservationAwareFileStorage(FileStorage):
    """Guard EG-6B Raw and Metadata writes with the active Batch reservation."""

    def __init__(self, delegate: FileStorage, reservation: BatchReservation) -> None:
        reservation.verify_identity()
        super().__init__(delegate.raw_root, delegate.metadata_root)
        self._delegate = delegate
        self._reservation = reservation

    def save_raw(self, area_code: str, requested_at: datetime, request_id: str, payload: bytes) -> Path:
        self._reservation.verify_identity()
        path = self._delegate.save_raw(area_code, requested_at, request_id, payload)
        self._reservation.verify_identity()
        return path

    def save_metadata(self, requested_at: datetime, request_id: str, metadata: Mapping[str, object]) -> Path:
        self._reservation.verify_identity()
        path = self._delegate.save_metadata(requested_at, request_id, metadata)
        self._reservation.verify_identity()
        return path


class BatchStorage:
    """Write one immutable collection log and manifest for a batch."""

    def __init__(self, reservation: BatchReservation) -> None:
        if (
            not isinstance(reservation, BatchReservation)
            or reservation._token is not _BATCH_RESERVATION_TOKEN
        ):
            raise BatchReservationError("batch_reservation_error")
        reservation.verify_identity()
        self._reservation = reservation

    @property
    def batch_directory(self) -> Path:
        return self._reservation.batch_directory

    @staticmethod
    def json_payload(document: Mapping[str, object]) -> bytes:
        return (json.dumps(dict(document), ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    def _save_json(self, filename: str, document: Mapping[str, object]) -> Path:
        return self._reservation.write_exclusive(filename, self.json_payload(document))

    def save_collection_log(self, document: Mapping[str, object]) -> Path:
        return self._save_json("collection_log.json", document)

    def save_manifest(self, document: Mapping[str, object]) -> Path:
        return self._save_json("manifest.json", document)
