"""Shared canonical Batch ID validation for collection and backup."""

from __future__ import annotations

import re
import uuid


BATCH_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class BatchIdValidationError(ValueError):
    """Raised when a Batch ID is not already in canonical UUID form."""


def canonical_batch_id(value: str) -> str:
    """Return an unchanged canonical UUID or raise a non-sensitive error."""

    if not isinstance(value, str) or not BATCH_ID_PATTERN.fullmatch(value):
        raise BatchIdValidationError("BATCH_ID_INVALID")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise BatchIdValidationError("BATCH_ID_INVALID") from error
    if str(parsed) != value:
        raise BatchIdValidationError("BATCH_ID_INVALID")
    return value
